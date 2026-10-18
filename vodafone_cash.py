"""Trusted Android SMS bridge. This is not a Vodafone or bank API.

Keep disabled until an authenticated HTTPS bridge is connected. Never accept
customer-supplied screenshots or SMS text as proof of payment.
"""
import hmac
import json
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from store import StoreError, money, display


def parse_receipt(sender, body, wallet, utc_offset=3):
    if sender != 'VF-Cash' or not isinstance(body, str) or len(body) > 4096:
        raise ValueError('invalid_sender_or_body')
    text = body.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    pattern = (r'\A\s*تم استلام مبلغ\s+([0-9]+\.[0-9]{2})\s+جنيه من\s+(01[0125][0-9]{8})[؛;]\s*'
               r'المسجل بإسم\s+[^\r\n]+\s+على رقم محفظتك\s+(01[0125][0-9]{8})\s+بتاريخ\s+'
               r'([0-9]{2}:[0-9]{2})\s+([0-9]{2}-[0-9]{2}-[0-9]{2})\.\s*'
               r'رصيدك الحالي:\s*[0-9]+\.[0-9]{2}\s+جنيه\s+رقم العملية:\s*([0-9]{6,32})(?:\s|$)')
    match = re.match(pattern, text)
    date_formats = ('%y-%m-%d %H:%M',)
    if not match:
        pattern = (r'\A\s*تم استلام مبلغ\s+([0-9]+(?:\.[0-9]{1,2})?)\s+جنيه من رقم\s+(01[0125][0-9]{8})\s*'
                   r'المسجل ب[اإأ]سم\s+.+?\s+على رقم محفظتك\s+(01[0125][0-9]{8})\s*\.\s*'
                   r'رصيدك الحالي:\s*[0-9]+(?:\.[0-9]{1,2})?\s+جنيه\s+'
                   r'تاريخ العملية:\s*([0-9]{2}:[0-9]{2})\s+([0-9]{2}-[0-9]{2}-[0-9]{2})\s+'
                   r'رقم العملية:\s*([0-9]{6,32})(?:\s|$)')
        match = re.match(pattern, text, flags=re.S)
        # Android RTL notifications can display the numeric date in either order.
        date_formats = ('%d-%m-%y %H:%M', '%y-%m-%d %H:%M')
    if not match or match[3] != wallet or text.count('رقم العملية:') != 1:
        raise ValueError('unrecognized_receipt')
    candidates = []
    for date_format in date_formats:
        try:
            parsed = datetime.strptime(match[5] + ' ' + match[4], date_format)
            candidates.append(parsed.replace(tzinfo=timezone(timedelta(hours=utc_offset))).timestamp())
        except ValueError:
            continue
    if not candidates:
        raise ValueError('invalid_date')
    stamp = min(candidates, key=lambda value: abs(time.time() - value))
    amount = money(match[1])
    if amount <= 0:
        raise ValueError('invalid_amount')
    return {'amount': amount, 'payer': match[2], 'transaction': match[6], 'timestamp': stamp}


class VodafoneCash:
    def __init__(self, path, store, wallet='01044266974', token='', enabled=False, utc_offset=3):
        self.store, self.wallet, self.token = store, wallet, token
        self.enabled, self.utc_offset = enabled, utc_offset
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS cash_quotes(
                id TEXT PRIMARY KEY, customer INTEGER NOT NULL, payer TEXT NOT NULL,
                amount INTEGER NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
                transaction_id TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS cash_receipts(
                transaction_id TEXT PRIMARY KEY, quote_id TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS cash_bridge(name TEXT PRIMARY KEY, value REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS cash_notifications(quote_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS cash_ingest_events(created REAL NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cash_unmatched_receipts(
                transaction_id TEXT PRIMARY KEY, amount INTEGER NOT NULL,
                payer TEXT NOT NULL, timestamp REAL NOT NULL, seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS cash_manual_reviews(
                transaction_id TEXT PRIMARY KEY, quote_id TEXT NOT NULL,
                reviewer INTEGER NOT NULL, reviewed REAL NOT NULL, reason TEXT NOT NULL);
        ''')

    def ready(self):
        with self.lock:
            row = self.db.execute("SELECT value FROM cash_bridge WHERE name='last_seen'").fetchone()
            return bool(self.enabled and len(self.token) >= 32 and row and time.time() - row[0] < 300)

    def quote(self, customer, amount, payer):
        if not self.ready():
            raise StoreError('Vodafone Cash SMS bridge is offline.')
        if not re.fullmatch(r'01[0125][0-9]{8}', payer) or not re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,2})?', amount):
            raise StoreError('Enter a valid Egyptian phone number and amount.')
        base, now = money(amount), time.time()
        if not money('5') <= base <= money('10000'):
            raise StoreError('Vodafone Cash amount must be between 5 and 10000 EGP.')
        with self.lock, self.db:
            if self.db.execute('SELECT count(*) FROM cash_quotes WHERE customer=? AND expires>? AND transaction_id IS NULL', (customer, now)).fetchone()[0] >= 3:
                raise StoreError('You already have 3 active Vodafone Cash requests.')
            previous = self.db.execute('SELECT * FROM cash_quotes WHERE payer=? AND amount=? AND expires>?', (payer, base, now)).fetchone()
            if previous:
                if previous['customer'] == customer and previous['transaction_id'] is None:
                    return {'id': previous['id'], 'amount': display(base), 'wallet': self.wallet}
                raise StoreError('في طلب شحن بنفس الرقم والمبلغ. انتظر انتهاء مدته أو اختار مبلغ مختلف.')
            identity, total = uuid.uuid4().hex, base
            self.db.execute('INSERT INTO cash_quotes VALUES (?,?,?,?,?,?,NULL)', (identity, customer, payer, total, now, now + 1800))
            return {'id': identity, 'amount': display(total), 'wallet': self.wallet}

    def receive(self, sender, body, received_at):
        now = time.time()
        if not self.enabled or abs(now - float(received_at)) > 120:
            raise ValueError('stale_or_disabled')
        receipt = parse_receipt(sender, body, self.wallet, self.utc_offset)
        if not now - 1860 <= receipt['timestamp'] <= now + 60:
            raise ValueError('stale_sms')
        with self.lock, self.db:
            previous = self.db.execute('SELECT quote_id FROM cash_receipts WHERE transaction_id=?', (receipt['transaction'],)).fetchone()
            if previous:
                quote = self.db.execute('SELECT * FROM cash_quotes WHERE id=?', (previous[0],)).fetchone()
            else:
                matches = self.db.execute('SELECT * FROM cash_quotes WHERE payer=? AND amount=? AND transaction_id IS NULL AND created<? AND expires>=? AND expires>=?',
                    (receipt['payer'], receipt['amount'], receipt['timestamp'] + 60, receipt['timestamp'], now)).fetchall()
                if len(matches) != 1:
                    self.db.execute('INSERT OR IGNORE INTO cash_unmatched_receipts VALUES (?,?,?,?,?)',
                        (receipt['transaction'], receipt['amount'], receipt['payer'], receipt['timestamp'], now))
                    return {'status': 'unmatched'}
                quote = matches[0]
                self.db.execute('INSERT INTO cash_receipts VALUES (?,?)', (receipt['transaction'], quote['id']))
                self.db.execute('UPDATE cash_quotes SET transaction_id=? WHERE id=?', (receipt['transaction'], quote['id']))
        # Persist the claim first. Retrying delivery recovers a crash before credit.
        self.store.credit_verified_payment(quote['customer'], quote['amount'], 'vodafone:' + receipt['transaction'])
        return {'status': 'credited', 'request': quote['id']}

    def settle_reviewed_receipt(self, identity, customer, transaction, reviewer, reason):
        """Internal owner-reviewed exception; never expose to customer/API input.

        Uses only a receipt already received through the authenticated phone.
        The calling owner administration must authorize the reviewer.
        """
        if not reason.strip():
            raise ValueError('review_reason_required')
        with self.lock, self.db:
            quote = self.db.execute('SELECT * FROM cash_quotes WHERE id=? AND customer=?', (identity, customer)).fetchone()
            receipt = self.db.execute('SELECT * FROM cash_unmatched_receipts WHERE transaction_id=?', (transaction,)).fetchone()
            if not quote or not receipt or quote['payer'] != receipt['payer'] or quote['amount'] != receipt['amount']:
                raise ValueError('review_mismatch')
            prior = self.db.execute('SELECT quote_id FROM cash_receipts WHERE transaction_id=?', (transaction,)).fetchone()
            if (prior and prior[0] != identity) or quote['transaction_id'] not in (None, transaction):
                raise ValueError('already_claimed')
            self.db.execute('INSERT OR IGNORE INTO cash_receipts VALUES (?,?)', (transaction, identity))
            self.db.execute('UPDATE cash_quotes SET transaction_id=? WHERE id=?', (transaction, identity))
            self.db.execute('INSERT OR IGNORE INTO cash_manual_reviews VALUES (?,?,?,?,?)', (transaction, identity, reviewer, time.time(), reason))
        return self.store.credit_verified_payment(customer, quote['amount'], 'vodafone:' + transaction)

    def pending_notifications(self):
        with self.lock:
            rows = self.db.execute('SELECT * FROM cash_quotes WHERE transaction_id IS NOT NULL AND id NOT IN (SELECT quote_id FROM cash_notifications)').fetchall()
        for row in rows:
            # Recover interruption between persisting the receipt and wallet credit.
            self.store.credit_verified_payment(row['customer'], row['amount'], 'vodafone:' + row['transaction_id'])
        return rows

    def notified(self, identity):
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO cash_notifications VALUES (?)', (identity,))


def make_sms_server(cash, host='127.0.0.1', port=8091):
    if len(cash.token) < 32:
        raise ValueError('SMS bridge token must be at least 32 characters')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.connection.settimeout(10)
            status, result = 400, {'error': 'invalid_request'}
            try:
                supplied = self.headers.get('Authorization', '')
                if not hmac.compare_digest(supplied.encode(), ('Bearer ' + cash.token).encode()):
                    status, result = 401, {'error': 'unauthorized'}
                elif self.path not in ('/sms/vodafone', '/sms/heartbeat'):
                    status, result = 404, {'error': 'not_found'}
                elif self.path == '/sms/heartbeat':
                    with cash.lock, cash.db:
                        cash.db.execute("INSERT OR REPLACE INTO cash_bridge VALUES ('last_seen',?)", (time.time(),))
                    status, result = 200, {'status': 'online'}
                else:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 8192:
                        raise ValueError('invalid_body_size')
                    raw = self.rfile.read(size)
                    content_type = self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
                    if content_type == 'text/plain':
                        # A paired, sender-filtered Android macro can forward the
                        # SMS verbatim, avoiding unsafe interpolation into JSON.
                        data = {'sender': self.headers.get('X-SMS-Sender', ''),
                                'body': raw.decode('utf-8'), 'received_at': time.time()}
                    else:
                        data = json.loads(raw)
                    result = cash.receive(data['sender'], data['body'], data['received_at'])
                    status = 200
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                known = {'invalid_sender_or_body', 'unrecognized_receipt', 'invalid_date',
                         'invalid_amount', 'stale_sms', 'stale_or_disabled', 'invalid_body_size'}
                reason = str(exc)
                result = {'error': reason if reason in known else 'invalid_request'}
            except Exception:
                status, result = 503, {'error': 'retry_same_receipt'}
            with cash.lock, cash.db:
                cash.db.execute('INSERT INTO cash_ingest_events VALUES (?,?)',
                    (time.time(), str(status) + ':' + result.get('status', result.get('error', 'unknown'))))
                cash.db.execute('DELETE FROM cash_ingest_events WHERE created<?', (time.time() - 86400,))
            payload = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return ThreadingHTTPServer((host, port), Handler)
