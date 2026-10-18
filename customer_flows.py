"""Persistent customer forms: top-up, warranty, API-key confirmation and orders."""
import json
import re
import uuid

from store import StoreError, display, money
from binance_pay import BinanceError


class CustomerFlows:
    def init_customer_flows(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS customer_form(customer INTEGER PRIMARY KEY,value TEXT NOT NULL)')
        self.db.commit()

    def customer_form(self, user):
        row = self.db.execute('SELECT value FROM customer_form WHERE customer=?', (user,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_customer_form(self, user, form):
        self.db.execute('INSERT OR REPLACE INTO customer_form VALUES (?,?)', (user, json.dumps(form)))
        self.db.commit()

    def clear_customer_form(self, user):
        self.db.execute('DELETE FROM customer_form WHERE customer=?', (user,))
        self.db.commit()

    def cancel_markup(self, user):
        return {'inline_keyboard': [[{'text': self.t(user, 'cancel'), 'callback_data': 'customer:cancel'}]]}

    def payment_text(self, user):
        text = self.option('MANUAL_PAYMENT_DETAILS_EN') if self.language(user) == 'en' else ''
        return text or self.option('MANUAL_PAYMENT_DETAILS', self.t(user, 'no_payment'))

    def send_order(self, chat, user, order):
        currency, identity = order['currency'], order['id']
        rows = [[{'text': self.t(user, 'refresh'), 'callback_data': f'order:{currency}:{identity}'}]]
        link = self.order_delivery_url(order)
        if link:
            rows.insert(0, [{'text': self.t(user, 'activate_link'), 'url': link}])
        if order['state'] == 'completed':
            rows.append([{'text': self.t(user, 'claim_button'), 'callback_data': f'claim:{currency}:{identity}'}])
        if order['state'] in ('reserved', 'processing', 'uncertain'):
            rows.append([{'text': self.t(user, 'retry'), 'callback_data': f'retry:{currency}:{identity}'}])
        rows.append([{'text': self.t(user, 'copy_order'), 'copy_text': {'text': identity}}])
        rows.append([{'text': self.t(user, 'back_orders'), 'callback_data': 'myorders:0'}])
        rows.append([{'text': self.t(user, 'support'), 'callback_data': 'section:support'}, {'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}])
        self.record_message(chat, self.order_text(user, order), {'inline_keyboard': rows})

    def show_orders(self, chat, user, offset=0):
        orders = sorted((order for store in self.stores.values() for order in store.orders(user)), key=lambda order: order['created_at'], reverse=True)
        if not orders:
            self.menu_message(chat, self.t(user, 'no_orders'), {'inline_keyboard': [
                [{'text': self.t(user, 'products'), 'callback_data': 'section:products'}],
                [{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
            ]})
            return
        size = 6
        offset = min(max(0, offset), ((len(orders) - 1) // size) * size)
        rows = []
        for order in orders[offset:offset + size]:
            label = order.get('product_name') or order['id'][:10]
            rows.append([{'text': f"{label[:38]} · {order['amount']} {order['currency']}", 'callback_data': f"order:{order['currency']}:{order['id']}"}])
        navigation = []
        if offset:
            navigation.append({'text': self.t(user, 'previous'), 'callback_data': f'myorders:{offset-size}'})
        if len(orders) > offset + size:
            navigation.append({'text': self.t(user, 'next'), 'callback_data': f'myorders:{offset+size}'})
        if navigation:
            rows.append(navigation)
        rows.append([{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}])
        self.catalog_message(chat, self.t(user, 'orders_page', page=offset // size + 1, total=(len(orders) + size - 1) // size), {'inline_keyboard': rows})

    def announce_topup(self, user, currency, identity):
        store = self.stores[currency]
        with store.lock:
            row = store.db.execute('SELECT * FROM topups WHERE id=? AND customer=?', (identity, user)).fetchone()
        if not row:
            raise StoreError('طلب الشحن غير موجود.')
        self.notify(self.owner, f"💳 طلب شحن بانتظار المراجعة\n\n👤 العميل: {user}\n💰 المبلغ: {display(row['amount'])} {currency}\n\n🧾 رقم الطلب:\n{identity}\n\n📎 إثبات التحويل:\n{row['proof']}", self.topup_buttons(currency, identity))
        if row['proof'].startswith('photo:'):
            try:
                self.tg('sendPhoto', chat_id=self.owner, photo=row['proof'].splitlines()[0][6:], caption=identity)
            except Exception:
                pass  # Receipt remains available through the owner pending-deposits screen.

    def handle_customer_flow(self, user, chat, text, action, message):
        form = self.customer_form(user)
        if action == 'binance':
            currencies = self.binance.currencies()
            if not currencies:
                raise BinanceError('disabled')
            rows = [[{'text': self.t(user, 'egp' if currency == 'EGP' else 'usd'), 'callback_data': 'bnwallet:' + currency}] for currency in currencies]
            rows.append([{'text': self.t(user, 'cancel'), 'callback_data': 'customer:cancel'}])
            self.clear_customer_form(user)
            rates = '\n'.join(f"1 USDT = {self.binance.rate(currency)} {currency}" for currency in currencies)
            self.menu_message(chat, self.t(user, 'bn_wallet', rates=rates), {'inline_keyboard': rows})
            return True
        if action.startswith('bnwallet:'):
            currency = action.split(':')[1]
            if currency not in self.binance.currencies():
                raise BinanceError('disabled')
            self.save_customer_form(user, {'kind': 'bn_amount', 'currency': currency})
            self.menu_message(chat, self.t(user, 'bn_amount_prompt', rate=str(self.binance.rate(currency)), currency=currency), {'inline_keyboard': [
                [{'text': self.t(user, 'bn_change_wallet'), 'callback_data': 'binance'}],
                [{'text': self.t(user, 'cancel'), 'callback_data': 'customer:cancel'}],
            ]})
            return True
        if action.startswith('bnenter:'):
            identity = action.split(':')[1]
            self.binance.request(user, identity)
            self.save_customer_form(user, {'kind': 'bn_transaction', 'request': identity})
            self.menu_message(chat, self.t(user, 'bn_tx_prompt'), self.cancel_markup(user))
            return True
        if action.startswith('bncheck:'):
            identity = action.split(':')[1]
            self.check_binance(chat, user, identity, self.binance.submitted_transaction(user, identity))
            return True
        if text == '/cancel' or action == 'customer:cancel':
            self.clear_customer_form(user)
            if user == self.owner:
                self.clear_form()
            self.home(chat, user)
            return True
        if action == 'charge':
            self.clear_customer_form(user)
            methods = []
            if self.binance.currencies():
                methods.append([{'text': self.t(user, 'binance_payment'), 'callback_data': 'binance'}])
            if self.cash_available(user):
                methods.append([{'text': self.t(user, 'cash_payment'), 'callback_data': 'cashcharge'}])
            available = bool(methods)
            methods.append([{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}])
            self.menu_message(chat, self.t(user, 'payment_method' if available else 'payments_unavailable'), {'inline_keyboard': methods})
            return True
        if action == 'cashcharge':
            if not self.cash_available(user):
                self.menu_message(chat, self.t(user, 'cash_offline'))
                return True
            self.save_customer_form(user, {'kind': 'cash_amount'})
            self.menu_message(chat, self.t(user, 'cash_amount'), self.cancel_markup(user))
            return True
        if action == 'manualcharge':
            self.menu_message(chat, self.t(user, 'charge_currency'), {'inline_keyboard': [[{'text': self.t(user, 'egp'), 'callback_data': 'deposit:EGP'}, {'text': self.t(user, 'usd'), 'callback_data': 'deposit:USD'}], [{'text': self.t(user, 'cancel'), 'callback_data': 'customer:cancel'}]]})
            return True
        if action.startswith('deposit:'):
            currency = action.split(':')[1]
            if currency not in self.stores:
                raise StoreError('اختيار غير صالح.')
            self.save_customer_form(user, {'kind': 'deposit_amount', 'currency': currency, 'id': uuid.uuid4().hex})
            self.menu_message(chat, self.t(user, 'amount_prompt', currency=currency), self.cancel_markup(user))
            return True
        if action.startswith('submitdeposit:'):
            identity = action.split(':')[1]
            if not form or form['kind'] != 'deposit_confirm' or form['id'] != identity:
                self.menu_message(chat, self.t(user, 'expired_form'))
                return True
            store = self.stores[form['currency']]
            identity = store.topup(user, form['amount'], form['proof'], identity)
            self.clear_customer_form(user)
            self.record_message(chat, self.t(user, 'topup_received', id=identity))
            self.announce_topup(user, store.currency, identity)
            return True
        if action.startswith('order:'):
            _, currency, identity = action.split(':')
            self.send_order(chat, user, self.stores[currency].order(user, identity))
            return True
        if action.startswith('myorders:'):
            self.show_orders(chat, user, int(action.split(':')[1]))
            return True
        if action.startswith('claim:'):
            _, currency, identity = action.split(':')
            order = self.stores[currency].order(user, identity)
            if order['state'] != 'completed':
                raise StoreError('طلب الضمان غير صالح.')
            self.save_customer_form(user, {'kind': 'claim', 'currency': currency, 'order': identity})
            self.menu_message(chat, self.t(user, 'claim_prompt', id=identity), self.cancel_markup(user))
            return True
        if action.startswith('retry:'):
            _, currency, identity = action.split(':')
            store = self.stores[currency]
            with store.lock:
                row = store.db.execute('SELECT product,idem FROM orders WHERE id=? AND customer=?', (identity, user)).fetchone()
            if not row:
                raise StoreError('الطلب غير موجود.')
            result = store.purchase(user, row['product'], row['idem'])
            self.send_order(chat, user, result)
            return True
        if action == 'newkey':
            currency = self.selected(user).currency
            identity = uuid.uuid4().hex
            self.save_customer_form(user, {'kind': 'key_confirm', 'id': identity, 'currency': currency})
            self.menu_message(chat, self.t(user, 'key_confirm', currency=currency), {'inline_keyboard': [[{'text': self.t(user, 'key_generate'), 'callback_data': 'confirmkey:' + identity}], [{'text': self.t(user, 'cancel'), 'callback_data': 'customer:cancel'}]]})
            return True
        if action.startswith('confirmkey:'):
            if not form or form['kind'] != 'key_confirm' or form['id'] != action.split(':')[1]:
                self.menu_message(chat, self.t(user, 'expired_form'))
                return True
            currency = form['currency']
            key = self.stores[currency].rotate_key(user)
            self.clear_customer_form(user)
            self.record_message(chat, self.t(user, 'key', currency=currency, key=key, url=self.option('PUBLIC_API_URL') or self.t(user, 'no_api_url')))
            return True
        if action.startswith('cancelquote:'):
            _, currency, identity = action.split(':')
            self.stores[currency].cancel_quote(user, identity)
            self.home(chat, user)
            return True
        if action or not form or text.startswith('/'):
            return False
        if form['kind'] == 'cash_amount':
            if not re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,2})?', text.strip()) or not money('5') <= money(text.strip()) <= money('10000'):
                self.menu_message(chat, self.t(user, 'cash_amount'), self.cancel_markup(user))
                return True
            self.save_customer_form(user, {'kind': 'cash_payer', 'amount': text.strip()})
            self.menu_message(chat, self.t(user, 'cash_payer'), self.cancel_markup(user))
            return True
        if form['kind'] == 'cash_payer':
            payer = text.strip()
            if not re.fullmatch(r'01[0125][0-9]{8}', payer):
                self.menu_message(chat, self.t(user, 'cash_payer'), self.cancel_markup(user))
                return True
            if not self.cash_available(user):
                self.menu_message(chat, self.t(user, 'cash_offline'))
                return True
            quote = self.cash.quote(user, form['amount'], payer)
            self.clear_customer_form(user)
            self.record_message(chat, self.t(user, 'cash_quote', amount=quote['amount'], wallet=quote['wallet'], payer=payer, id=quote['id']), {'inline_keyboard': [
                [{'text': '📋 ' + quote['wallet'], 'copy_text': {'text': quote['wallet']}}],
                [{'text': self.t(user, 'bn_copy_amount', amount=quote['amount']), 'copy_text': {'text': quote['amount']}}],
                [{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
            ]})
            return True
        if form['kind'] == 'bn_amount':
            quote = self.binance.quote(user, form['currency'], text.strip())
            self.save_customer_form(user, {'kind': 'bn_transaction', 'request': quote['id']})
            amount = display(quote['amount'])
            self.record_message(chat, self.t(user, 'bn_quote', amount=amount, pay_id=quote['pay_id'], credit=display(quote['credit']), currency=quote['wallet'], rate=quote['rate'], id=quote['id']), {'inline_keyboard': [
                [{'text': '📋 ' + str(quote['pay_id']), 'copy_text': {'text': str(quote['pay_id'])}}],
                [{'text': self.t(user, 'bn_copy_amount', amount=amount), 'copy_text': {'text': amount}}],
                [{'text': self.t(user, 'bn_enter'), 'callback_data': 'bnenter:' + quote['id']}],
                [{'text': self.t(user, 'bn_change_wallet'), 'callback_data': 'binance'}],
                [{'text': self.t(user, 'home'), 'callback_data': 'customer:cancel'}],
            ]})
            return True
        if form['kind'] == 'bn_transaction':
            if not re.fullmatch(r'[0-9]{5,32}', text.strip()):
                raise BinanceError('transaction')
            self.check_binance(chat, user, form['request'], text.strip())
            return True
        if form['kind'] == 'deposit_amount':
            amount = money(text)
            if amount <= 0:
                raise StoreError('أرسل مبلغ موجب وإثبات تحويل.')
            form.update(kind='deposit_proof', amount=display(amount))
            self.save_customer_form(user, form)
            self.menu_message(chat, self.t(user, 'proof_prompt', amount=form['amount'], currency=form['currency'], payment=self.payment_text(user)), self.cancel_markup(user))
            return True
        if form['kind'] == 'deposit_proof':
            proof = text.strip()
            if message.get('photo'):
                proof = 'photo:' + message['photo'][-1]['file_id'] + ('\n' + proof if proof else '')
            if not proof or len(proof) > 2000:
                raise StoreError('أرسل مبلغ موجب وإثبات تحويل.')
            form.update(kind='deposit_confirm', proof=proof)
            self.save_customer_form(user, form)
            self.menu_message(chat, self.t(user, 'deposit_confirm', amount=form['amount'], currency=form['currency']), {'inline_keyboard': [[{'text': self.t(user, 'submit'), 'callback_data': 'submitdeposit:' + form['id']}], [{'text': self.t(user, 'cancel'), 'callback_data': 'customer:cancel'}]]})
            return True
        if form['kind'] == 'claim':
            store = self.stores[form['currency']]
            ticket = store.ticket(user, form['order'], text.strip())
            self.clear_customer_form(user)
            self.record_message(chat, self.t(user, 'claim_received', id=ticket))
            self.notify(self.owner, f"🛡 طلب ضمان جديد\n\n👤 العميل: {user}\n💱 العملة: {store.currency}\n\n🧾 رقم الطلب الأصلي:\n{form['order']}\n\n🛡 رقم طلب الضمان:\n{ticket}\n\n📝 وصف المشكلة:\n{text}")
            return True
        if form['kind'] in ('deposit_confirm', 'key_confirm'):
            self.menu_message(chat, self.t(user, 'expired_form'), self.cancel_markup(user))
            return True
        return False

    def check_binance(self, chat, user, identity, transaction):
        self.menu_message(chat, self.t(user, 'bn_checking'), {'inline_keyboard': [[{'text': self.t(user, 'bn_check'), 'callback_data': 'bncheck:' + identity}]]})
        result = self.binance.check(user, identity, transaction)
        self.clear_customer_form(user)
        reference = result.get('order_id') or result['transaction_id']
        self.record_message(chat, self.t(user, 'bn_paid', credit=display(result['credit']), currency=result['wallet'], id=identity, transaction=reference))
        if result['changed']:
            self.notify(self.owner, f"✅ تأكيد شحن Binance Pay\n\n👤 العميل: {user}\n💵 التحويل: {display(result['amount'])} USDT\n👛 الرصيد المضاف: {display(result['credit'])} {result['wallet']}\n\n🧾 رقم طلب الشحن:\n{identity}\n\n🔎 رقم التحويل (Order ID):\n{reference}")
