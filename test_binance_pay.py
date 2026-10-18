import os
import tempfile
import unittest
from unittest.mock import patch

from binance_pay import BinanceError, BinancePay
from store import Store, display


class FakeClient:
    def __init__(self):
        self.now = 1_800_000_000_000
        self.records = []
        self.calls = 0

    def clock_ms(self):
        return self.now

    def history(self):
        self.calls += 1
        return self.records


class BinancePaymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'BINANCE_API_KEY': 'fake-key', 'BINANCE_API_SECRET': 'fake-secret'})
        self.env.start()
        self.stores = {currency: Store(self.temp.name + '/' + currency + '.sqlite3', currency) for currency in ('EGP', 'USD')}
        self.config = {'BINANCE_ENABLED': '1', 'BINANCE_PAY_ID': '998877', 'BINANCE_RECEIVER_UID': '123456', 'BINANCE_USDT_EGP_RATE': '50', 'BINANCE_USDT_USD_RATE': '1'}
        self.client = FakeClient()
        self.pay = BinancePay(self.temp.name + '/payments.sqlite3', self.stores, lambda key, default='': self.config.get(key, default), self.client)

    def tearDown(self):
        self.pay.db.close()
        for store in self.stores.values():
            store.db.close()
        self.env.stop()
        self.temp.cleanup()

    def receipt(self, quote, transaction='TX_12345678'):
        return {'orderType': 'C2C', 'orderId': '460079334348996608', 'transactionId': transaction, 'transactionTime': quote['created'] + 1000,
                'amount': display(quote['amount']), 'currency': 'USDT', 'receiverInfo': {'binanceId': '123456'}}

    def prepare(self, currency='EGP', user=1):
        quote = self.pay.quote(user, currency, '10')
        self.client.now += 2000
        self.client.records = [self.receipt(quote)]
        return quote

    def test_exact_amounts_allow_multiple_customers_and_currencies(self):
        usd = self.pay.quote(1, 'USD', '10')
        egp = self.pay.quote(2, 'EGP', '10')
        self.assertEqual(display(usd['amount']), '10')
        self.assertEqual(display(usd['credit']), '10')
        self.assertEqual(display(egp['amount']), '10')
        self.assertEqual(display(egp['credit']), '500')
        self.assertNotEqual(usd['id'], egp['id'])

    def test_verified_income_credits_once_using_locked_rate(self):
        quote = self.prepare()
        self.config['BINANCE_USDT_EGP_RATE'] = '99'
        self.assertEqual(self.stores['EGP'].balance(1)['balance'], '0')
        result = self.pay.check(1, quote['id'], 'TX_12345678')
        self.assertTrue(result['changed'])
        self.assertEqual(self.stores['EGP'].customer(1)['balance'], quote['credit'])
        again = self.pay.check(1, quote['id'], 'TX_12345678')
        self.assertFalse(again['changed'])
        self.assertEqual(self.stores['EGP'].customer(1)['balance'], quote['credit'])

    def test_replay_across_customer_and_currency_is_rejected(self):
        quote = self.prepare('USD')
        self.pay.check(1, quote['id'], 'TX_12345678')
        another = self.pay.quote(2, 'EGP', '10')
        with self.assertRaises(BinanceError) as error:
            self.pay.check(2, another['id'], 'TX_12345678')
        self.assertEqual(error.exception.kind, 'used')
        with self.assertRaises(BinanceError):
            self.pay.check(2, quote['id'], 'TX_12345678')
        self.assertEqual(self.stores['EGP'].balance(2)['balance'], '0')

    def test_numeric_order_id_and_transaction_id_share_one_credit(self):
        quote = self.prepare('USD')
        result = self.pay.check(1, quote['id'], '460079334348996608')
        self.assertTrue(result['changed'])
        self.assertEqual(result['order_id'], '460079334348996608')
        self.assertEqual(result['transaction_id'], 'TX_12345678')
        self.assertFalse(self.pay.check(1, quote['id'], 'TX_12345678')['changed'])
        self.assertFalse(self.pay.check(1, quote['id'], '460079334348996608')['changed'])
        self.assertEqual(self.stores['USD'].customer(1)['balance'], quote['credit'])
        other = self.pay.quote(2, 'EGP', '10')
        for reference in ('460079334348996608', 'TX_12345678'):
            with self.assertRaises(BinanceError) as error:
                self.pay.check(2, other['id'], reference)
            self.assertEqual(error.exception.kind, 'used')

    def test_ambiguous_order_id_is_not_accepted(self):
        quote = self.prepare()
        second = dict(self.client.records[0], transactionId='OTHER_TX_123')
        self.client.records.append(second)
        with self.assertRaises(BinanceError) as error:
            self.pay.check(1, quote['id'], '460079334348996608')
        self.assertEqual(error.exception.kind, 'mismatch')
        self.assertEqual(self.stores['EGP'].balance(1)['balance'], '0')

    def test_wrong_recipient_amount_asset_time_and_outgoing_never_credit(self):
        quote = self.prepare()
        original = self.receipt(quote)
        variants = [dict(original, amount='-10'), dict(original, amount='999'), dict(original, currency='BTC'),
                    dict(original, orderType='PAY_REFUND'), dict(original, transactionTime=quote['created'] - 1),
                    dict(original, transactionTime=quote['expires'] + 1), dict(original, receiverInfo={'binanceId': '999999'})]
        for receipt in variants:
            with self.subTest(receipt=receipt):
                self.client.records = [receipt]
                self.pay.cache_until = 0
                with self.assertRaises(BinanceError) as error:
                    self.pay.check(1, quote['id'], 'TX_12345678')
                self.assertEqual(error.exception.kind, 'mismatch')
                self.assertEqual(self.stores['EGP'].balance(1)['balance'], '0')

    def test_missing_receipt_does_not_credit_and_reuses_history_cache(self):
        quote = self.prepare()
        self.client.records = []
        for _ in range(2):
            with self.assertRaises(BinanceError) as error:
                self.pay.check(1, quote['id'], 'TX_12345678')
            self.assertEqual(error.exception.kind, 'not_found')
        self.assertEqual(self.client.calls, 1)
        self.assertEqual(self.stores['EGP'].balance(1)['balance'], '0')

    def test_crash_after_claim_is_recoverable_without_another_provider_request(self):
        quote = self.prepare()
        store = self.stores['EGP']
        with patch.object(store, 'credit_verified_payment', side_effect=RuntimeError('simulated crash')):
            with self.assertRaises(RuntimeError):
                self.pay.check(1, quote['id'], 'TX_12345678')
        self.assertEqual(self.pay.request(1, quote['id'])['state'], 'verified')
        self.pay.check(1, quote['id'], 'TX_12345678')
        self.assertEqual(store.customer(1)['balance'], quote['credit'])
        self.assertEqual(self.client.calls, 1)
        self.pay.db.execute("UPDATE payment_requests SET state='verified' WHERE id=?", (quote['id'],))
        self.pay.check(1, quote['id'], 'TX_12345678')
        self.assertEqual(store.customer(1)['balance'], quote['credit'])

    def test_feature_stays_disabled_without_credentials_ids_and_explicit_rates(self):
        self.config['BINANCE_ENABLED'] = '0'
        self.assertEqual(self.pay.currencies(), [])
        with self.assertRaises(BinanceError):
            self.pay.quote(1, 'EGP', '10')
        self.config['BINANCE_ENABLED'] = '1'
        del self.config['BINANCE_USDT_EGP_RATE']
        self.assertEqual(self.pay.currencies(), ['USD'])
        with self.assertRaises(BinanceError):
            self.pay.quote(1, 'EGP', '10')


if __name__ == '__main__':
    unittest.main()
