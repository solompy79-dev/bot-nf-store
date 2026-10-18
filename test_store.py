import concurrent.futures
import json
import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from reseller_api import make_server
from store import Store, StoreError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name + '/test.sqlite3', 'EGP')
        topup = self.store.topup(1, '100', 'receipt')
        self.store.decide_topup(topup, True)

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def product(self, source='local', price='20'):
        identity = self.store.add_product({'name': 'Test', 'source': source, 'price': price})
        if source == 'local':
            self.store.add_stock(identity, 'secret delivery')
        return identity

    def test_approval_is_exactly_once(self):
        identity = self.store.topup(1, '25', 'proof')
        self.store.decide_topup(identity, True)
        self.store.decide_topup(identity, True)
        self.assertEqual(self.store.balance(1)['balance'], '125')
        self.store.decide_topup(identity, False)
        self.assertEqual(self.store.balance(1)['balance'], '125')

    def test_quote_does_not_charge_and_duplicate_purchase_does_not_charge_twice(self):
        product = self.product()
        identity = self.store.quote(1, product)
        self.assertEqual(self.store.balance(1)['balance'], '100')
        result = self.store.purchase(1, product, identity)
        self.assertEqual(result['delivery'], 'secret delivery')
        self.assertEqual(self.store.purchase(1, product, identity), result)
        self.assertEqual(self.store.balance(1)['balance'], '80')
        with self.assertRaises(StoreError):
            self.store.order(2, result['id'])

    def test_last_stock_cannot_sell_twice_concurrently(self):
        product = self.product()
        self.store.decide_topup(self.store.topup(2, '100', 'receipt2'), True)
        def purchase(user):
            try:
                return self.store.purchase(user, product, f'unique-key-{user}')['state']
            except StoreError:
                return 'sold_out'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(purchase, [1, 2]))
        self.assertCountEqual(results, ['completed', 'sold_out'])
        total = sum(int(self.store.balance(user)['balance']) for user in (1, 2))
        self.assertEqual(total, 180)

    def test_manual_fulfillment_and_refund(self):
        product = self.product('manual')
        result = self.store.purchase(1, product, 'manual-key-1')
        self.assertEqual(result['state'], 'waiting_admin')
        self.store.refund(result['id'], 'Unavailable')
        self.assertEqual(self.store.balance(1)['balance'], '100')
        with self.assertRaises(StoreError):
            self.store.refund(result['id'], 'Again')
        result = self.store.purchase(1, product, 'manual-key-2')
        self.store.fulfill(result['id'], 'Delivered')
        self.assertEqual(self.store.order(1, result['id'])['delivery'], 'Delivered')
        with self.assertRaises(StoreError):
            self.store.refund(result['id'], 'Again')

    def test_admin_refund_cannot_release_processing_supplier_funds(self):
        product = self.product('manual')
        order = self.store.purchase(1, product, 'manual-processing-1')
        self.store.db.execute("UPDATE orders SET state='processing' WHERE id=?", (order['id'],))
        with self.assertRaises(StoreError):
            self.store.refund(order['id'], 'racing state', manual_only=True)
        self.assertEqual(self.store.balance(1)['balance'], '80')

    def test_idempotency_key_cannot_change_product(self):
        first, second = self.product(), self.product()
        self.store.purchase(1, first, 'same-key-123')
        with self.assertRaises(StoreError):
            self.store.purchase(1, second, 'same-key-123')

    def test_money_and_combined_markup(self):
        from store import money, display
        self.assertEqual(display(Store.pricing(money('100'), money('10'), '5')), '115')
        for value in ('NaN', 'Infinity', '-1', 'abc'):
            with self.assertRaises(StoreError):
                money(value)

    def test_quotes_reject_changed_prices(self):
        product = self.product()
        identity = self.store.quote(1, product)
        self.store.db.execute('UPDATE products SET price=price+1 WHERE id=?', (product,))
        with self.assertRaises(StoreError):
            self.store.purchase(1, product, identity)
        self.assertEqual(self.store.balance(1)['balance'], '100')

    def test_uncertain_supplier_purchase_reuses_identity_and_debit(self):
        os.environ['TEST_STORE_SUPPLIER_KEY'] = 'fake-key'
        self.store.add_supplier('vendor', {'adapter': 'canboso', 'base_url': 'https://example.com', 'key_env': 'TEST_STORE_SUPPLIER_KEY'})
        remote_product = {'productId': 'remote', 'name': 'Remote', 'productType': 'account', 'price': {'amount': 10, 'currency': 'EGP'}, 'availability': {'available': 2}}
        purchases = []
        def transport(base, key, endpoint, body, identity, supplier):
            if endpoint == 'products':
                return {'products': [remote_product]}
            purchases.append((body, identity))
            if len(purchases) == 1:
                raise TimeoutError()
            return {'order': {'status': 'completed', 'orderCode': 'vendor-order'}, 'delivery': {'accounts': [{'user': 'u'}]}}
        self.store.transport = transport
        self.store.sync('vendor', '1', '10')
        product = self.store.catalog()[0]['id']
        with self.assertRaises(StoreError):
            self.store.purchase(1, product, 'supplier-key-1')
        self.assertEqual(self.store.balance(1)['balance'], '88')
        result = self.store.purchase(1, product, 'supplier-key-1')
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(purchases[0], purchases[1])
        self.assertEqual(self.store.balance(1)['balance'], '88')
        self.assertNotIn('supplier_order', result)

    def test_explicit_supplier_rejection_refunds_once(self):
        from store import SupplierRejected
        os.environ['TEST_STORE_SUPPLIER_KEY'] = 'fake-key'
        self.store.add_supplier('vendor', {'adapter': 'canboso', 'base_url': 'https://example.com', 'key_env': 'TEST_STORE_SUPPLIER_KEY'})
        remote = {'productId': 'r', 'name': 'R', 'productType': 'account', 'price': {'amount': 10, 'currency': 'EGP'}}
        def transport(base, key, endpoint, body, identity, supplier):
            if endpoint == 'products':
                return {'products': [remote]}
            raise SupplierRejected('insufficient supplier funds')
        self.store.transport = transport
        self.store.sync('vendor')
        product = self.store.catalog()[0]['id']
        result = self.store.purchase(1, product, 'rejected-key-123')
        self.assertEqual(result['state'], 'refunded')
        self.store.purchase(1, product, 'rejected-key-123')
        self.assertEqual(self.store.balance(1)['balance'], '100')

    def test_sync_imports_special_products_but_prevents_unsupported_checkout(self):
        os.environ['TEST_STORE_SUPPLIER_KEY'] = 'fake-key'
        self.store.add_supplier('vendor', {'adapter': 'canboso', 'base_url': 'https://example.com', 'key_env': 'TEST_STORE_SUPPLIER_KEY'})
        self.store.transport = lambda *args: {'products': [{'productId': 'slot', 'name': 'Slot', 'productType': 'slot', 'price': {'amount': 5, 'currency': 'EGP'}, 'availability': {'available': 4}, 'purchaseRequirements': {'customerEmail': True}}]}
        self.assertEqual(self.store.sync('vendor'), 1)
        product = self.store.catalog()[0]
        self.assertEqual(product['stock'], 4)
        self.assertFalse(product['purchasable'])
        with self.assertRaises(StoreError):
            self.store.purchase(1, product['id'], 'unsupported-slot')
        self.assertEqual(self.store.balance(1)['balance'], '100')
        self.store.set_visible(product['id'], False)
        self.store.sync('vendor')
        self.assertEqual(self.store.catalog(), [])

    def test_api_auth_key_rotation_and_own_orders(self):
        product = self.product()
        key = self.store.rotate_key(1)
        server = make_server({'EGP': self.store}, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}/v1/EGP'
        def call(path, token=key, body=None, identity=None):
            headers = {'Authorization': 'Bearer ' + token}
            if identity:
                headers['Idempotency-Key'] = identity
            req = Request(base + path, data=json.dumps(body).encode() if body else None, headers=headers)
            with urlopen(req) as response:
                return json.load(response)
        try:
            self.assertEqual(call('/balance')['balance'], '100')
            first = call('/purchase', body={'product_id': product}, identity='api-purchase-123')
            self.assertEqual(call('/purchase', body={'product_id': product}, identity='api-purchase-123'), first)
            other = self.store.rotate_key(2)
            with self.assertRaises(HTTPError) as error:
                call('/orders/' + first['id'], token=other)
            self.assertEqual(error.exception.code, 409)
            error.exception.close()
            self.store.rotate_key(1)
            with self.assertRaises(HTTPError) as error:
                call('/balance')
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
