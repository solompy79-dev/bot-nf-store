import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from storefront import Storefront


class TelegramStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with patch('storefront.ROOT', Path(self.tmp.name)), patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'fake', 'ADMIN_TELEGRAM_ID': '99', 'API_ENABLED': '0'}):
            self.bot = Storefront()
        for user in (1, 2, 99):
            self.bot.set_language(user, 'ar')
        self.bot.send = Mock()
        self.bot.tg = Mock()

    def tearDown(self):
        self.bot.cash.db.close()
        self.bot.binance.db.close()
        self.bot.db.close()
        for store in self.bot.stores.values():
            store.db.close()
        self.tmp.cleanup()

    def msg(self, text, user=1, identity=1):
        return {'message': {'message_id': identity, 'from': {'id': user}, 'chat': {'id': user, 'type': 'private'}, 'text': text}}

    def cb(self, data, user=1):
        return {'callback_query': {'id': 'cb', 'from': {'id': user}, 'data': data, 'message': {'chat': {'id': user, 'type': 'private'}}}}

    def test_cash_pilot_is_owner_only(self):
        with patch.object(self.bot.cash, 'ready', return_value=True), patch.dict('os.environ', {'VODAFONE_TEST_ONLY': '1'}):
            self.assertTrue(self.bot.cash_available(99))
            self.assertFalse(self.bot.cash_available(1))
            self.bot.handle(self.cb('cashcharge', user=1))
            self.assertIsNone(self.bot.customer_form(1))
            self.bot.handle(self.cb('cashcharge', user=99))
            self.assertEqual(self.bot.customer_form(99)['kind'], 'cash_amount')

    def test_customer_topup_requires_owner_and_preserves_currency(self):
        self.bot.handle(self.cb('currency:USD'))
        self.bot.handle(self.msg('/topup 15 bank-reference'))
        usd = self.bot.stores['USD']
        pending = usd.pending_topups()[0]
        self.bot.handle(self.cb('approve:USD:' + pending['id'], user=1))
        self.assertEqual(usd.balance(1)['balance'], '0')
        self.bot.handle(self.cb('approve:USD:' + pending['id'], user=99))
        self.bot.handle(self.cb('approve:USD:' + pending['id'], user=99))
        self.assertEqual(usd.balance(1)['balance'], '15')
        self.assertEqual(self.bot.stores['EGP'].balance(1)['balance'], '0')

    def test_owner_creates_account_product_and_delivers_one_account(self):
        from store import StoreError
        self.bot.handle(self.cb('adm:newcurrency:EGP', user=99))
        self.bot.handle(self.msg('Account product', user=99))
        choices = self.bot.send.call_args.args[2]['inline_keyboard']
        self.assertEqual([r[0]['callback_data'] for r in choices[:3]], ['adm:source:link', 'adm:source:account', 'adm:source:manual'])
        self.bot.handle(self.cb('adm:source:account', user=99))
        self.bot.handle(self.msg('5', user=99))
        self.bot.handle(self.msg('Private account', user=99))
        self.bot.handle(self.cb('adm:confirmproduct', user=99))
        store = self.bot.stores['EGP']
        product = store.catalog()[0]['id']
        self.assertEqual(store.delivery_format(product), 'account')
        self.bot.handle(self.cb('adm:stock:EGP:' + product, user=99))
        self.bot.handle(self.msg('not-an-email', user=99))
        self.assertEqual(store.catalog()[0]['stock'], 0)
        self.bot.handle(self.msg('first@example.com', user=99))
        self.assertEqual(store.catalog()[0]['stock'], 0)
        self.bot.handle(self.msg('/private-password', user=99))
        self.assertEqual(store.catalog()[0]['stock'], 1)
        store.add_stock(product, 'Email: second@example.com\nPassword: second-password')
        with self.assertRaises(StoreError):
            store.add_stock(product, 'unstructured account')
        store.decide_topup(store.topup(1, '5', 'test'), True)
        result = store.purchase(1, product, store.quote(1, product))
        self.assertEqual(result['delivery'], 'Email: first@example.com\nPassword: /private-password')
        self.assertEqual(store.catalog()[0]['stock'], 1)
        self.assertEqual(store.balance(1)['balance'], '0')

    def test_owner_link_and_manual_product_options(self):
        from store import StoreError
        for kind in ('link', 'manual'):
            self.bot.handle(self.cb('adm:newcurrency:EGP', user=99))
            self.bot.handle(self.msg(kind + ' product', user=99))
            self.bot.handle(self.cb('adm:source:' + kind, user=99))
            self.bot.handle(self.msg('5', user=99))
            self.bot.handle(self.msg('-', user=99))
            self.bot.handle(self.cb('adm:confirmproduct', user=99))
        store = self.bot.stores['EGP']
        link = next(p for p in store.catalog() if p['name'] == 'link product')
        manual = next(p for p in store.catalog() if p['name'] == 'manual product')
        self.bot.handle(self.cb('adm:stock:EGP:' + link['id'], user=99))
        self.bot.handle(self.msg('https://example.com/delivery', user=99))
        self.assertEqual(store.delivery_format(link['id']), 'link')
        with self.assertRaises(StoreError):
            store.add_stock(link['id'], 'javascript:alert(1)')
        store.decide_topup(store.topup(1, '10', 'test'), True)
        result = store.purchase(1, link['id'], store.quote(1, link['id']))
        self.assertEqual(result['delivery'], 'https://example.com/delivery')
        result = store.purchase(1, manual['id'], store.quote(1, manual['id']))
        self.assertEqual(result['state'], 'waiting_admin')

    def test_free_service_wizard_catalog_and_all_delivery_methods(self):
        from store import StoreError
        store = self.bot.stores['EGP']
        store.add_product({'name': 'Paid product', 'price': '5', 'source': 'manual'})
        products = {}
        for kind in ('link', 'account', 'manual'):
            self.bot.handle(self.cb('adm:addfree', user=99))
            self.bot.handle(self.msg('Free ' + kind, user=99))
            self.bot.handle(self.cb('adm:source:' + kind, user=99))
            self.bot.handle(self.msg('-', user=99))
            self.bot.handle(self.cb('adm:confirmproduct', user=99))
            products[kind] = next(p['id'] for p in store.catalog() if p['name'] == 'Free ' + kind)
            with self.assertRaises(StoreError):
                store.set_price(products[kind], '5')
        store.add_stock(products['link'], 'https://example.com/activate')
        store.add_stock(products['account'], 'Email: free@example.com\nPassword: free-password')
        self.bot.handle(self.msg('🛍 Products'))
        labels = str(self.bot.send.call_args.args[2])
        self.assertIn('Paid product', labels)
        self.assertNotIn('Free link', labels)
        self.bot.handle(self.msg('🎁 خدمات مجانية'))
        labels = str(self.bot.send.call_args.args[2])
        self.assertIn('Free link', labels)
        self.assertNotIn('Paid product', labels)
        for kind, product in products.items():
            self.bot.handle(self.cb('pick:EGP:' + product))
            confirm = self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['callback_data']
            self.bot.handle(self.cb(confirm))
            text, markup = self.bot.send.call_args.args[1:3]
            if kind == 'link':
                self.assertEqual(markup['inline_keyboard'][0][0]['url'], 'https://example.com/activate')
                self.assertNotIn('https://example.com/activate', text)
            elif kind == 'account':
                self.assertIn('free@example.com', text)
                self.assertIn('free-password', text)
            else:
                self.assertIn('بانتظار التسليم', text)
            self.bot.handle(self.cb(confirm))
            self.assertEqual(store.balance(1)['balance'], '0')
        self.assertEqual(store.db.execute('SELECT count(*) FROM ledger').fetchone()[0], 0)
        self.assertEqual(len(store.orders(1)), 3)

    def test_delivery_activation_button_only_for_completed_valid_links(self):
        order = {'id': 'example-order', 'state': 'completed', 'amount': '0', 'currency': 'EGP', 'delivery': 'https://example.com/activate'}
        self.bot.send_order(1, 1, order)
        self.assertEqual(self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['url'], order['delivery'])
        self.assertIsNone(self.bot.order_delivery_url({**order, 'state': 'waiting_admin'}))
        self.assertIsNone(self.bot.order_delivery_url({**order, 'delivery': 'javascript:alert(1)'}))
        self.assertIsNone(self.bot.order_delivery_url({**order, 'delivery': 'Email: user@example.com\nPassword: secret'}))
        self.bot.notify(1, __import__('json').dumps(order))
        self.assertEqual(self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['url'], order['delivery'])

    def test_customer_cannot_add_products(self):
        self.bot.handle(self.msg('/product EGP {"name":"bad","price":"1"}'))
        self.assertEqual(self.bot.stores['EGP'].catalog(), [])

    def test_telegram_checkout_and_api_share_wallet(self):
        store = self.bot.stores['EGP']
        store.decide_topup(store.topup(1, '50', 'proof'), True)
        product = store.add_product({'name': 'Local', 'price': '10'})
        store.add_stock(product, 'private')
        self.bot.handle(self.cb('pick:EGP:' + product))
        markup = self.bot.send.call_args.args[2]
        pay = markup['inline_keyboard'][0][0]['callback_data']
        self.bot.handle(self.cb(pay))
        self.bot.handle(self.cb(pay))
        self.assertEqual(store.balance(1)['balance'], '40')
        self.assertEqual(store.orders(1)[0]['delivery'], 'private')
        self.bot.handle(self.cb(pay, user=2))
        self.assertEqual(store.balance(2)['balance'], '0')

    def test_catalog_does_not_change_with_selected_wallet(self):
        self.bot.stores['EGP'].add_product({'name': 'Egypt product', 'source': 'manual', 'price': '10'})
        self.bot.stores['USD'].add_product({'name': 'Dollar product', 'source': 'manual', 'price': '2'})
        self.bot.handle(self.msg('🛍 Products'))
        initial = self.bot.send.call_args
        self.bot.send.reset_mock()
        self.bot.handle(self.cb('currency:USD'))
        self.bot.send.reset_mock()
        self.bot.handle(self.msg('🛍 Products'))
        self.assertEqual(initial, self.bot.send.call_args)
        rows = initial.args[2]['inline_keyboard']
        self.assertTrue(all(len(row) == 1 for row in rows))
        tiles = [row[0] for row in rows if row[0]['callback_data'].startswith('view:')]
        self.assertEqual(len(tiles), 2)
        self.assertTrue(any('Egypt product | 10 EGP' in tile['text'] for tile in tiles))
        self.assertTrue(any('Dollar product | 2 USD' in tile['text'] for tile in tiles))
        self.bot.handle(self.cb(tiles[0]['callback_data']))
        self.assertIn('💵 السعر:', self.bot.send.call_args.args[1])
        self.assertEqual(self.bot.stores['USD'].balance(1)['balance'], '0')
        self.assertEqual(self.bot.stores['EGP'].balance(1)['balance'], '0')

    def test_admin_button_is_only_visible_to_owner(self):
        self.bot.handle(self.msg('/start', user=1))
        customer_keyboard = self.bot.send.call_args.args[2]['keyboard']
        self.assertNotIn('⚙️ لوحة الإدارة', [button['text'] for row in customer_keyboard for button in row])
        self.bot.handle(self.msg('/start', user=99))
        owner_keyboard = self.bot.send.call_args.args[2]['keyboard']
        self.assertIn('⚙️ لوحة الإدارة', [button['text'] for row in owner_keyboard for button in row])

    def test_customer_cannot_forge_admin_callbacks(self):
        product = self.bot.stores['EGP'].add_product({'name': 'Product', 'price': '5'})
        self.bot.handle(self.cb(f'adm:visible:EGP:{product}:0'))
        self.assertEqual(len(self.bot.stores['EGP'].catalog()), 1)
        self.bot.handle(self.cb('adm:newcurrency:EGP'))
        self.assertIsNone(self.bot.db.execute('SELECT value FROM admin_form WHERE customer=99').fetchone())

    def test_owner_product_wizard_stock_price_and_visibility(self):
        self.bot.handle(self.cb('adm:newcurrency:USD', user=99))
        self.bot.handle(self.msg('New product', user=99))
        self.bot.handle(self.cb('adm:source:local', user=99))
        self.bot.handle(self.msg('7.5', user=99))
        self.bot.handle(self.msg('Description', user=99))
        self.bot.handle(self.cb('adm:confirmproduct', user=99))
        store = self.bot.stores['USD']
        product = store.catalog()[0]
        self.assertEqual(product['price'], '7.5')
        self.bot.handle(self.cb(f"adm:stock:USD:{product['id']}", user=99))
        self.bot.handle(self.msg('one private stock payload', user=99))
        self.assertEqual(store.catalog()[0]['stock'], 1)
        self.bot.handle(self.cb(f"adm:price:USD:{product['id']}", user=99))
        self.bot.handle(self.msg('9', user=99))
        self.assertEqual(store.catalog()[0]['price'], '9')
        self.bot.handle(self.cb(f"adm:visible:USD:{product['id']}:0", user=99))
        self.assertEqual(store.catalog(), [])
        self.bot.handle(self.cb(f"adm:visible:USD:{product['id']}:1", user=99))
        self.assertEqual(store.catalog()[0]['stock'], 1)

    def test_settings_survive_form_and_apply_without_restart(self):
        self.bot.handle(self.cb('adm:payment', user=99))
        self.bot.handle(self.msg('Transfer details', user=99))
        self.bot.handle(self.msg('👛 Wallet'))
        self.assertNotIn('Transfer details', self.bot.send.call_args.args[1])

    def test_product_photo_and_owner_photo_upload(self):
        store = self.bot.stores['USD']
        identity = store.add_product({'name': 'Photo product', 'price': '2', 'source': 'manual'})
        self.bot.handle(self.cb(f'adm:image:USD:{identity}', user=99))
        message = self.msg('', user=99)
        message['message']['photo'] = [{'file_id': 'small'}, {'file_id': 'telegram_photo_id'}]
        self.bot.handle(message)
        self.assertEqual(store.catalog()[0]['image'], 'telegram_photo_id')
        self.bot.handle(self.cb(f'view:USD:{identity}:0'))
        self.bot.tg.assert_called_with('sendPhoto', chat_id=1, photo='telegram_photo_id', caption=unittest.mock.ANY, reply_markup=unittest.mock.ANY)
        self.assertEqual(store.balance(1)['balance'], '0')

    def test_broken_photo_falls_back_to_product_text(self):
        from main import ApiError
        store = self.bot.stores['USD']
        identity = store.add_product({'name': 'Photo product', 'price': '2'})
        store.set_image(identity, 'https://example.com/missing.png')
        self.bot.tg.side_effect = lambda method, **kwargs: (_ for _ in ()).throw(ApiError('bad image', code=400)) if method == 'sendPhoto' else None
        self.bot.handle(self.cb(f'view:USD:{identity}:0'))
        self.assertIn('Photo product', self.bot.send.call_args.args[1])

    def test_first_visit_requires_language_then_sets_default_currency(self):
        self.bot.handle(self.msg('/start', user=7))
        message = self.bot.send.call_args
        self.assertIn('Choose your language', message.args[1])
        self.assertEqual([b['callback_data'] for b in message.args[2]['inline_keyboard'][0]], ['lang:ar', 'lang:en'])
        self.assertIsNone(self.bot.language(7))
        self.bot.handle(self.cb('lang:en', user=7))
        self.assertEqual(self.bot.language(7), 'en')
        self.assertEqual(self.bot.selected(7).currency, 'USD')
        self.assertIn('Welcome to NF STORE', self.bot.send.call_args.args[1])
        keyboard = self.bot.send.call_args.args[2]['keyboard']
        self.assertIn('🌐 Language', [button['text'] for row in keyboard for button in row])
        self.bot.handle(self.msg('/start', user=7))
        self.assertIn('Welcome to NF STORE', self.bot.send.call_args.args[1])
        self.bot.handle(self.cb('lang:ar', user=8))
        self.assertEqual(self.bot.selected(8).currency, 'EGP')
        self.assertIn('🛍 المنتجات', [b['text'] for row in self.bot.send.call_args.args[2]['keyboard'] for b in row])

    def test_language_changes_preserve_balances_keys_and_products(self):
        store = self.bot.stores['EGP']
        store.decide_topup(store.topup(1, '50', 'receipt'), True)
        key = store.rotate_key(1)
        store.add_product({'name': 'Merchant product', 'price': '10'})
        before = self.bot.all_products()
        self.bot.handle(self.cb('lang:en'))
        self.assertEqual(store.balance(1)['balance'], '50')
        self.assertEqual(self.bot.stores['USD'].balance(1)['balance'], '0')
        self.assertEqual(store.authenticate(key), 1)
        self.assertEqual(self.bot.all_products(), before)
        self.bot.handle(self.cb('currency:EGP'))
        self.bot.handle(self.msg('/start'))
        self.assertEqual(self.bot.selected(1).currency, 'EGP')
        self.assertEqual(self.bot.language(1), 'en')
        self.assertIn('Welcome', self.bot.send.call_args.args[1])

    def test_english_checkout_errors_wallet_and_delivery(self):
        self.bot.handle(self.cb('lang:en'))
        store = self.bot.stores['USD']
        identity = store.add_product({'name': 'Original product name', 'price': '5'})
        store.add_stock(identity, 'original private payload')
        self.bot.handle(self.cb('pick:USD:' + identity))
        self.assertIn('Insufficient', self.bot.send.call_args.args[1])
        store.decide_topup(store.topup(1, '20', 'proof'), True)
        self.bot.handle(self.cb('pick:USD:' + identity))
        self.assertIn('Review your purchase', self.bot.send.call_args.args[1])
        pay = self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['callback_data']
        self.bot.handle(self.cb(pay))
        self.assertIn('Completed', self.bot.send.call_args.args[1])
        self.assertIn('original private payload', self.bot.send.call_args.args[1])
        self.bot.handle(self.msg('👛 Wallet'))
        self.assertIn('Selected top-up wallet: USD', self.bot.send.call_args.args[1])
        self.bot.handle(self.cb('newkey'))
        confirm_key = self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['callback_data']
        self.bot.handle(self.cb(confirm_key))
        self.assertIn('Wallet: USD', self.bot.send.call_args.args[1])
        self.assertIn('Access key:', self.bot.send.call_args.args[1])

    def test_guided_topup_snapshots_currency_and_cannot_duplicate_credit(self):
        self.bot.handle(self.cb('deposit:USD'))
        self.bot.handle(self.msg('12.5'))
        message = self.msg('Bank reference')
        message['message']['photo'] = [{'file_id': 'receipt_file_id'}]
        self.bot.handle(message)
        confirm = self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['callback_data']
        self.assertEqual(self.bot.stores['USD'].balance(1)['balance'], '0')
        self.bot.handle(self.cb(confirm))
        self.bot.handle(self.cb(confirm))
        pending = self.bot.stores['USD'].pending_topups()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['proof'], 'photo:receipt_file_id\nBank reference')
        self.assertEqual(self.bot.stores['EGP'].pending_topups(), [])
        action = 'approve:USD:' + pending[0]['id']
        self.bot.handle(self.cb(action, user=99))
        self.bot.handle(self.cb(action, user=99))
        self.assertEqual(self.bot.stores['USD'].balance(1)['balance'], '12.5')

    def test_cancelled_quote_cannot_be_charged_by_old_button(self):
        store = self.bot.stores['EGP']
        store.decide_topup(store.topup(1, '20', 'proof'), True)
        product = store.add_product({'name': 'Manual', 'source': 'manual', 'price': '5'})
        self.bot.handle(self.cb('pick:EGP:' + product))
        rows = self.bot.send.call_args.args[2]['inline_keyboard']
        pay, cancel = rows[0][0]['callback_data'], rows[1][0]['callback_data']
        self.bot.handle(self.cb(cancel))
        self.bot.handle(self.cb(pay))
        self.assertEqual(store.balance(1)['balance'], '20')
        self.assertEqual(store.orders(1), [])

    def test_api_key_requires_confirmation_and_duplicate_confirmation_does_not_rotate(self):
        store = self.bot.stores['EGP']
        old = store.rotate_key(1)
        self.bot.handle(self.cb('newkey'))
        self.assertEqual(store.authenticate(old), 1)
        confirm = self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['callback_data']
        self.bot.handle(self.cb(confirm))
        with store.lock:
            new_hash = store.db.execute('SELECT hash FROM keys WHERE customer=1').fetchone()[0]
        self.assertIsNone(store.authenticate(old))
        self.bot.handle(self.cb(confirm))
        with store.lock:
            self.assertEqual(store.db.execute('SELECT hash FROM keys WHERE customer=1').fetchone()[0], new_hash)

    def test_warranty_uses_owned_order_currency_and_reuses_open_ticket(self):
        store = self.bot.stores['USD']
        store.decide_topup(store.topup(1, '20', 'proof'), True)
        product = store.add_product({'name': 'Local', 'price': '5'})
        store.add_stock(product, 'delivery')
        order = store.purchase(1, product, 'cross-currency-order')
        self.assertEqual(self.bot.selected(1).currency, 'EGP')
        self.bot.handle(self.msg('/claim ' + order['id'] + ' issue'))
        self.bot.handle(self.cb('claim:USD:' + order['id']))
        self.bot.handle(self.msg('same issue'))
        self.assertEqual(store.db.execute('SELECT count(*) FROM tickets').fetchone()[0], 1)
        self.bot.handle(self.cb('claim:USD:' + order['id'], user=2))
        self.assertIsNone(self.bot.customer_form(2))

    def test_malformed_buttons_do_not_stop_bot(self):
        for action in ('adm:price', 'currency:', 'view:USD', 'submitdeposit:', 'order:XYZ:nope'):
            self.bot.handle(self.cb(action, user=99))
        self.bot.handle(self.msg('/start'))
        self.assertIn('معرّف حسابك:', self.bot.send.call_args.args[1])

    def test_admin_can_edit_name_and_description(self):
        store = self.bot.stores['EGP']
        product = store.add_product({'name': 'Old', 'price': '5'})
        self.bot.handle(self.cb(f'adm:name:EGP:{product}', user=99))
        self.bot.handle(self.msg('New name', user=99))
        self.bot.handle(self.cb(f'adm:description:EGP:{product}', user=99))
        self.bot.handle(self.msg('New description', user=99))
        item = store.catalog()[0]
        self.assertEqual((item['name'], item['description']), ('New name', 'New description'))

    def test_deposit_notification_uses_recipients_language(self):
        self.bot.handle(self.cb('lang:en'))
        store = self.bot.stores['USD']
        topup = store.topup(1, '15', 'proof')
        self.bot.handle(self.cb('approve:USD:' + topup, user=99))
        self.assertEqual(self.bot.send.call_args.args[0], 1)
        self.assertIn('Approved', self.bot.send.call_args.args[1])

    def test_binance_customer_flow_credits_only_verified_receipt(self):
        import os
        from test_binance_pay import FakeClient
        from store import display
        config = {'BINANCE_ENABLED': '1', 'BINANCE_PAY_ID': '998877', 'BINANCE_RECEIVER_UID': '123456', 'BINANCE_USDT_EGP_RATE': '50'}
        with self.bot.db:
            for key, value in config.items():
                self.bot.db.execute('INSERT OR REPLACE INTO shop_options VALUES (?,?)', (key, value))
        client = FakeClient()
        self.bot.binance.client = client
        with patch.dict(os.environ, {'BINANCE_API_KEY': 'fake-key', 'BINANCE_API_SECRET': 'fake-secret'}):
            self.bot.handle(self.cb('charge'))
            self.assertEqual(self.bot.send.call_args.args[2]['inline_keyboard'][0][0]['callback_data'], 'binance')
            self.bot.handle(self.cb('bnwallet:EGP'))
            self.bot.handle(self.msg('10'))
            form = self.bot.customer_form(1)
            quote = self.bot.binance.request(1, form['request'])
            buttons = self.bot.send.call_args.args[2]['inline_keyboard']
            self.assertEqual(buttons[0][0]['copy_text'], {'text': '998877'})
            self.assertEqual(buttons[1][0]['copy_text'], {'text': display(quote['amount'])})
            self.assertEqual(self.bot.stores['EGP'].balance(1)['balance'], '0')
            client.now += 2000
            client.records = [{'orderType': 'C2C', 'orderId': '460079334348996608', 'transactionId': 'TX_12345678', 'transactionTime': quote['created'] + 1000,
                               'amount': display(quote['amount']), 'currency': 'USDT', 'receiverInfo': {'binanceId': '123456'}}]
            self.bot.handle(self.msg('460079334348996608'))
            self.assertEqual(self.bot.stores['EGP'].customer(1)['balance'], quote['credit'])
            self.bot.handle(self.cb('bncheck:' + quote['id']))
            self.assertEqual(self.bot.stores['EGP'].customer(1)['balance'], quote['credit'])

    def test_binance_credit_currency_does_not_change_wallet_preference(self):
        import os
        from test_binance_pay import FakeClient
        with self.bot.db:
            for key, value in {'BINANCE_ENABLED': '1', 'BINANCE_PAY_ID': '998877', 'BINANCE_RECEIVER_UID': '123456', 'BINANCE_USDT_EGP_RATE': '54', 'BINANCE_USDT_USD_RATE': '1'}.items():
                self.bot.db.execute('INSERT OR REPLACE INTO shop_options VALUES (?,?)', (key, value))
        self.bot.binance.client = FakeClient()
        with patch.dict(os.environ, {'BINANCE_API_KEY': 'fake', 'BINANCE_API_SECRET': 'fake'}):
            self.bot.handle(self.cb('binance'))
            self.assertIn('1 USDT = 54 EGP', self.bot.send.call_args.args[1])
            self.assertIn('1 USDT = 1 USD', self.bot.send.call_args.args[1])
            self.bot.handle(self.cb('bnwallet:USD'))
            self.assertEqual(self.bot.selected(1).currency, 'EGP')
            self.bot.handle(self.msg('10'))
            quote = self.bot.binance.request(1, self.bot.customer_form(1)['request'])
            self.assertEqual(quote['wallet'], 'USD')
            self.assertEqual(quote['amount'], quote['credit'])
            self.assertEqual(self.bot.selected(1).currency, 'EGP')
            self.bot.handle(self.cb('binance'))
            self.bot.handle(self.cb('bnwallet:EGP'))
            self.assertEqual(self.bot.customer_form(1)['currency'], 'EGP')

    def test_only_owner_can_change_binance_rates(self):
        self.bot.handle(self.cb('adm:bn_rate_USD', user=1))
        self.assertIsNone(self.bot.customer_form(1))
        self.bot.handle(self.cb('adm:bn_rate_EGP', user=99))
        self.bot.handle(self.msg('51.25', user=99))
        self.assertEqual(str(self.bot.binance.rate('EGP')), '51.25')
        self.assertFalse(self.bot.binance.ready())


if __name__ == '__main__':
    unittest.main()
