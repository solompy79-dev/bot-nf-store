"""Read-only Binance Pay receipts and recoverable, exactly-once wallet credit."""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from store import SCALE, display, money


class BinanceError(Exception):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(kind)


def resolve_receipt(records, reference):
    """Match an exact app Order ID; keep legacy receipt IDs for recovery only."""
    receipts = [row for row in records if isinstance(row, dict)
                and (str(row.get('orderId', '')) == reference or str(row.get('transactionId', '')) == reference)]
    if not receipts:
        raise BinanceError('not_found')
    if len(receipts) != 1:
        raise BinanceError('mismatch')
    receipt = receipts[0]
    transaction_id, order_id = str(receipt.get('transactionId', '')), str(receipt.get('orderId', ''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{5,128}', transaction_id):
        raise BinanceError('mismatch')
    if order_id and not re.fullmatch(r'[0-9]{5,32}', order_id):
        raise BinanceError('mismatch')
    return receipt


class BinanceClient:
    """Only GET time and signed GET Pay history are implemented. No transfers."""
    def __init__(self):
        self.offset = 0
        self.synced = -1000
        self.blocked_until = 0

    def get(self, path, params=None, signed=False):
        if time.monotonic() < self.blocked_until:
            raise BinanceError('wait')
        params = dict(params or {})
        headers = {}
        if signed:
            key, secret = os.environ.get('BINANCE_API_KEY'), os.environ.get('BINANCE_API_SECRET')
            if not key or not secret:
                raise BinanceError('disabled')
            params.update(timestamp=self.clock_ms(), recvWindow=5000)
            query = urlencode(params)
            params['signature'] = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            headers['X-MBX-APIKEY'] = key
        url = 'https://api.binance.com' + path + ('?' + urlencode(params) if params else '')
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code in (418, 429):
                try:
                    delay = max(60, int(exc.headers.get('Retry-After', '60')))
                except ValueError:
                    delay = 60
                self.blocked_until = time.monotonic() + delay
                raise BinanceError('wait') from None
            raise BinanceError('service') from None
        except (URLError, OSError, ValueError):
            raise BinanceError('service') from None
        if not isinstance(payload, dict):
            raise BinanceError('service')
        return payload

    def clock_ms(self):
        if time.monotonic() - self.synced >= 60:
            payload = self.get('/api/v3/time')
            try:
                self.offset = int(payload['serverTime']) - int(time.time() * 1000)
            except (KeyError, ValueError, TypeError):
                raise BinanceError('service') from None
            self.synced = time.monotonic()
        return int(time.time() * 1000) + self.offset

    def history(self):
        now = self.clock_ms()
        payload = self.get('/sapi/v1/pay/transactions', {'startTime': now - 86_400_000, 'endTime': now, 'limit': 100}, signed=True)
        if payload.get('success') is not True or str(payload.get('code')) != '000000' or not isinstance(payload.get('data'), list):
            raise BinanceError('service')
        return payload['data']


class BinancePay:
    def __init__(self, path, stores, option, client=None):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS payment_requests(id TEXT PRIMARY KEY, customer INTEGER NOT NULL,
                wallet TEXT NOT NULL, receiver_uid TEXT NOT NULL, pay_id TEXT NOT NULL,
                amount INTEGER NOT NULL, credit INTEGER NOT NULL, rate TEXT NOT NULL,
                created INTEGER NOT NULL, expires INTEGER NOT NULL, state TEXT NOT NULL,
                transaction_id TEXT UNIQUE);
            DROP INDEX IF EXISTS payment_unique_active_amount;
            CREATE INDEX IF NOT EXISTS payment_active_amount
                ON payment_requests(receiver_uid,amount,state);
            CREATE TABLE IF NOT EXISTS payment_claims(transaction_id TEXT PRIMARY KEY, request TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS payment_submissions(request TEXT PRIMARY KEY, transaction_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS payment_order_ids(order_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL UNIQUE, request TEXT NOT NULL UNIQUE);
        ''')
        self.stores, self.option = stores, option
        self.client = client or BinanceClient()
        self.history_cache = []
        self.cache_until = 0

    def rate(self, currency):
        try:
            rate = Decimal(self.option('BINANCE_USDT_' + currency + '_RATE'))
            if not rate.is_finite() or not 0 < rate <= Decimal('1000000'):
                raise ValueError()
            return rate
        except (InvalidOperation, ValueError, TypeError):
            return None

    def configured(self):
        return (bool(re.fullmatch(r'[0-9]{4,24}', self.option('BINANCE_PAY_ID')))
                and bool(re.fullmatch(r'[0-9]{4,24}', self.option('BINANCE_RECEIVER_UID')))
                and bool(os.environ.get('BINANCE_API_KEY')) and bool(os.environ.get('BINANCE_API_SECRET')))

    def ready(self):
        return self.option('BINANCE_ENABLED', '0') == '1' and self.configured()

    def currencies(self):
        return [currency for currency in self.stores if self.rate(currency)] if self.ready() else []

    def request(self, user, identity):
        row = self.db.execute('SELECT * FROM payment_requests WHERE id=? AND customer=?', (identity, user)).fetchone()
        if not row:
            raise BinanceError('expired')
        return dict(row)

    def quote(self, user, currency, base_amount):
        if currency not in self.currencies():
            raise BinanceError('disabled')
        try:
            base = money(base_amount)
            if base <= 0 or base % 10000 or base > 1_000_000 * SCALE:
                raise ValueError()
        except Exception:
            raise BinanceError('amount') from None
        now = self.client.clock_ms()
        self.db.execute("UPDATE payment_requests SET state='expired' WHERE state='pending' AND expires<?", (now,))
        active = self.db.execute("SELECT count(*) FROM payment_requests WHERE customer=? AND state='pending'", (user,)).fetchone()[0]
        if active >= 3:
            raise BinanceError('active')
        rate = self.rate(currency)
        uid, pay_id = self.option('BINANCE_RECEIVER_UID'), self.option('BINANCE_PAY_ID')
        amount = base
        credit = int((Decimal(amount) * rate).quantize(Decimal('1'), rounding=ROUND_DOWN))
        if not 0 < credit <= 1_000_000_000 * SCALE:
            raise BinanceError('amount')
        identity = uuid.uuid4().hex
        self.db.execute('INSERT INTO payment_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)',
            (identity, user, currency, uid, pay_id, amount, credit, str(rate), now, now + 30 * 60_000, 'pending'))
        return self.request(user, identity)

    def settle(self, request):
        # The global claim binds this transaction permanently to one customer AND wallet.
        # Wallet credit has its own unique ledger reference, so a crash between these
        # commits is recoverable without ever crediting the receipt twice.
        store = self.stores[request['wallet']]
        changed = store.credit_verified_payment(request['customer'], request['credit'], 'binance:' + request['transaction_id'])
        self.db.execute("UPDATE payment_requests SET state='credited' WHERE id=?", (request['id'],))
        alias = self.db.execute('SELECT order_id FROM payment_order_ids WHERE request=?', (request['id'],)).fetchone()
        return {**self.request(request['customer'], request['id']), 'order_id': alias['order_id'] if alias else '', 'changed': changed}

    def check(self, user, identity, reference):
        request = self.request(user, identity)
        if request['state'] in ('verified', 'credited'):
            alias = self.db.execute('SELECT order_id FROM payment_order_ids WHERE request=?', (identity,)).fetchone()
            if reference != request['transaction_id'] and not (alias and reference == alias['order_id']):
                raise BinanceError('mismatch')
            return self.settle(request)
        if not self.ready() or self.option('BINANCE_RECEIVER_UID') != request['receiver_uid']:
            raise BinanceError('disabled')
        if not re.fullmatch(r'[A-Za-z0-9_-]{5,128}', reference):
            raise BinanceError('transaction')
        self.db.execute('INSERT OR REPLACE INTO payment_submissions VALUES (?,?)', (identity, reference))
        now = self.client.clock_ms()
        if now - request['created'] > 86_400_000:
            raise BinanceError('expired')
        claim = self.db.execute('SELECT request FROM payment_claims WHERE transaction_id=?', (reference,)).fetchone()
        alias = self.db.execute('SELECT request FROM payment_order_ids WHERE order_id=?', (reference,)).fetchone()
        if (claim and claim['request'] != identity) or (alias and alias['request'] != identity):
            raise BinanceError('used')
        if time.monotonic() >= self.cache_until:
            self.history_cache = self.client.history()
            self.cache_until = time.monotonic() + 60
        receipt = resolve_receipt(self.history_cache, reference)
        # Binance's live response includes an app-facing numeric orderId.
        # All aliases still share the same canonical receipt claim and ledger entry.
        transaction_id = str(receipt.get('transactionId', ''))
        order_id = str(receipt.get('orderId', ''))
        try:
            amount = Decimal(str(receipt['amount']))
            received_micro = amount * SCALE
            receiver = str(receipt['receiverInfo']['binanceId'])
            when = int(receipt['transactionTime'])
            valid = (receipt.get('orderType') in ('C2C', 'PAY') and receipt.get('currency') == 'USDT'
                     and amount.is_finite() and amount > 0 and received_micro == request['amount']
                     and receiver == request['receiver_uid']
                     and request['created'] <= when <= request['expires'] and when <= now)
        except (KeyError, TypeError, ValueError, InvalidOperation):
            valid = False
        if not valid:
            raise BinanceError('mismatch')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            claim = self.db.execute('SELECT request FROM payment_claims WHERE transaction_id=?', (transaction_id,)).fetchone()
            if claim and claim['request'] != identity:
                raise BinanceError('used')
            if order_id:
                alias = self.db.execute('SELECT * FROM payment_order_ids WHERE order_id=? OR transaction_id=? OR request=?', (order_id, transaction_id, identity)).fetchall()
                if any(row['request'] != identity or row['transaction_id'] != transaction_id or row['order_id'] != order_id for row in alias):
                    raise BinanceError('used')
                self.db.execute('INSERT OR IGNORE INTO payment_order_ids VALUES (?,?,?)', (order_id, transaction_id, identity))
            self.db.execute('INSERT OR IGNORE INTO payment_claims VALUES (?,?)', (transaction_id, identity))
            current = self.request(user, identity)
            if current['transaction_id'] and current['transaction_id'] != transaction_id:
                raise BinanceError('used')
            self.db.execute("UPDATE payment_requests SET state='verified',transaction_id=? WHERE id=?", (transaction_id, identity))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        return self.settle(self.request(user, identity))

    def submitted_transaction(self, user, identity):
        self.request(user, identity)
        row = self.db.execute('SELECT transaction_id FROM payment_submissions WHERE request=?', (identity,)).fetchone()
        if not row:
            raise BinanceError('transaction')
        return row['transaction_id']
