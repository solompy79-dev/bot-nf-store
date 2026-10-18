"""Shared wallet, stock, order and supplier logic for Telegram and reseller API."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from urllib.parse import urljoin, urlsplit
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


SCALE = 1_000_000


class StoreError(Exception):
    pass


class SupplierRejected(StoreError):
    """Upstream explicitly confirmed rejection, so no charge is ambiguous."""


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > Decimal('1000000000'):
            raise ValueError()
        return int((number * SCALE).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        raise StoreError('المبلغ غير صالح.') from None


def display(amount):
    return format(Decimal(amount) / SCALE, '.6f').rstrip('0').rstrip('.') or '0'


class Store:
    def __init__(self, path, currency='USD', transport=None):
        self.currency = currency
        self.transport = transport
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0 CHECK(balance>=0));
            CREATE TABLE IF NOT EXISTS keys(hash TEXT PRIMARY KEY, customer INTEGER NOT NULL REFERENCES customers(id));
            CREATE TABLE IF NOT EXISTS suppliers(id TEXT PRIMARY KEY, config TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
                remote_id TEXT, cost INTEGER NOT NULL, fixed INTEGER NOT NULL, percent TEXT NOT NULL,
                price INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, description TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS stock(id INTEGER PRIMARY KEY, product TEXT NOT NULL REFERENCES products(id),
                payload TEXT NOT NULL, order_id TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, customer INTEGER NOT NULL REFERENCES customers(id),
                idem TEXT NOT NULL, product TEXT NOT NULL, price INTEGER NOT NULL, body TEXT NOT NULL,
                state TEXT NOT NULL, result TEXT, created REAL NOT NULL, UNIQUE(customer,idem));
            CREATE TABLE IF NOT EXISTS topups(id TEXT PRIMARY KEY, customer INTEGER NOT NULL REFERENCES customers(id),
                amount INTEGER NOT NULL, proof TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending');
            CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY, customer INTEGER NOT NULL,
                delta INTEGER NOT NULL, reference TEXT NOT NULL UNIQUE, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, customer INTEGER NOT NULL,
                order_id TEXT NOT NULL, message TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'open');
            CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS product_details(product TEXT PRIMARY KEY, kind TEXT NOT NULL,
                requirements TEXT NOT NULL, available INTEGER, supported INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS product_media(product TEXT PRIMARY KEY, supplier_image TEXT NOT NULL DEFAULT '',
                override_image TEXT);
            CREATE TABLE IF NOT EXISTS product_brand(product TEXT PRIMARY KEY, brand TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS product_delivery_format(
                product TEXT PRIMARY KEY REFERENCES products(id), kind TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS free_services(product TEXT PRIMARY KEY REFERENCES products(id));
            CREATE INDEX IF NOT EXISTS stock_available ON stock(product,order_id);
            CREATE INDEX IF NOT EXISTS orders_customer_created ON orders(customer,created DESC);
            CREATE INDEX IF NOT EXISTS tickets_customer_order ON tickets(customer,order_id,state);
        ''')
        with self.lock:
            saved = self.db.execute("SELECT value FROM meta WHERE name='currency'").fetchone()
            if saved and saved['value'] != currency:
                raise StoreError('عملة قاعدة البيانات مختلفة عن STORE_CURRENCY.')
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('currency',?)", (currency,))

    def transaction(self, action):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                result = action()
                self.db.execute('COMMIT')
                return result
            except BaseException:
                self.db.execute('ROLLBACK')
                raise

    def customer(self, user):
        with self.lock:
            self.db.execute('INSERT OR IGNORE INTO customers(id) VALUES (?)', (user,))
            return self.db.execute('SELECT * FROM customers WHERE id=?', (user,)).fetchone()

    def balance(self, user):
        return {'balance': display(self.customer(user)['balance']), 'currency': self.currency}

    def credit_verified_payment(self, user, amount, reference):
        """Internal only: the payment verifier supplies the verified, immutable quote."""
        if not isinstance(amount, int) or amount <= 0 or not reference.startswith(('binance:', 'vodafone:')):
            raise StoreError('المبلغ غير صالح.')
        self.customer(user)
        def action():
            previous = self.db.execute('SELECT customer,delta FROM ledger WHERE reference=?', (reference,)).fetchone()
            if previous:
                if previous['customer'] != user or previous['delta'] != amount:
                    raise StoreError('اختيار غير صالح.')
                return False
            self.db.execute('UPDATE customers SET balance=balance+? WHERE id=?', (amount, user))
            self.db.execute('INSERT INTO ledger(customer,delta,reference,created) VALUES (?,?,?,?)', (user, amount, reference, time.time()))
            return True
        return self.transaction(action)

    def rotate_key(self, user):
        self.customer(user)
        key = 'shop_' + secrets.token_urlsafe(32)
        def action():
            self.db.execute('DELETE FROM keys WHERE customer=?', (user,))
            self.db.execute('INSERT INTO keys VALUES (?,?)', (hashlib.sha256(key.encode()).hexdigest(), user))
        self.transaction(action)
        return key

    def authenticate(self, key):
        with self.lock:
            row = self.db.execute('SELECT customer FROM keys WHERE hash=?', (hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
        return row['customer'] if row else None

    def topup(self, user, amount, proof, identity=None):
        self.customer(user)
        amount = money(amount)
        if amount <= 0 or not proof or len(proof) > 2000:
            raise StoreError('أرسل مبلغ موجب وإثبات تحويل.')
        identity = identity or uuid.uuid4().hex
        with self.lock:
            self.db.execute('INSERT OR IGNORE INTO topups(id,customer,amount,proof) VALUES (?,?,?,?)', (identity, user, amount, proof))
        return identity

    def decide_topup(self, identity, approve):
        def action():
            row = self.db.execute('SELECT * FROM topups WHERE id=?', (identity,)).fetchone()
            if not row:
                raise StoreError('طلب الشحن غير موجود.')
            if row['state'] != 'pending':
                return {**dict(row), 'changed': False}
            state = 'approved' if approve else 'rejected'
            if approve:
                self.db.execute('UPDATE customers SET balance=balance+? WHERE id=?', (row['amount'], row['customer']))
                self.db.execute('INSERT INTO ledger(customer,delta,reference,created) VALUES (?,?,?,?)', (row['customer'], row['amount'], 'topup:' + identity, time.time()))
            self.db.execute('UPDATE topups SET state=? WHERE id=?', (state, identity))
            return {**dict(row), 'state': state, 'changed': True}
        return self.transaction(action)

    def pending_topups(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM topups WHERE state='pending' LIMIT 30")]

    def add_supplier(self, identity, config):
        if not identity.isascii() or not identity.isalnum() or len(identity) > 24 or identity in ('local', 'manual'):
            raise StoreError('اسم المورد حروف وأرقام فقط، بحد أقصى 24.')
        # New API contracts need an explicit adapter, never guess purchase semantics.
        if config.get('adapter') != 'canboso' or not config.get('key_env'):
            raise StoreError('المتاح حاليًا adapter=canboso مع key_env. أي API مختلف يحتاج موصّل خاص.')
        if not config.get('base_url', '').startswith('https://'):
            raise StoreError('رابط المورد يجب أن يبدأ بـ https://')
        with self.lock:
            existing = self.db.execute('SELECT config FROM suppliers WHERE id=?', (identity,)).fetchone()
            if existing and json.loads(existing['config']) != config:
                raise StoreError('اسم المورد مستخدم. استخدم اسم جديد لتجنب تغيير وجهة الطلبات القديمة.')
            self.db.execute('INSERT OR IGNORE INTO suppliers VALUES (?,?)', (identity, json.dumps(config)))

    def supplier_config(self, identity):
        with self.lock:
            row = self.db.execute('SELECT config FROM suppliers WHERE id=?', (identity,)).fetchone()
        if not row:
            raise StoreError('المورد غير موجود.')
        config = json.loads(row['config'])
        key = os.environ.get(config['key_env'])
        if not key:
            raise StoreError('مفتاح المورد غير موجود في إعدادات السيرفر.')
        return config, key

    def remote(self, supplier, endpoint, body=None, identity=None):
        config, key = self.supplier_config(supplier)
        with self.lock:
            cooldown = self.db.execute('SELECT value FROM meta WHERE name=?', ('cooldown:' + supplier,)).fetchone()
        if cooldown and float(cooldown['value']) > time.time():
            raise StoreError('المورد طلب الانتظار. حاول لاحقًا بنفس الطلب.')
        return self.transport(config['base_url'], key, endpoint, body, identity, supplier)

    def cooldown(self, supplier, seconds):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('cooldown:' + supplier, str(time.time() + max(1, seconds))))

    @staticmethod
    def pricing(cost, fixed, percent):
        try:
            percent = Decimal(str(percent))
            if not percent.is_finite() or not 0 <= percent <= 10000:
                raise ValueError()
            return int((Decimal(cost) * (1 + percent / 100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) + fixed
        except (InvalidOperation, ValueError):
            raise StoreError('نسبة الربح غير صالحة.') from None

    def add_product(self, data):
        identity = data.get('id') or uuid.uuid4().hex[:12]
        if not identity.isascii() or not identity.isalnum() or len(identity) > 32:
            raise StoreError('معرف المنتج حروف وأرقام فقط وبحد أقصى 32.')
        source = data.get('source', 'local')
        delivery_format = data.get('delivery_format', 'manual' if source == 'manual' else 'text')
        if delivery_format not in ('link', 'account', 'manual', 'text') or (delivery_format == 'manual') != (source == 'manual'):
            raise StoreError('نوع بيانات التسليم لا يطابق طريقة تسليم المنتج.')
        if source not in ('local', 'manual'):
            raise StoreError('استعمل مزامنة المورد لإضافة منتجات API.')
        name = str(data['name']).strip()
        if not name or len(name) > 180:
            raise StoreError('اسم المنتج مطلوب وبحد أقصى 180 حرف.')
        cost, fixed = money(data.get('cost', 0)), money(data.get('fixed', 0))
        percent = str(data.get('percent', 0))
        is_free = data.get('is_free', False)
        if type(is_free) is not bool:
            raise StoreError('قيمة الخدمة المجانية غير صالحة.')
        price = money(data['price']) if 'price' in data else (0 if is_free else self.pricing(cost, fixed, percent))
        if price < 0 or (price == 0 and not is_free) or (is_free and price != 0):
            raise StoreError('سعر البيع لازم يكون أكبر من صفر.')
        def action():
            if self.db.execute('SELECT 1 FROM products WHERE id=?', (identity,)).fetchone():
                raise StoreError('معرف المنتج مستخدم.')
            self.db.execute('INSERT INTO products(id,name,source,cost,fixed,percent,price,description) VALUES (?,?,?,?,?,?,?,?)',
                            (identity, name, source, cost, fixed, percent, price, str(data.get('description', ''))[:1500]))
            self.db.execute('INSERT INTO product_delivery_format VALUES (?,?)', (identity, delivery_format))
            if is_free:
                self.db.execute('INSERT INTO free_services VALUES (?)', (identity,))
        self.transaction(action)
        return identity

    def sync(self, supplier, fixed='0', percent='0'):
        fixed = money(fixed)
        self.pricing(0, fixed, percent)
        response = self.remote(supplier, 'products')
        products = response.get('products', [])
        prepared = []
        for product in products:
            if product['price']['currency'] != self.currency:
                continue
            cost = money(product['price']['amount'])
            price = self.pricing(cost, fixed, percent)
            if price <= 0:
                continue
            identity = hashlib.sha256((supplier + ':' + product['productId']).encode()).hexdigest()[:24]
            prepared.append((identity, product['name'][:180], supplier, product['productId'], cost, fixed, str(percent), price, str(product.get('description', ''))[:1500]))
        def action():
            self.db.execute('UPDATE products SET active=0 WHERE source=?', (supplier,))
            for row in prepared:
                self.db.execute('''INSERT INTO products(id,name,source,remote_id,cost,fixed,percent,price,description) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name,cost=excluded.cost,fixed=excluded.fixed,
                    percent=excluded.percent,price=excluded.price,active=1,description=excluded.description''', row)
            for product in products:
                identity = hashlib.sha256((supplier + ':' + product['productId']).encode()).hexdigest()[:24]
                if not any(row[0] == identity for row in prepared):
                    continue
                requirements = product.get('purchaseRequirements') or {}
                supported = product.get('productType') == 'account' and not any(requirements.values())
                self.db.execute('INSERT OR REPLACE INTO product_details VALUES (?,?,?,?,?)',
                    (identity, product.get('productType', 'account'), json.dumps(requirements), product.get('availability', {}).get('available'), int(supported)))
        self.transaction(action)
        self.update_supplier_images(supplier, products)
        return len(prepared)

    def update_supplier_images(self, supplier, products):
        config, _ = self.supplier_config(supplier)
        def action():
            for product in products:
                identity = hashlib.sha256((supplier + ':' + product['productId']).encode()).hexdigest()[:24]
                if not self.db.execute('SELECT 1 FROM products WHERE id=? AND source=?', (identity, supplier)).fetchone():
                    continue
                image = str(product.get('image') or '').strip()
                if image:
                    image = urljoin(config['base_url'].rstrip('/') + '/', image)
                    parsed = urlsplit(image)
                    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or len(image) > 2000:
                        image = ''
                self.db.execute('''INSERT INTO product_media(product,supplier_image) VALUES (?,?)
                    ON CONFLICT(product) DO UPDATE SET supplier_image=excluded.supplier_image''', (identity, image))
                self.db.execute('INSERT OR REPLACE INTO product_brand VALUES (?,?)', (identity, str(product.get('emoji') or '')[:100]))
        self.transaction(action)

    def set_image(self, identity, image):
        if not isinstance(image, str) or len(image) > 2000:
            raise StoreError('الصورة غير صالحة.')
        if image.startswith(('http://', 'https://')):
            parsed = urlsplit(image)
            if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
                raise StoreError('رابط الصورة لازم يكون https بدون بيانات دخول.')
        elif image and not all(c.isascii() and (c.isalnum() or c in '_-') for c in image):
            raise StoreError('ابعت صورة أو رابط صورة مباشر يبدأ بـ https://')
        with self.lock:
            if not self.db.execute('SELECT 1 FROM products WHERE id=?', (identity,)).fetchone():
                raise StoreError('المنتج غير موجود.')
            self.db.execute('''INSERT INTO product_media(product,override_image) VALUES (?,?)
                ON CONFLICT(product) DO UPDATE SET override_image=excluded.override_image''', (identity, image))

    def delivery_format(self, product):
        with self.lock:
            row = self.db.execute('SELECT p.source,f.kind FROM products p LEFT JOIN product_delivery_format f ON f.product=p.id WHERE p.id=?', (product,)).fetchone()
        if not row:
            raise StoreError('المنتج غير موجود.')
        return row['kind'] or ('manual' if row['source'] == 'manual' else 'text' if row['source'] == 'local' else 'supplier')

    def add_stock(self, product, payload):
        with self.lock:
            row = self.db.execute('SELECT source FROM products WHERE id=?', (product,)).fetchone()
            if not row or row['source'] != 'local' or not payload or len(payload) > 12000:
                raise StoreError('المنتج لازم يكون محلي وبيانات التسليم غير فارغة وأقل من 12000 حرف.')
            kind = self.delivery_format(product)
            if kind == 'link':
                payload = payload.strip()
                parsed = urlsplit(payload)
                if parsed.scheme not in ('https', 'http') or not parsed.hostname or any(char.isspace() for char in payload):
                    raise StoreError('أرسل رابطًا صحيحًا يبدأ بـ https:// أو http:// لقطعة واحدة.')
            elif kind == 'account':
                match = re.fullmatch(r'Email: ([^\s@]+@[^\s@]+\.[^\s@]+)\nPassword: ([^\r\n]+)', payload)
                if not match or not match[2].strip():
                    raise StoreError('بيانات الحساب غير مكتملة. أضف البريد الإلكتروني وكلمة المرور من لوحة الإدارة.')
            self.db.execute('INSERT INTO stock(product,payload) VALUES (?,?)', (product, payload))

    def catalog(self):
        with self.lock:
            rows = self.db.execute('''SELECT p.*, d.available, d.supported, b.brand, COALESCE(m.override_image,m.supplier_image,'') AS image,
                EXISTS(SELECT 1 FROM free_services f WHERE f.product=p.id) AS is_free,
                (SELECT count(*) FROM stock s WHERE s.product=p.id AND s.order_id IS NULL) AS stock
                FROM products p LEFT JOIN product_details d ON d.product=p.id
                LEFT JOIN product_media m ON m.product=p.id
                LEFT JOIN product_brand b ON b.product=p.id
                WHERE active=1 AND NOT EXISTS(SELECT 1 FROM meta WHERE name='hidden:' || p.id) ORDER BY name''').fetchall()
        return [{'id': r['id'], 'name': r['name'], 'description': r['description'], 'price': display(r['price']),
                 'currency': self.currency, 'stock': r['stock'] if r['source'] == 'local' else r['available'],
                 'purchasable': r['supported'] != 0,
                 'image': r['image'],
                 'brand': r['brand'] or '',
                 'is_free': bool(r['is_free']),
                 'delivery': 'manual' if r['source'] == 'manual' else 'automatic'} for r in rows]

    def set_visible(self, identity, visible):
        with self.lock:
            if not self.db.execute('SELECT 1 FROM products WHERE id=?', (identity,)).fetchone():
                raise StoreError('المنتج غير موجود.')
            if visible:
                self.db.execute('DELETE FROM meta WHERE name=?', ('hidden:' + identity,))
            else:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('hidden:' + identity, '1'))

    def set_price(self, identity, price):
        price = money(price)
        if price <= 0:
            raise StoreError('سعر البيع لازم يكون أكبر من صفر.')
        with self.lock:
            if self.db.execute('SELECT 1 FROM free_services WHERE product=?', (identity,)).fetchone():
                raise StoreError('الخدمة مجانية ولا تحتاج سعر بيع.')
            cursor = self.db.execute('UPDATE products SET price=? WHERE id=?', (price, identity))
            if cursor.rowcount != 1:
                raise StoreError('المنتج غير موجود.')

    def set_product_text(self, identity, field, value):
        if field not in ('name', 'description'):
            raise StoreError('اختيار غير صالح.')
        value = value.strip()
        if (field == 'name' and not 1 <= len(value) <= 180) or len(value) > 1500:
            raise StoreError('اسم المنتج بحد أقصى 180 حرف، والوصف بحد أقصى 1500 حرف.')
        with self.lock:
            cursor = self.db.execute('UPDATE products SET ' + field + '=? WHERE id=?', (value, identity))
            if cursor.rowcount != 1:
                raise StoreError('المنتج غير موجود.')

    def quote(self, user, product):
        identity = uuid.uuid4().hex
        self.reserve(user, product, identity, reserve=False)
        return identity

    def cancel_quote(self, user, identity):
        with self.lock:
            self.db.execute("UPDATE orders SET state='cancelled' WHERE customer=? AND idem=? AND state='quoted'", (user, identity))

    def reserve(self, user, product, identity, reserve=True):
        if not isinstance(identity, str) or not 8 <= len(identity) <= 128:
            raise StoreError('Idempotency-Key مطلوب من 8 إلى 128 حرف.')
        self.customer(user)
        def action():
            previous = self.db.execute('SELECT * FROM orders WHERE customer=? AND idem=?', (user, identity)).fetchone()
            if previous:
                if previous['product'] != product:
                    raise StoreError('رقم العملية مستخدم لمنتج مختلف.')
                return dict(previous)
            item = self.db.execute('SELECT * FROM products WHERE id=? AND active=1', (product,)).fetchone()
            if not item:
                raise StoreError('المنتج غير موجود أو غير متاح.')
            hidden = self.db.execute('SELECT 1 FROM meta WHERE name=?', ('hidden:' + product,)).fetchone()
            details = self.db.execute('SELECT supported FROM product_details WHERE product=?', (product,)).fetchone()
            if hidden:
                raise StoreError('المنتج غير متاح حاليًا.')
            if details and not details['supported']:
                raise StoreError('المنتج يحتاج تجهيز بيانات إضافية؛ تواصل مع الدعم قبل الشراء.')
            balance = self.db.execute('SELECT balance FROM customers WHERE id=?', (user,)).fetchone()['balance']
            if balance < item['price']:
                raise StoreError('رصيدك غير كافي. اشحن المحفظة الأول.')
            order_id = uuid.uuid4().hex
            stock = None
            if item['source'] == 'local':
                stock = self.db.execute('SELECT * FROM stock WHERE product=? AND order_id IS NULL ORDER BY id LIMIT 1', (product,)).fetchone()
                if not stock:
                    raise StoreError('المخزون خلص.')
            body = {'source': item['source'], 'product_id': item['remote_id'], 'cost': item['cost'], 'name': item['name'],
                    'delivery_format': self.delivery_format(product)}
            # Quotes are persisted but do not reserve funds; execution reserves atomically.
            state = 'reserved' if reserve else 'quoted'
            self.db.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)', (order_id, user, identity, product, item['price'], json.dumps(body), state, None, time.time()))
            if reserve:
                self._debit(user, item['price'], order_id)
                if stock:
                    self.db.execute('UPDATE stock SET order_id=? WHERE id=?', (order_id, stock['id']))
            return dict(self.db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone())
        return self.transaction(action)

    def _debit(self, user, price, identity):
        if price == 0:
            return
        cursor = self.db.execute('UPDATE customers SET balance=balance-? WHERE id=? AND balance>=?', (price, user, price))
        if cursor.rowcount != 1:
            raise StoreError('رصيدك غير كافي.')
        self.db.execute('INSERT INTO ledger(customer,delta,reference,created) VALUES (?,?,?,?)', (user, -price, 'order:' + identity, time.time()))

    def _activate(self, row):
        def action():
            current = self.db.execute('SELECT * FROM orders WHERE id=?', (row['id'],)).fetchone()
            if current['state'] != 'quoted':
                return dict(current)
            if time.time() - current['created'] > 900:
                raise StoreError('انتهت صلاحية السعر. اختار المنتج من جديد.')
            product = self.db.execute('SELECT * FROM products WHERE id=? AND active=1', (current['product'],)).fetchone()
            if not product or product['price'] != current['price'] or product['cost'] != json.loads(current['body'])['cost']:
                raise StoreError('السعر اتغير. اختار المنتج من جديد.')
            if self.db.execute('SELECT 1 FROM meta WHERE name=?', ('hidden:' + current['product'],)).fetchone():
                raise StoreError('المنتج غير متاح حاليًا.')
            stock = None
            if product['source'] == 'local':
                stock = self.db.execute('SELECT id FROM stock WHERE product=? AND order_id IS NULL LIMIT 1', (product['id'],)).fetchone()
                if not stock:
                    raise StoreError('المخزون خلص.')
            self._debit(current['customer'], current['price'], current['id'])
            if stock:
                self.db.execute('UPDATE stock SET order_id=? WHERE id=?', (current['id'], stock['id']))
            self.db.execute("UPDATE orders SET state='reserved' WHERE id=?", (current['id'],))
            return dict(self.db.execute('SELECT * FROM orders WHERE id=?', (current['id'],)).fetchone())
        return self.transaction(action)

    def purchase(self, user, product, identity):
        row = self._activate(self.reserve(user, product, identity))
        if row['state'] not in ('reserved', 'processing', 'uncertain'):
            return self.order(user, row['id'])
        body = json.loads(row['body'])
        if body['source'] == 'local':
            with self.lock:
                stock = self.db.execute('SELECT payload FROM stock WHERE order_id=?', (row['id'],)).fetchone()
                self.db.execute("UPDATE orders SET state='completed',result=? WHERE id=? AND state='reserved'", (json.dumps({'delivery': stock['payload']}), row['id']))
        elif body['source'] == 'manual':
            with self.lock:
                self.db.execute("UPDATE orders SET state='waiting_admin' WHERE id=? AND state='reserved'", (row['id'],))
        else:
            # A persistent lease avoids parallel calls; an uncertain retry uses the exact stored request.
            def claim():
                current = self.db.execute('SELECT state,result FROM orders WHERE id=?', (row['id'],)).fetchone()
                result = json.loads(current['result'] or '{}')
                if current['state'] == 'processing' and result.get('lease', 0) > time.time():
                    return False
                if current['state'] not in ('reserved', 'uncertain', 'processing'):
                    return False
                self.db.execute("UPDATE orders SET state='processing',result=? WHERE id=?", (json.dumps({'lease': time.time() + 120}), row['id']))
                return True
            if not self.transaction(claim):
                return self.order(user, row['id'])
            try:
                if not body.get('verified'):
                    products = self.remote(body['source'], 'products').get('products', [])
                    remote = next((p for p in products if p['productId'] == body['product_id']), None)
                    if not remote or remote['price']['currency'] != self.currency or money(remote['price']['amount']) != body['cost'] or remote.get('availability', {}).get('available') == 0:
                        return self.refund(row['id'], 'السعر أو المخزون اتغير؛ اختار المنتج بعد مزامنة المورد.')
                    if remote.get('productType') != 'account' or any((remote.get('purchaseRequirements') or {}).values()):
                        return self.refund(row['id'], 'المنتج يحتاج بيانات إضافية غير مدعومة.')
                    body['verified'] = True
                    with self.lock:
                        self.db.execute('UPDATE orders SET body=? WHERE id=?', (json.dumps(body), row['id']))
                response = self.remote(body['source'], 'purchase', {'product_id': body['product_id'], 'quantity': 1}, row['id'])
                state = 'completed' if response.get('order', {}).get('status') == 'completed' else 'supplier_pending'
                result = {'delivery': response.get('delivery'), 'supplier_order': response.get('order', {}).get('orderCode')}
                with self.lock:
                    self.db.execute('UPDATE orders SET state=?,result=? WHERE id=?', (state, json.dumps(result), row['id']))
            except SupplierRejected:
                return self.refund(row['id'], 'المورد رفض الطلب؛ تم رد الرصيد لمحفظتك.')
            except Exception:
                # Never refund an ambiguous network result: supplier may already have charged.
                with self.lock:
                    self.db.execute("UPDATE orders SET state='uncertain',result=NULL WHERE id=?", (row['id'],))
                raise StoreError('نتيجة المورد غير مؤكدة؛ الرصيد محجوز. أعد نفس الطلب بنفس زر التأكيد أو نفس Idempotency-Key.') from None
        return self.order(user, row['id'])

    def refund(self, identity, reason, manual_only=False):
        def action():
            row = self.db.execute('SELECT * FROM orders WHERE id=?', (identity,)).fetchone()
            if not row or row['state'] not in ('processing', 'waiting_admin', 'reserved'):
                raise StoreError('حالة الطلب لا تسمح بالاسترداد.')
            if manual_only and (row['state'] != 'waiting_admin' or json.loads(row['body'])['source'] != 'manual'):
                raise StoreError('الرد متاح للطلبات اليدوية المنتظرة فقط.')
            self.db.execute('UPDATE customers SET balance=balance+? WHERE id=?', (row['price'], row['customer']))
            self.db.execute('INSERT INTO ledger(customer,delta,reference,created) VALUES (?,?,?,?)', (row['customer'], row['price'], 'refund:' + identity, time.time()))
            self.db.execute("UPDATE orders SET state='refunded',result=? WHERE id=?", (json.dumps({'message': reason}), identity))
            return row['customer']
        user = self.transaction(action)
        return self.order(user, identity)

    def fulfill(self, identity, delivery):
        if not delivery or len(delivery) > 12000:
            raise StoreError('بيانات التسليم مطلوبة وبحد أقصى 12000 حرف.')
        def action():
            row = self.db.execute('SELECT * FROM orders WHERE id=?', (identity,)).fetchone()
            if not row or row['state'] != 'waiting_admin':
                raise StoreError('الطلب غير منتظر تسليم يدوي.')
            self.db.execute("UPDATE orders SET state='completed',result=? WHERE id=?", (json.dumps({'delivery': delivery}), identity))
            return row['customer']
        return self.transaction(action)

    def order(self, user, identity):
        with self.lock:
            row = self.db.execute('SELECT * FROM orders WHERE id=? AND customer=?', (identity, user)).fetchone()
        if not row:
            raise StoreError('الطلب غير موجود.')
        result = json.loads(row['result'] or '{}')
        # Supplier identifiers, costs and internal leases never go to a reseller.
        result = {k: v for k, v in result.items() if k in ('delivery', 'message')}
        return {'id': row['id'], 'product_id': row['product'], 'product_name': json.loads(row['body']).get('name', ''),
                'created_at': row['created'], 'state': row['state'], 'amount': display(row['price']), 'currency': self.currency, **result}

    def orders(self, user):
        with self.lock:
            rows = self.db.execute("SELECT id FROM orders WHERE customer=? AND state NOT IN ('quoted','cancelled') ORDER BY created DESC LIMIT 30", (user,)).fetchall()
        return [self.order(user, row['id']) for row in rows]

    def ticket(self, user, identity, message):
        order = self.order(user, identity)
        if order['state'] != 'completed' or not message.strip() or len(message) > 1500:
            raise StoreError('طلب الضمان غير صالح.')
        def action():
            existing = self.db.execute("SELECT id FROM tickets WHERE customer=? AND order_id=? AND state='open'", (user, identity)).fetchone()
            if existing:
                return existing['id']
            ticket = uuid.uuid4().hex
            self.db.execute('INSERT INTO tickets(id,customer,order_id,message) VALUES (?,?,?,?)', (ticket, user, identity, message))
            return ticket
        return self.transaction(action)
