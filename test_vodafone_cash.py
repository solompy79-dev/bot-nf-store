import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from store import Store, display, money
from vodafone_cash import VodafoneCash, make_sms_server, parse_receipt


def sms(amount, transaction='024742315677', wallet='01044266974', payer='01000000001', timestamp=None):
    amount = format(Decimal(amount), '.2f')
    stamp = datetime.fromtimestamp(timestamp or time.time(), timezone(timedelta(hours=3))).strftime('%H:%M %y-%m-%d')
    return (f'تم استلام مبلغ {amount} جنيه من {payer}؛\nالمسجل بإسم TEST USER\n'
            f'على رقم محفظتك {wallet} بتاريخ {stamp}.\nرصيدك الحالي: 462.22 جنيه\nرقم العملية: {transaction}\n')


class CashTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'store.db', 'EGP', None)
        self.cash = VodafoneCash(Path(self.tmp.name) / 'cash.db', self.store, token='x' * 48, enabled=True)
        with self.cash.db:
            self.cash.db.execute("INSERT INTO cash_bridge VALUES ('last_seen',?)", (time.time(),))

    def tearDown(self):
        self.cash.db.close()
        self.store.db.close()
        self.tmp.cleanup()

    def quote(self):
        return self.cash.quote(1, '450', '01000000001')

    def test_exact_credit_and_replay(self):
        quote = self.quote()
        body = sms(quote['amount'])
        for _ in range(2):
            self.assertEqual(self.cash.receive('VF-Cash', body, time.time())['status'], 'credited')
        self.assertEqual(self.store.balance(1)['balance'], quote['amount'])
        self.assertEqual(len(self.cash.pending_notifications()), 1)
        self.cash.notified(quote['id'])
        self.assertEqual(self.cash.pending_notifications(), [])

    def test_sender_recipient_and_staleness(self):
        quote = self.quote()
        invalid = [('Vodafone', sms(quote['amount']), time.time()),
                   ('VF-Cash', sms(quote['amount'], wallet='01044266975'), time.time()),
                   ('VF-Cash', sms(quote['amount'], timestamp=time.time()-7200), time.time()),
                   ('VF-Cash', sms(quote['amount']), time.time()-180)]
        for sender, body, received in invalid:
            with self.assertRaises(ValueError):
                self.cash.receive(sender, body, received)
        self.assertEqual(self.store.balance(1)['balance'], '0')

    def test_integer_receipt_with_alternate_wording(self):
        quote = self.cash.quote(1, '5', '01000000001')
        stamp = datetime.now(timezone(timedelta(hours=3))).strftime('%H:%M %d-%m-%y')
        body = (f'تم استلام مبلغ 5 جنيه من رقم 01000000001 المسجل باسم TEST USER '
                f'على رقم محفظتك 01044266974. رصيدك الحالي: 416.22 جنيه '
                f'تاريخ العملية: {stamp} رقم العملية: 024757421701\nتابع كل مصروفاتك')
        self.assertEqual(self.cash.receive('VF-Cash', body, time.time())['status'], 'credited')
        self.assertEqual(self.store.balance(1)['balance'], '5')
        self.cash.receive('VF-Cash', body, time.time())
        self.assertEqual(self.store.balance(1)['balance'], '5')

    def test_actual_receipt_spelling_and_date_order(self):
        from unittest.mock import patch
        stamp = datetime(2026, 10, 15, 20, 40, tzinfo=timezone(timedelta(hours=3))).timestamp()
        template = ('تم استلام مبلغ 5 جنيه من رقم 01000000001 المسجل بإسم TEST USER '
                    'على رقم محفظتك  01044266974.\nرصيدك الحالي: 416.22 جنيه\n'
                    'تاريخ العملية: 20:40 {date}\nرقم العملية: 024757421701\n'
                    'تابع كل مصروفاتك من تاريخ المعاملات')
        with patch('vodafone_cash.time.time', return_value=stamp + 60):
            for date in ('26-10-15', '15-10-26'):
                receipt = parse_receipt('VF-Cash', template.format(date=date), self.cash.wallet)
                self.assertEqual(receipt['timestamp'], stamp)
                self.assertEqual(receipt['amount'], money('5'))

    def test_wrong_amount_payer_expired_and_old_sms_never_credit(self):
        quote = self.quote()
        for body in (sms('449.00'), sms(quote['amount'], payer='01000000002'), sms(quote['amount'], timestamp=time.time()-120)):
            self.assertEqual(self.cash.receive('VF-Cash', body, time.time())['status'], 'unmatched')
        with self.cash.db:
            self.cash.db.execute('UPDATE cash_quotes SET expires=?', (time.time()-1,))
        self.assertEqual(self.cash.receive('VF-Cash', sms(quote['amount']), time.time())['status'], 'unmatched')
        self.assertEqual(self.store.balance(1)['balance'], '0')

    def test_review_requires_authenticated_receipt_and_credits_once(self):
        quote = self.quote()
        with self.assertRaises(ValueError):
            self.cash.settle_reviewed_receipt(quote['id'], 1, '024742315677', 99, 'review')
        body = sms('450', timestamp=time.time()-120)
        self.assertEqual(self.cash.receive('VF-Cash', body, time.time())['status'], 'unmatched')
        with self.assertRaises(ValueError):
            self.cash.settle_reviewed_receipt(quote['id'], 2, '024742315677', 99, 'review')
        self.assertTrue(self.cash.settle_reviewed_receipt(quote['id'], 1, '024742315677', 99, 'payment predates quote'))
        self.assertFalse(self.cash.settle_reviewed_receipt(quote['id'], 1, '024742315677', 99, 'retry'))
        self.assertEqual(self.store.balance(1)['balance'], '450')

    def test_receipt_matches_quote_in_last_second_of_minute(self):
        from unittest.mock import patch
        minute = int(time.time() // 60) * 60
        with patch('vodafone_cash.time.time', return_value=minute + 59.9):
            quote = self.quote()
        body = sms(quote['amount'], timestamp=minute)
        with patch('vodafone_cash.time.time', return_value=minute + 60.1):
            self.assertEqual(self.cash.receive('VF-Cash', body, minute + 60.1)['status'], 'credited')

    def test_recovery_after_credit_failure(self):
        from unittest.mock import patch
        quote = self.quote()
        with patch.object(self.store, 'credit_verified_payment', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.cash.receive('VF-Cash', sms(quote['amount']), time.time())
        self.cash.pending_notifications()
        self.cash.pending_notifications()
        self.assertEqual(self.store.balance(1)['balance'], quote['amount'])

    def test_bridge_requires_secret(self):
        import threading
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        server = make_sms_server(self.cash, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/sms/vodafone'
            with self.assertRaises(HTTPError) as failure:
                urlopen(Request(url, data=b'{}'), timeout=3)
            self.assertEqual(failure.exception.code, 401)
            failure.exception.close()
            quote = self.quote()
            payload = json.dumps({'sender': 'VF-Cash', 'body': sms(quote['amount']), 'received_at': time.time()}).encode()
            with urlopen(Request(url, data=payload, headers={'Authorization': 'Bearer ' + self.cash.token}), timeout=3) as response:
                self.assertEqual(json.load(response)['status'], 'credited')
            second = self.cash.quote(1, '451', '01000000001')
            raw = sms(second['amount'], transaction='024742315678').encode('utf-8')
            headers = {'Authorization': 'Bearer ' + self.cash.token,
                       'Content-Type': 'text/plain; charset=utf-8', 'X-SMS-Sender': 'VF-Cash'}
            with urlopen(Request(url, data=raw, headers=headers), timeout=3) as response:
                self.assertEqual(json.load(response)['status'], 'credited')
            self.assertEqual(self.store.customer(1)['balance'], money(quote['amount']) + money(second['amount']))
        finally:
            server.shutdown()
            server.server_close()

    def test_exact_amount_and_conflicting_requests(self):
        from store import StoreError
        first, second = self.quote(), self.quote()
        self.assertEqual(first['amount'], '450')
        self.assertEqual(first['id'], second['id'])
        with self.assertRaises(StoreError):
            self.cash.quote(2, '450', '01000000001')
        independent = self.cash.quote(2, '450', '01000000002')
        self.assertEqual(independent['amount'], '450')
        self.assertNotEqual(first['id'], independent['id'])
        with self.cash.db:
            self.cash.db.execute("UPDATE cash_bridge SET value=?", (time.time()-301,))
        self.assertFalse(self.cash.ready())


if __name__ == '__main__':
    unittest.main()
