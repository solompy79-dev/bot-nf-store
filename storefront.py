import json
import os
import re
import sqlite3
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from main import ApiError, Bot, ROOT
from reseller_api import make_server
from store import Store, StoreError, SupplierRejected, display
from admin_panel import AdminPanel
from product_icons import icon_for, plain_buttons
from localization import TEXT, translate, error_text
from customer_flows import CustomerFlows
from binance_pay import BinancePay, BinanceError
from vodafone_cash import VodafoneCash, make_sms_server
from navigation import Navigation


class Storefront(Navigation, CustomerFlows, AdminPanel, Bot):
    def __init__(self):
        self.token = os.environ['TELEGRAM_BOT_TOKEN']
        self.owner = int(os.environ['ADMIN_TELEGRAM_ID'])
        self.stores = {currency: Store(ROOT / ('shop_' + currency + '.sqlite3'), currency, self.transport) for currency in ('EGP', 'USD')}
        self.db = sqlite3.connect(ROOT / 'telegram.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY,value TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS preferences(customer INTEGER PRIMARY KEY,currency TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS customer_language(customer INTEGER PRIMARY KEY,language TEXT NOT NULL)')
        self.init_navigation()
        self.init_admin()
        self.init_customer_flows()
        self.binance = BinancePay(ROOT / 'binance_pay.sqlite3', self.stores, self.option)
        self.cash = VodafoneCash(ROOT / 'vodafone_cash.sqlite3', self.stores['EGP'],
            wallet=os.environ.get('VODAFONE_WALLET', '01044266974'),
            token=os.environ.get('SMS_BRIDGE_TOKEN', ''),
            enabled=os.environ.get('VODAFONE_ENABLED', '0') == '1',
            utc_offset=int(os.environ.get('VODAFONE_UTC_OFFSET', '3')))
        self.sms_server = None
        if self.cash.enabled or os.environ.get('SMS_BRIDGE_ENABLED', '0') == '1':
            self.sms_server = make_sms_server(self.cash, os.environ.get('SMS_BRIDGE_HOST', '127.0.0.1'), int(os.environ.get('SMS_BRIDGE_PORT', '8091')))
            threading.Thread(target=self.sms_server.serve_forever, daemon=True).start()
        self.api_server = None
        if os.environ.get('API_ENABLED', '0') == '1':
            self.api_server = make_server(self.stores, os.environ.get('API_HOST', '127.0.0.1'), int(os.environ.get('API_PORT', '8080')))
            threading.Thread(target=self.api_server.serve_forever, daemon=True).start()

    def cash_available(self, user):
        pilot = os.environ.get('VODAFONE_TEST_ONLY', '1') == '1'
        return self.cash.ready() and (not pilot or user == self.owner)

    def background_tasks(self):
        for row in self.cash.pending_notifications():
            self.send(row['customer'], self.t(row['customer'], 'cash_paid', amount=display(row['amount']), transaction=row['transaction_id']))
            self.cash.notified(row['id'])

    def transport(self, base, key, endpoint, body, identity, supplier):
        url = base.rstrip('/') + '/api/v2/telegram-buyer/' + endpoint
        headers = {'Content-Type': 'application/json'}
        data = None
        if body is None:
            url += '?' + urlencode({'key': key})
        else:
            data = json.dumps({'key': key, **body}).encode()
            headers['Idempotency-Key'] = identity
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=40) as response:
                result = json.load(response)
        except HTTPError as exc:
            if exc.code == 429:
                try:
                    delay = max(1, int(exc.headers.get('Retry-After', '60')))
                except ValueError:
                    delay = 60
                for store in self.stores.values():
                    store.cooldown(supplier, delay)
            if exc.code in (400, 401, 403, 404):
                try:
                    failure = json.load(exc)
                except (ValueError, OSError):
                    failure = {}
                if isinstance(failure, dict) and failure.get('success') is False:
                    raise SupplierRejected('المورد رفض العملية.') from None
            raise StoreError('تعذر تنفيذ طلب المورد. أعد المحاولة لاحقًا بنفس العملية.') from None
        except (URLError, TimeoutError, ValueError):
            raise StoreError('تعذر تأكيد رد المورد.') from None
        if isinstance(result, dict) and result.get('success') is False:
            raise SupplierRejected('المورد رفض العملية.')
        if not isinstance(result, dict) or result.get('success') is not True:
            raise StoreError('المورد لم يؤكد نجاح الطلب.')
        return result

    def selected(self, user):
        row = self.db.execute('SELECT currency FROM preferences WHERE customer=?', (user,)).fetchone()
        return self.stores[row[0] if row else 'EGP']

    def all_products(self):
        return sorted((product for store in self.stores.values() for product in store.catalog()), key=lambda p: (p['name'].casefold(), p['currency']))

    def language(self, user):
        row = self.db.execute('SELECT language FROM customer_language WHERE customer=?', (user,)).fetchone()
        return row[0] if row else None

    def t(self, customer_id, message_key, **values):
        return translate(self.language(customer_id) or 'ar', message_key, **values)

    def set_language(self, user, language):
        if language not in ('ar', 'en'):
            raise StoreError('لغة غير مدعومة.')
        currency = 'EGP' if language == 'ar' else 'USD'
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO customer_language VALUES (?,?)', (user, language))
            self.db.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)', (user, currency))

    def language_prompt(self, chat):
        name = self.option('STORE_NAME', 'NF STORE')
        self.menu_message(chat, f'🛍️ {name}\n\nأهلًا بك في متجرنا 👋\nاختر لغتك للمتابعة.\n\nWelcome to our store 👋\nChoose your language to continue.', {'inline_keyboard': [[{'text': '🇪🇬 العربية', 'callback_data': 'lang:ar'}, {'text': '🇬🇧 English', 'callback_data': 'lang:en'}]]})

    def support_links(self, user):
        rows = []
        username = self.option('SUPPORT_USERNAME').strip().lstrip('@')
        phone = self.option('SUPPORT_WHATSAPP').strip().lstrip('+')
        if re.fullmatch(r'[A-Za-z0-9_]{5,32}', username):
            rows.append([{'text': self.t(user, 'telegram_support'), 'url': 'https://t.me/' + username}])
        if re.fullmatch(r'[1-9][0-9]{7,14}', phone):
            rows.append([{'text': self.t(user, 'whatsapp_support'), 'url': 'https://wa.me/' + phone}])
        return {'inline_keyboard': rows} if rows else None

    def canonical_text(self, text):
        for key, canonical in (('products', '🛍 Products'), ('free_services', '🎁 Free services'), ('support', '💬 Support'), ('wallet', '👛 Wallet'), ('api', '🔗 API'), ('warranty', '🛡 Warranty'), ('orders', '📦 Orders'), ('currency', '💱 Currency'), ('language', '🌐 Language')):
            if text in TEXT[key]:
                return canonical
        return text

    @staticmethod
    def order_delivery_url(order):
        delivery = order.get('delivery')
        if order.get('state') != 'completed' or not isinstance(delivery, str):
            return None
        delivery = delivery.strip()
        if not delivery or any(char.isspace() for char in delivery):
            return None
        try:
            parsed = urlsplit(delivery)
            return delivery if parsed.scheme in ('http', 'https') and parsed.hostname else None
        except ValueError:
            return None

    def order_text(self, user, order):
        state = self.t(user, order['state']) if order['state'] in TEXT else order['state']
        text = self.t(user, 'order', id=order['id'], state=state, amount=order['amount'], currency=order['currency'])
        if order.get('product_name'):
            text = '🛍 ' + order['product_name'] + '\n\n' + text
        if order.get('delivery'):
            delivery = order['delivery']
            if not isinstance(delivery, str):
                delivery = json.dumps(delivery, ensure_ascii=False, indent=2)
            text += '\n\n' + self.t(user, 'order_delivery') + ':\n' + (self.t(user, 'activation_hint') if self.order_delivery_url(order) else delivery)
        if order.get('message'):
            text += '\n\n' + self.t(user, 'order_message') + ': ' + error_text(self.language(user), order['message'], preserve=True)
        return text

    def home(self, chat, user):
        sections = (
            ('products',),
            ('free_services',),
            ('wallet', 'orders'),
            ('support', 'warranty'),
            ('currency', 'language'),
            ('api',),
        )
        rows = [[{'text': self.t(user, key)} for key in row] for row in sections]
        if user == self.owner:
            rows.append([{'text': '⚙️ لوحة الإدارة'}])
        self.menu_message(chat, self.t(user, 'welcome', store=self.option('STORE_NAME', 'NF STORE'), currency=self.selected(user).currency, user=user), {
            'keyboard': rows,
            'resize_keyboard': True,
            'input_field_placeholder': self.t(user, 'menu_hint'),
        })

    def catalog_message(self, chat, text, markup, callback=None):
        try:
            return self.menu_message(chat, text, markup)
        except ApiError as exc:
            if exc.code != 400 or not any('icon_custom_emoji_id' in button for row in markup['inline_keyboard'] for button in row):
                raise
            return self.menu_message(chat, text, plain_buttons(markup))

    def product_message(self, chat, product, text, markup, callback=None):
        image = product.get('image')
        if not image:
            self.catalog_message(chat, text, markup, callback)
            return
        # Telegram captions count UTF-16 units, including two units for many emoji.
        if len(text.encode('utf-16-le')) > 2000:
            stock = str(product['stock']) if product['stock'] is not None else self.t(chat, 'availability')
            price = self.t(chat, 'free_label') if product.get('is_free') else f"{product['price']} {product['currency']}"
            header = f"🛍 {product['name']}\n\n💵 {self.t(chat, 'price_label')}: {price}\n📦 {self.t(chat, 'stock_label')}: {stock}\n\n"
            remaining = max(0, 1980 - len(header.encode('utf-16-le')))
            text = header + product['description'].encode('utf-16-le')[:remaining - remaining % 2].decode('utf-16-le', errors='ignore') + '…'
        old = self.current_menu(chat)
        if old:
            try:
                self.tg('editMessageMedia', chat_id=chat, message_id=old[0],
                        media={'type': 'photo', 'media': image, 'caption': text}, reply_markup=markup)
                self.remember_menu(chat, {'message_id': old[0]}, 'photo')
                return
            except ApiError as exc:
                if exc.not_modified:
                    return
                if exc.code != 400:
                    raise
        try:
            result = self.tg('sendPhoto', chat_id=chat, photo=image, caption=text, reply_markup=markup)
            self.remember_menu(chat, result, 'photo')
        except ApiError as exc:
            if exc.code != 400:
                raise
            # Broken upstream images must never prevent browsing or purchasing.
            self.catalog_message(chat, text, markup, callback)

    def notify(self, chat, text, markup=None):
        if text.startswith('{'):
            try:
                order = json.loads(text)
                if all(key in order for key in ('id', 'state', 'amount', 'currency')):
                    text = self.order_text(chat, order)
                    link = self.order_delivery_url(order)
                    if link:
                        markup = {'inline_keyboard': [[{'text': self.t(chat, 'activate_link'), 'url': link}]]}
            except (ValueError, TypeError):
                pass
        try:
            self.send(chat, text, markup)
        except ApiError:
            pass  # Approval/delivery remains persisted even when notification fails.

    def handle(self, update):
        try:
            self.dispatch(update)
        except BinanceError as exc:
            msg = update.get('message') or update.get('callback_query', {}).get('message', {})
            if msg.get('chat', {}).get('type') == 'private':
                self.send(msg['chat']['id'], self.t(msg['chat']['id'], 'bn_' + exc.kind))
        except (StoreError, ApiError, ValueError, KeyError, TypeError, IndexError) as exc:
            msg = update.get('message') or update.get('callback_query', {}).get('message', {})
            if msg.get('chat', {}).get('type') == 'private':
                user = (update.get('callback_query') or msg).get('from', {}).get('id', msg['chat']['id'])
                text = error_text(self.language(user), str(exc)) if isinstance(exc, (StoreError, ApiError)) else self.t(user, 'invalid')
                self.send(msg['chat']['id'], text)

    def dispatch(self, update):
        callback = update.get('callback_query')
        msg = callback.get('message', {}) if callback else update.get('message', {})
        user = (callback or msg).get('from', {}).get('id')
        if msg.get('chat', {}).get('type') != 'private' or not user:
            return
        chat = msg['chat']['id']
        text = msg.get('text', '') or msg.get('caption', '')
        action = callback.get('data', '') if callback else ''
        if callback:
            try:
                self.tg('answerCallbackQuery', callback_query_id=callback['id'])
            except ApiError as exc:
                if getattr(exc, 'code', None) != 400:
                    raise
        if action.startswith('section:'):
            sections = {'products': '🛍 Products', 'free_services': '🎁 Free services', 'wallet': '👛 Wallet', 'support': '💬 Support',
                        'api': '🔗 API', 'warranty': '🛡 Warranty', 'orders': '📦 Orders',
                        'currency': '💱 Currency', 'language': '🌐 Language'}
            text = sections[action.split(':', 1)[1]]
            action = ''
        if action.startswith('lang:'):
            self.clear_customer_form(user)
            self.set_language(user, action.split(':', 1)[1])
            if user == self.owner:
                self.clear_form()
            self.home(chat, user)
            return
        text = self.canonical_text(text)
        if text in ('/language', '🌐 Language') or not self.language(user):
            self.clear_customer_form(user)
            if user == self.owner:
                self.clear_form()
            self.language_prompt(chat)
            return
        store = self.selected(user)
        store.customer(user)
        navigation = ('/start', '/admin', '⚙️ لوحة الإدارة', '🛍 Products', '🎁 Free services', '💬 Support', '👛 Wallet', '🔗 API', '🛡 Warranty', '📦 Orders', '💱 Currency')
        if text in navigation or text.startswith(('/topup', '/claim')) or action.startswith(('adm:', 'currency:')):
            self.clear_customer_form(user)
        if self.handle_customer_flow(user, chat, text, action, msg):
            return
        if self.handle_admin(user, chat, text, action, msg):
            return
        if action.startswith('currency:'):
            currency = action.split(':')[1]
            if currency not in self.stores:
                raise StoreError('عملة غير مدعومة.')
            self.db.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)', (user, currency))
            self.db.commit()
            self.menu_message(chat, self.t(user, 'currency_selected', currency=currency))
        elif action.startswith('view:'):
            _, currency, identity, page = action.split(':', 3)
            product = next((p for p in self.stores[currency].catalog() if p['id'] == identity), None)
            if not product:
                self.send(chat, self.t(user, 'unavailable'))
                return
            stock = str(product['stock']) if product['stock'] is not None else self.t(user, 'availability')
            mode = 'free' if product.get('is_free') else 'all'
            buy = {'text': self.t(user, 'free_get' if product.get('is_free') else 'buy'), 'callback_data': f'pick:{currency}:{identity}'} if product.get('purchasable', True) else {'text': self.t(user, 'inquire'), 'callback_data': f'inquire:{currency}:{identity}'}
            if product['stock'] == 0:
                buy = {'text': self.t(user, 'out_of_stock'), 'callback_data': f'page:{mode}:' + str(max(0, int(page)))}
            delivery = self.t(user, 'manual' if product['delivery'] == 'manual' else 'automatic' if product.get('purchasable', True) else 'contact')
            description = product['description'].strip()
            text = f"🛍 {product['name']}\n\n"
            if description:
                text += description + '\n\n'
            price_label = self.t(user, 'free_label') if product.get('is_free') else f"{product['price']} {currency}"
            text += f"💵 {self.t(user, 'price_label')}: {price_label}\n📦 {self.t(user, 'stock_label')}: {stock}\n🚚 {self.t(user, 'delivery_label')}: {delivery}"
            markup = {'inline_keyboard': [[buy],
                [{'text': self.t(user, 'wallet'), 'callback_data': 'section:wallet'}, {'text': self.t(user, 'support'), 'callback_data': 'section:support'}],
                [{'text': self.t(user, 'back_free' if mode == 'free' else 'back_products'), 'callback_data': f'page:{mode}:{max(0, int(page))}'}]]}
            self.product_message(chat, product, text, markup, callback)
        elif action.startswith('pick:'):
            _, currency, product = action.split(':', 2)
            store = self.stores[currency]
            identity = store.quote(user, product)
            item = next(p for p in store.catalog() if p['id'] == product)
            self.menu_message(chat, self.t(user, 'free_confirm' if item.get('is_free') else 'confirm', name=item['name'], price=item['price'], currency=currency), {'inline_keyboard': [[{'text': self.t(user, 'free_get' if item.get('is_free') else 'pay'), 'callback_data': f'pay:{currency}:{identity}'}], [{'text': self.t(user, 'cancel'), 'callback_data': f'cancelquote:{currency}:{identity}'}]]})
        elif action.startswith('pay:'):
            _, currency, identity = action.split(':', 2)
            store = self.stores[currency]
            with store.lock:
                row = store.db.execute('SELECT product,state FROM orders WHERE customer=? AND idem=?', (user, identity)).fetchone()
            if not row:
                raise StoreError('الطلب غير موجود.')
            result = store.purchase(user, row['product'], identity)
            self.send_order(chat, user, result)
            if result['state'] == 'waiting_admin' and row['state'] != 'waiting_admin':
                self.notify(self.owner, f"📦 طلب جديد بانتظار التسليم\n\n👤 العميل: {user}\n💱 العملة: {currency}\n\n🧾 رقم الطلب:\n{result['id']}\n\nللتسليم من لوحة الإدارة، افتح «الطلبات والتسليم».\nأو استخدم:\n/deliver {currency} {result['id']} بيانات التسليم")
        elif action.startswith(('approve:', 'reject:')):
            if user != self.owner:
                raise StoreError('للأدمن فقط.')
            decision, currency, identity = action.split(':', 2)
            result = self.stores[currency].decide_topup(identity, decision == 'approve')
            self.send(chat, '👛 تحديث طلب الشحن\n\n📌 الحالة: ' + self.t(user, result['state']))
            recipient = result['customer']
            if result['changed']:
                self.notify(recipient, self.t(recipient, 'topup_decision', id=identity, state=self.t(recipient, result['state']), amount=display(result['amount']), currency=currency))
        elif text.startswith('/topup '):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                self.send(chat, self.t(user, 'topup_help'))
                return
            proof = parts[2] if len(parts) > 2 else ''
            if msg.get('photo'):
                proof = 'photo:' + msg['photo'][-1]['file_id'] + '\n' + proof
            identity = store.topup(user, parts[1], proof, f"tg{chat}m{msg['message_id']}")
            self.record_message(chat, self.t(user, 'topup_received', id=identity))
            self.announce_topup(user, store.currency, identity)
        elif text.startswith('/claim '):
            _, identity, reason = text.split(maxsplit=2)
            for wallet in self.stores.values():
                with wallet.lock:
                    owned = wallet.db.execute('SELECT 1 FROM orders WHERE id=? AND customer=?', (identity, user)).fetchone()
                if owned:
                    store = wallet
                    break
            ticket = store.ticket(user, identity, reason)
            self.record_message(chat, self.t(user, 'claim_received', id=ticket))
            self.notify(self.owner, f'طلب ضمان {store.currency}: {ticket}\nطلب: {identity}\nعميل: {user}\n{reason}')
        elif user == self.owner and self.admin(chat, text):
            return
        elif text in ('🛍 Products', '🎁 Free services') or action.startswith('page:'):
            mode = 'free' if text == '🎁 Free services' else 'all'
            if action.startswith('page:'):
                mode = 'free' if action.split(':')[1] == 'free' else 'all'
                offset = max(0, int(action.split(':')[-1]))
            else:
                offset = 0
            products = [p for p in self.all_products() if bool(p.get('is_free')) == (mode == 'free')]
            if not products:
                self.menu_message(chat, self.t(user, 'no_free_services' if mode == 'free' else 'no_products'), {'inline_keyboard': [
                    [{'text': self.t(user, 'support'), 'callback_data': 'section:support'}],
                    [{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
                ]})
                return
            page_size = 8
            offset = min(offset, ((len(products) - 1) // page_size) * page_size)
            tiles = []
            for product in products[offset:offset + page_size]:
                name = product['name']
                price = ' | ' + (self.t(user, 'free_label') if product.get('is_free') else f"{product['price']} {product['currency']}")
                name_limit = max(12, 90 - len(price))
                label = (name if len(name) <= name_limit else name[:name_limit - 1] + '…') + price
                custom_icon, fallback = icon_for(product)
                button = {'text': label, 'callback_data': f"view:{product['currency']}:{product['id']}:{offset}"}
                if product.get('stock') == 0:
                    button['text'] = '❌ ' + label
                elif custom_icon and self.option('CUSTOM_BUTTON_ICONS', '1') == '1':
                    button['icon_custom_emoji_id'] = custom_icon
                else:
                    button['text'] = fallback + ' ' + label
                tiles.append(button)
            rows = [[tile] for tile in tiles]
            navigation = []
            if offset > 0:
                navigation.append({'text': self.t(user, 'previous'), 'callback_data': f'page:{mode}:{max(0, offset - page_size)}'})
            if len(products) > offset + page_size:
                navigation.append({'text': self.t(user, 'next'), 'callback_data': f'page:{mode}:{offset + page_size}'})
            if navigation:
                rows.append(navigation)
            rows.append([{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}])
            page_number = offset // page_size + 1
            total_pages = (len(products) + page_size - 1) // page_size
            self.catalog_message(chat, self.t(user, 'free_catalog' if mode == 'free' else 'catalog', page=page_number, total=total_pages, count=len(products)), {'inline_keyboard': rows}, callback)
        elif action.startswith('inquire:'):
            _, currency, identity = action.split(':', 2)
            product = next((p for p in self.stores[currency].catalog() if p['id'] == identity), None)
            if not product:
                raise StoreError('المنتج غير متاح.')
            support = self.option('SUPPORT_USERNAME').lstrip('@')
            contact = self.t(user, 'contact_user', username=support) if support else self.t(user, 'contact_admin')
            self.menu_message(chat, self.t(user, 'inquiry', name=product['name'], support=contact), self.support_links(user))
        elif text == '👛 Wallet':
            balances = [f"{'🇪🇬' if s.currency == 'EGP' else '💵'} {s.balance(user)['balance']} {s.currency}" for s in self.stores.values()]
            markup = {'inline_keyboard': [
                [{'text': self.t(user, 'charge'), 'callback_data': 'charge'}],
                [{'text': self.t(user, 'orders'), 'callback_data': 'myorders:0'}, {'text': self.t(user, 'currency'), 'callback_data': 'walletcurrency'}],
                [{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
            ]}
            self.menu_message(chat, self.t(user, 'wallet_text', balances='\n'.join(balances), currency=store.currency), markup)
            pending = []
            for wallet in self.stores.values():
                with wallet.lock:
                    rows = wallet.db.execute("SELECT id,amount FROM topups WHERE customer=? AND state='pending' LIMIT 5", (user,)).fetchall()
                pending += [display(row['amount']) + ' ' + wallet.currency + ' · ' + row['id'][:8] for row in rows]
            if pending:
                self.send(chat, self.t(user, 'topup_pending', requests='\n'.join(pending)))
        elif text == '💱 Currency' or action == 'walletcurrency':
            self.menu_message(chat, self.t(user, 'currency_prompt'), {'inline_keyboard': [
                [{'text': self.t(user, 'egp'), 'callback_data': 'currency:EGP'}, {'text': self.t(user, 'usd'), 'callback_data': 'currency:USD'}],
                [{'text': self.t(user, 'wallet'), 'callback_data': 'section:wallet'}, {'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
            ]})
        elif text == '📦 Orders':
            self.show_orders(chat, user)
        elif text == '🔗 API':
            self.menu_message(chat, self.t(user, 'api_prompt', currency=store.currency), {'inline_keyboard': [
                [{'text': self.t(user, 'newkey'), 'callback_data': 'newkey'}],
                [{'text': self.t(user, 'wallet'), 'callback_data': 'section:wallet'}, {'text': self.t(user, 'support'), 'callback_data': 'section:support'}],
                [{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
            ]})
        elif text == '🛡 Warranty':
            self.menu_message(chat, self.t(user, 'claim_choose'), {'inline_keyboard': [
                [{'text': self.t(user, 'orders'), 'callback_data': 'myorders:0'}],
                [{'text': self.t(user, 'support'), 'callback_data': 'section:support'}],
                [{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
            ]})
        elif text == '💬 Support':
            username = self.option('SUPPORT_USERNAME').lstrip('@')
            phone = self.option('SUPPORT_WHATSAPP')
            contacts = []
            if username:
                contacts.append('✈️ Telegram: @' + username)
            if phone:
                contacts.append('💬 WhatsApp: +' + phone.lstrip('+'))
            text = self.t(user, 'support_intro', store=self.option('STORE_NAME', 'NF STORE'), contacts='\n'.join(contacts)) if contacts else self.t(user, 'no_support')
            markup = self.support_links(user) or {'inline_keyboard': []}
            markup['inline_keyboard'].append([{'text': self.t(user, 'orders'), 'callback_data': 'myorders:0'}])
            markup['inline_keyboard'].append([{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}])
            self.menu_message(chat, text, markup)
        else:
            self.home(chat, user)

    @staticmethod
    def topup_buttons(currency, identity):
        return {'inline_keyboard': [[{'text': '✅ موافقة', 'callback_data': f'approve:{currency}:{identity}'}, {'text': '❌ رفض', 'callback_data': f'reject:{currency}:{identity}'}]]}

    def admin(self, chat, text):
        command = text.split(maxsplit=1)[0] if text else ''
        if command == '/admin':
            self.send(chat, '''أوامر الإدارة (EGP أو USD):
/product EGP {"name":"اسم","source":"local","cost":"100","fixed":"10","percent":"5"}
source=local تسليم مخزون؛ source=manual تسليم يدوي. price بديل لتحديد سعر بيع مباشر.
/stock EGP product_id بيانات قطعة واحدة
/supplier USD supplierName {"adapter":"canboso","base_url":"https://canboso.com","key_env":"SUPPLIER_API_KEY"}
/sync USD supplierName 10 0.5
آخر رقمين: نسبة ربح ثم ربح ثابت. المزامنة تستورد المنتجات المدعومة بنفس العملة فقط.
/pending EGP
/queue EGP
/deliver EGP order_id بيانات التسليم
/refund EGP order_id سبب الرد (للطلبات اليدوية المنتظرة فقط)
/hide EGP product_id
/tickets EGP
الأرصدة بالجنيه والدولار منفصلة. /admin يعرض الأوامر.''')
            return True
        supported = ('/product', '/stock', '/supplier', '/sync', '/pending', '/queue', '/deliver', '/refund', '/hide', '/tickets')
        if command not in supported:
            return False
        parts = text.split(maxsplit=2)
        store = self.stores[parts[1]]
        rest = parts[2] if len(parts) > 2 else ''
        if command == '/product':
            identity = store.add_product(json.loads(rest))
            self.send(chat, '✅ تمت إضافة المنتج\n\n🆔 معرّف المنتج:\n' + identity)
        elif command == '/stock':
            identity, payload = rest.split(maxsplit=1)
            store.add_stock(identity, payload)
            self.send(chat, '✅ تمت إضافة قطعة جديدة إلى المخزون.')
        elif command == '/supplier':
            identity, config = rest.split(maxsplit=1)
            store.add_supplier(identity, json.loads(config))
            self.send(chat, '✅ تم حفظ إعدادات المورد\n\n🔑 أضف مفتاحه إلى متغير البيئة المحدد، ثم أعد تشغيل البوت.')
        elif command == '/sync':
            identity, percent, fixed = rest.split()
            count = store.sync(identity, fixed, percent)
            self.send(chat, '✅ اكتملت مزامنة المورد\n\n📦 عدد المنتجات المحدّثة: ' + str(count))
        elif command == '/pending':
            rows = store.pending_topups()
            self.send(chat, '⏳ طلبات شحن قيد المراجعة\n\n🔢 العدد: ' + str(len(rows)))
            for row in rows:
                self.send(chat, f"{row['id']}\nعميل: {row['customer']}\n{display(row['amount'])} {store.currency}\n{row['proof']}", self.topup_buttons(store.currency, row['id']))
                if row['proof'].startswith('photo:'):
                    self.tg('sendPhoto', chat_id=chat, photo=row['proof'].splitlines()[0][6:])
        elif command == '/queue':
            with store.lock:
                rows = [dict(r) for r in store.db.execute("SELECT id,customer,product,state FROM orders WHERE state IN ('waiting_admin','uncertain','processing','supplier_pending') LIMIT 30")]
            self.send(chat, json.dumps(rows, ensure_ascii=False, indent=2))
        elif command == '/deliver':
            identity, payload = rest.split(maxsplit=1)
            customer = store.fulfill(identity, payload)
            self.send(chat, '✅ تم تسليم الطلب وتحديث حالته.')
            self.notify(customer, json.dumps(store.order(customer, identity), ensure_ascii=False, indent=2))
        elif command == '/refund':
            identity, reason = rest.split(maxsplit=1)
            # Admin cannot refund ambiguous supplier charges through this command.
            with store.lock:
                row = store.db.execute('SELECT state FROM orders WHERE id=?', (identity,)).fetchone()
            if not row or row['state'] != 'waiting_admin':
                raise StoreError('الأمر متاح للطلب اليدوي المنتظر فقط.')
            result = store.refund(identity, reason, manual_only=True)
            self.send(chat, json.dumps(result, ensure_ascii=False, indent=2))
        elif command == '/hide':
            store.set_visible(rest, False)
            self.send(chat, '✅ تم إخفاء المنتج من قائمة العملاء.')
        elif command == '/tickets':
            with store.lock:
                rows = [dict(r) for r in store.db.execute("SELECT * FROM tickets WHERE state='open' LIMIT 30")]
            self.send(chat, json.dumps(rows, ensure_ascii=False, indent=2))
        return True
