"""Persistent owner-only button menus and guided forms."""
import json
import os
import re

from store import StoreError, display, money
from binance_pay import BinanceError


def buttons(rows):
    return {'inline_keyboard': [[{'text': title, 'callback_data': data} for title, data in row] for row in rows]}


class AdminPanel:
    def init_admin(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS admin_form(customer INTEGER PRIMARY KEY, value TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS shop_options(name TEXT PRIMARY KEY,value TEXT NOT NULL)')
        self.db.commit()

    def option(self, name, default=''):
        row = self.db.execute('SELECT value FROM shop_options WHERE name=?', (name,)).fetchone()
        return row[0] if row else os.environ.get(name, '') or default

    def save_form(self, form):
        self.db.execute('INSERT OR REPLACE INTO admin_form VALUES (?,?)', (self.owner, json.dumps(form)))
        self.db.commit()

    def clear_form(self):
        self.db.execute('DELETE FROM admin_form WHERE customer=?', (self.owner,))
        self.db.commit()

    def admin_home(self, chat):
        self.clear_form()
        self.send(chat, '⚙️ لوحة إدارة NF STORE\n\nأهلًا بك في إدارة المتجر.\nاختر القسم المطلوب من الأزرار أدناه.', buttons([
            [('➕ إضافة منتج', 'adm:add'), ('📦 إدارة المنتجات والمخزون', 'adm:products:0')],
            [('🎁 إضافة خدمة مجانية', 'adm:addfree')],
            [('🔌 الموردون واستيراد المنتجات', 'adm:suppliers')],
            [('💳 طلبات الشحن', 'adm:topups'), ('🛒 الطلبات والتسليم', 'adm:orders')],
            [('📊 ملخص المتجر', 'adm:summary')],
            [('🛡 طلبات الضمان', 'adm:tickets'), ('⚙️ إعدادات المتجر', 'adm:settings')],
            [('🏠 القائمة الرئيسية', 'adm:exit')]]))

    def admin_items(self):
        items = []
        for currency, store in self.stores.items():
            with store.lock:
                for row in store.db.execute("SELECT p.*, EXISTS(SELECT 1 FROM meta WHERE name='hidden:' || p.id) AS hidden FROM products p ORDER BY name"):
                    is_free = bool(store.db.execute('SELECT 1 FROM free_services WHERE product=?', (row['id'],)).fetchone())
                    items.append({**dict(row), 'currency': currency, 'is_free': is_free})
        return items

    def admin_products(self, chat, page=0, stock_only=False):
        items = self.admin_items()
        if stock_only:
            items = [item for item in items if item['source'] == 'local']
        rows = []
        for item in items[page:page + 8]:
            flag = '🙈 ' if item['hidden'] or not item['active'] else ''
            if item.get('is_free'):
                flag += '🎁 '
            rows.append([(flag + item['name'][:40] + ' · ' + item['currency'], f"adm:item:{item['currency']}:{item['id']}")])
        navigation = []
        if page > 0:
            navigation.append(('⬅️ السابق', f'adm:products:{max(0, page - 8)}'))
        if len(items) > page + 8:
            navigation.append(('التالي ➡️', f'adm:products:{page + 8}'))
        if navigation:
            rows.append(navigation)
        rows.append([('➕ إضافة منتج', 'adm:add'), ('⬅️ لوحة الإدارة', 'adm:home')])
        self.send(chat, f'📦 إدارة المنتجات\n\n🔢 إجمالي المنتجات: {len(items)}\n\nاختر منتجًا لتعديل بياناته أو إضافة مخزون أو تغيير ظهوره للعملاء.', buttons(rows))

    def admin_item(self, chat, currency, identity):
        item = next((r for r in self.admin_items() if r['currency'] == currency and r['id'] == identity), None)
        if not item:
            raise StoreError('المنتج غير موجود.')
        store = self.stores[currency]
        with store.lock:
            stock = store.db.execute('SELECT count(*) FROM stock WHERE product=? AND order_id IS NULL', (identity,)).fetchone()[0]
        with store.lock:
            is_free = bool(store.db.execute('SELECT 1 FROM free_services WHERE product=?', (identity,)).fetchone())
        rows = [[('💵 تعديل السعر', f'adm:price:{currency}:{identity}')],
                [('✏️ تعديل الاسم', f'adm:name:{currency}:{identity}'), ('📝 تعديل الوصف', f'adm:description:{currency}:{identity}')],
                [('🖼 إضافة / تغيير الصورة', f'adm:image:{currency}:{identity}')],
                [('👁 إظهار' if item['hidden'] else '🙈 إخفاء', f"adm:visible:{currency}:{identity}:{int(bool(item['hidden']))}")]]
        if is_free:
            rows.pop(0)
        if item['source'] == 'local':
            rows.append([('➕ إضافة قطعة للمخزون', f'adm:stock:{currency}:{identity}')])
        rows.append([('⬅️ المنتجات', 'adm:products:0')])
        source_label = {'local': 'مخزون المتجر', 'manual': 'تسليم يدوي'}.get(item['source'], item['source'])
        price_label = 'مجاني' if is_free else f"{display(item['price'])} {currency}"
        text = f"🛍 {item['name']}\n\n💰 السعر: {price_label}\n🔌 المصدر: {source_label}\n\n🆔 معرّف المنتج:\n{identity}"
        if is_free:
            text = '🎁 خدمة مجانية\n\n' + text
        kind = store.delivery_format(identity)
        text += '\n\n🚚 نوع التسليم: ' + {'link': 'رابط', 'account': 'إيميل وكلمة مرور', 'manual': 'يدوي', 'text': 'بيانات نصية', 'supplier': 'المورد عبر API'}.get(kind, kind)
        if item['source'] == 'local':
            text += '\n\n📦 القطع المتاحة: ' + str(stock)
        self.send(chat, text, buttons(rows))

    def begin_form(self, chat, kind, prompt, **data):
        self.save_form({'kind': kind, **data})
        self.send(chat, prompt + '\n\n↩️ للإلغاء والعودة إلى القائمة: /cancel', buttons([[('❌ إلغاء', 'adm:home')]]))

    def handle_admin(self, user, chat, text, action, message=None):
        if user != self.owner:
            if action.startswith('adm:') or text in ('⚙️ لوحة الإدارة', '/admin'):
                raise StoreError('القسم ده للأدمن فقط.')
            return False
        if text in ('⚙️ لوحة الإدارة', '/admin', '/cancel') or action == 'adm:home':
            self.admin_home(chat)
            return True
        if text == '/start':
            self.clear_form()
            return False
        if action.startswith('adm:'):
            parts = action.split(':')
            cmd = parts[1]
            if cmd == 'exit':
                self.clear_form()
                self.home(chat, user)
            elif cmd == 'addfree':
                self.begin_form(chat, 'product_name', '🎁 إضافة خدمة مجانية\n\nأدخل اسم الخدمة.\nستختار بعدها رابطًا أو إيميل وباسورد أو تسليمًا يدويًا.', currency='EGP', is_free=True)
            elif cmd == 'add':
                self.clear_form()
                self.send(chat, '💱 عملة تسعير المنتج\n\nاختر العملة التي سيُعرض بها السعر.\nℹ️ سيظهر المنتج لجميع العملاء، بغض النظر عن المحفظة المختارة.', buttons([[('جنيه EGP', 'adm:newcurrency:EGP'), ('دولار USD', 'adm:newcurrency:USD')], [('⬅️ لوحة الإدارة', 'adm:home')]]))
            elif cmd == 'newcurrency':
                self.begin_form(chat, 'product_name', '🛍 اسم المنتج\n\nأدخل اسمًا واضحًا، بحد أقصى 180 حرفًا.', currency=parts[2])
            elif cmd == 'source':
                row = self.db.execute('SELECT value FROM admin_form WHERE customer=?', (self.owner,)).fetchone()
                form = json.loads(row[0]) if row else {}
                if form.get('kind') != 'product_source' or parts[2] not in ('link', 'account', 'local', 'manual'):
                    raise StoreError('ابدأ إضافة المنتج من جديد.')
                selected = parts[2]
                form.update(kind='product_price', source='manual' if selected == 'manual' else 'local',
                            delivery_format='text' if selected == 'local' else selected)
                if form.get('is_free'):
                    form.update(kind='product_description', price='0')
                    self.save_form(form)
                    self.send(chat, '📝 وصف الخدمة المجانية\n\nأدخل التفاصيل، أو أرسل - لتخطي الوصف.\nلن يُخصم أي رصيد عند طلب هذه الخدمة.')
                    return True
                self.save_form(form)
                self.send(chat, '💰 أدخل سعر البيع بعملة ' + form['currency'] + ':')
            elif cmd == 'confirmproduct':
                row = self.db.execute('SELECT value FROM admin_form WHERE customer=?', (self.owner,)).fetchone()
                form = json.loads(row[0]) if row else {}
                if form.get('kind') != 'product_confirm':
                    raise StoreError('النموذج انتهى أو تم حفظه بالفعل.')
                product = self.stores[form['currency']].add_product(form)
                self.clear_form()
                self.send(chat, '✅ تمت إضافة المنتج بنجاح.\n\nيمكنك الآن تعديل بياناته وإدارة المخزون من الأزرار أدناه.')
                self.admin_item(chat, form['currency'], product)
            elif cmd == 'products':
                self.clear_form()
                self.admin_products(chat, int(parts[2]))
            elif cmd == 'item':
                self.clear_form()
                self.admin_item(chat, parts[2], parts[3])
            elif cmd in ('price', 'stock', 'image', 'name', 'description'):
                if cmd == 'stock':
                    kind = self.stores[parts[2]].delivery_format(parts[3])
                    if kind == 'account':
                        self.begin_form(chat, 'stock_email', '📧 إضافة حساب للمخزون\n\nأرسل البريد الإلكتروني للحساب.\nسنطلب كلمة المرور في الخطوة التالية.', currency=parts[2], product=parts[3])
                        return True
                    if kind == 'link':
                        self.begin_form(chat, 'stock', '🔗 إضافة رابط للمخزون\n\nأرسل رابطًا واحدًا كاملًا يبدأ بـ https:// أو http://.\nسيتم تسليمه تلقائيًا لعميل واحد عند الشراء.', currency=parts[2], product=parts[3])
                        return True
                prompt = {'price': '💰 تعديل السعر\n\nأدخل سعر البيع الجديد بعملة المنتج.', 'stock': '📦 إضافة قطعة للمخزون\n\nأرسل بيانات التسليم الكاملة لقطعة واحدة في رسالة واحدة.\nℹ️ الرسالة كاملة تُسجّل كقطعة واحدة، حتى لو تضمنت عدة أسطر.', 'image': '🖼 صورة المنتج\n\nأرسل صورة عبر تلجرام أو رابط صورة مباشر يبدأ بـ https://.\nلإزالة الصورة الحالية، أرسل الرمز - فقط.', 'name': '✏️ تعديل اسم المنتج\n\nأدخل الاسم الجديد.', 'description': '📝 تعديل وصف المنتج\n\nأدخل الوصف الجديد.\nلإزالة الوصف، أرسل الرمز - فقط.'}[cmd]
                self.begin_form(chat, cmd, prompt, currency=parts[2], product=parts[3])
            elif cmd == 'visible':
                self.stores[parts[2]].set_visible(parts[3], parts[4] == '1')
                self.admin_item(chat, parts[2], parts[3])
            elif cmd == 'suppliers':
                self.clear_form()
                rows = []
                for currency, store in self.stores.items():
                    with store.lock:
                        suppliers = store.db.execute('SELECT id FROM suppliers ORDER BY id').fetchall()
                    for supplier in suppliers:
                        rows.append([(f"🔄 {supplier['id']} · {currency}", f"adm:sync:{currency}:{supplier['id']}")])
                rows += [[('➕ إضافة مورد', 'adm:addsupplier')], [('⬅️ لوحة الإدارة', 'adm:home')]]
                self.send(chat, '🔌 إدارة الموردين\n\nاختر موردًا لتحديث منتجاته وضبط هامش الربح.\n🔒 تُحفظ مفاتيح الوصول في إعدادات السيرفر.', buttons(rows))
            elif cmd == 'addsupplier':
                self.send(chat, '💱 عملة المورد\n\nاختر عملة أسعار المنتجات لدى المورد.', buttons([[('EGP', 'adm:suppliercurrency:EGP'), ('USD', 'adm:suppliercurrency:USD')], [('⬅️ الموردون', 'adm:suppliers')]]))
            elif cmd == 'suppliercurrency':
                self.begin_form(chat, 'supplier_name', '🔌 اسم المورد\n\nأدخل اسمًا مختصرًا باستخدام الحروف الإنجليزية والأرقام فقط، بحد أقصى 24 حرفًا.', currency=parts[2])
            elif cmd == 'sync':
                self.begin_form(chat, 'sync_percent', '📈 نسبة الربح\n\nأدخل النسبة المئوية، أو 0 دون نسبة إضافية.\nℹ️ المزامنة تعيد حساب أسعار منتجات هذا المورد.', currency=parts[2], supplier=parts[3])
            elif cmd in ('topups', 'orders', 'tickets'):
                self.clear_form()
                self.admin_records(chat, cmd)
            elif cmd == 'summary':
                self.clear_form()
                self.admin_summary(chat)
            elif cmd in ('deliver', 'refund'):
                self.begin_form(chat, cmd, '🔐 تسليم الطلب\n\nأرسل بيانات التسليم الكاملة للعميل في رسالة واحدة.' if cmd == 'deliver' else '↩️ إلغاء الطلب ورد الرصيد\n\nأدخل سبب الإلغاء. سيُرسل للعميل مع تحديث الطلب.', currency=parts[2], order=parts[3])
            elif cmd == 'closeticket':
                with self.stores[parts[2]].lock:
                    self.stores[parts[2]].db.execute("UPDATE tickets SET state='closed' WHERE id=?", (parts[3],))
                self.send(chat, '✅ تم إغلاق طلب الضمان.')
            elif cmd == 'settings':
                self.clear_form()
                self.send(chat, '⚙️ إعدادات المتجر\n\nاختر الإعداد الذي تريد تحديثه.\n\n✨ أيقونات المنتجات المخصصة تعتمد على أهلية حساب مالك البوت.\nعند عدم توفرها، تُستخدم رموز الإيموجي العادية.', buttons([[('🟡 إعداد شحن Binance', 'adm:binance')], [('💳 بيانات التحويل بالعربي', 'adm:payment'), ('💳 Payment instructions', 'adm:payment_en')], [('✈️ تلجرام الدعم', 'adm:support'), ('💬 واتساب الدعم', 'adm:whatsapp')], [('✨ تفعيل اللوجوهات', 'adm:logos:1'), ('رموز عادية', 'adm:logos:0')], [('⬅️ لوحة الإدارة', 'adm:home')]]))
            elif cmd == 'binance':
                self.clear_form()
                self.binance_settings(chat)
            elif cmd in ('bn_payid', 'bn_uid', 'bn_rate_EGP', 'bn_rate_USD'):
                prompts = {'bn_payid': '👤 معرّف استقبال Binance\n\nأدخل Pay ID أو UID الذي سيستخدمه العملاء للتحويل.', 'bn_uid': '🔎 UID حساب الاستقبال\n\nأدخل UID حساب Binance المرتبط بمفاتيح القراءة.\nيجب أن يطابق معرّف المستلم في سجل التحويلات.', 'bn_rate_EGP': '💱 سعر USDT مقابل الجنيه\n\nأدخل الرصيد بالجنيه الذي سيُضاف مقابل كل 1 USDT.', 'bn_rate_USD': '💱 سعر USDT مقابل رصيد الدولار\n\nأدخل رصيد الدولار الذي سيُضاف مقابل كل 1 USDT.'}
                self.begin_form(chat, cmd, prompts[cmd])
            elif cmd == 'bn_toggle':
                enabled = self.option('BINANCE_ENABLED', '0') != '1'
                if enabled and (not self.binance.configured() or not any(self.binance.rate(currency) for currency in self.stores)):
                    raise BinanceError('disabled')
                self.db.execute('INSERT OR REPLACE INTO shop_options VALUES (?,?)', ('BINANCE_ENABLED', '1' if enabled else '0'))
                self.db.commit()
                self.binance_settings(chat)
            elif cmd == 'bn_test':
                if not self.binance.configured():
                    raise BinanceError('disabled')
                records = self.binance.client.history()
                self.send(chat, f'✅ قراءة سجل Binance نجحت. عدد السجلات المتاحة: {len(records)}\nلم يتم إضافة أرصدة أو إجراء تحويلات. لازم تختبر تحويل وارد صغير وبيانات المستلم قبل فتح الدفع للعملاء.', buttons([[('⬅️ إعداد Binance', 'adm:binance')]]))
            elif cmd == 'logos':
                if parts[2] not in ('0', '1'):
                    raise StoreError('اختيار غير صالح.')
                self.db.execute('INSERT OR REPLACE INTO shop_options VALUES (?,?)', ('CUSTOM_BUTTON_ICONS', parts[2]))
                self.db.commit()
                self.send(chat, '✅ تم تحديث عرض الأيقونات.\n\nأعد فتح قائمة المنتجات لمعاينة التغيير.', buttons([[('⬅️ لوحة الإدارة', 'adm:home')]]))
            elif cmd in ('payment', 'payment_en', 'support', 'whatsapp'):
                prompt = '💬 رقم دعم واتساب\n\nأدخل الرقم مع كود الدولة، أو رقمًا مصريًا يبدأ بـ 01.' if cmd == 'whatsapp' else '✈️ حساب دعم تلجرام\n\nأدخل اسم المستخدم دون علامة @.' if cmd == 'support' else '💳 تعليمات التحويل اليدوي\n\nأدخل وسيلة الدفع ورقم الاستقبال والتعليمات باللغة المختارة.\nسيظهر هذا النص للعملاء كما تكتبه.'
                self.begin_form(chat, cmd, prompt)
            else:
                raise StoreError('الزر غير متاح.')
            return True
        row = self.db.execute('SELECT value FROM admin_form WHERE customer=?', (self.owner,)).fetchone()
        if row and not action and (message or {}).get('photo'):
            form = json.loads(row[0])
            if form.get('kind') == 'image':
                self.process_form(chat, form, message['photo'][-1]['file_id'])
                return True
        if row and text and not action:
            form = json.loads(row[0])
            if text.startswith('/') and form.get('kind') != 'stock_password':
                return False
            if text in ('🛍 Products', '🎁 Free services', '💬 Support', '👛 Wallet', '🔗 API', '🛡 Warranty', '📦 Orders', '💱 Currency'):
                self.clear_form()
                return False
            self.process_form(chat, form, text)
            return True
        return False

    def process_form(self, chat, form, text):
        kind = form['kind']
        store = self.stores.get(form.get('currency'))
        if kind in ('bn_payid', 'bn_uid', 'bn_rate_EGP', 'bn_rate_USD'):
            if kind in ('bn_payid', 'bn_uid'):
                if not re.fullmatch(r'[0-9]{4,24}', text.strip()):
                    raise StoreError('اكتب رقم Binance ID صحيح بالأرقام فقط.')
                value = text.strip()
                name = 'BINANCE_PAY_ID' if kind == 'bn_payid' else 'BINANCE_RECEIVER_UID'
            else:
                from decimal import Decimal, InvalidOperation
                try:
                    rate = Decimal(text.strip())
                    if not rate.is_finite() or not 0 < rate <= 1000000:
                        raise ValueError()
                except (InvalidOperation, ValueError):
                    raise StoreError('اكتب سعر تحويل موجب وصحيح.') from None
                value, name = str(rate), 'BINANCE_USDT_' + kind[-3:] + '_RATE'
            self.db.execute('INSERT OR REPLACE INTO shop_options VALUES (?,?)', (name, value))
            self.db.commit()
            self.clear_form()
            self.binance_settings(chat)
        elif kind == 'product_name':
            if not text.strip() or len(text) > 180:
                raise StoreError('اسم المنتج من 1 إلى 180 حرف.')
            form.update(kind='product_source', name=text.strip())
            self.save_form(form)
            self.send(chat, '🚚 نوع تسليم المنتج\n\n🔗 رابط: تضيف الروابط إلى المخزون ويُسلّم رابط لكل عملية شراء.\n📧 إيميل وباسورد: تضيف الحسابات ويُسلّم حساب لكل عملية شراء.\n👨‍💻 يدوي: تستقبل الطلب وتُرسل بيانات التسليم بنفسك.\n\nاختر النوع المناسب:', buttons([[('🔗 رابط', 'adm:source:link')], [('📧 إيميل وباسورد', 'adm:source:account')], [('👨‍💻 تسليم يدوي', 'adm:source:manual')], [('❌ إلغاء', 'adm:home')]]))
        elif kind == 'product_price':
            if money(text) <= 0:
                raise StoreError('السعر لازم يكون أكبر من صفر.')
            form.update(kind='product_description', price=text)
            self.save_form(form)
            self.send(chat, '📝 وصف المنتج\n\nأدخل التفاصيل التي يحتاجها العميل قبل الشراء.\nلتخطي الوصف، أرسل الرمز - فقط.')
        elif kind == 'product_description':
            form.update(kind='product_confirm', description='' if text == '-' else text[:1500])
            self.save_form(form)
            delivery_label = {'link': 'رابط — تلقائي', 'account': 'إيميل وباسورد — تلقائي', 'manual': 'يدوي', 'text': 'مخزون نصي — تلقائي'}.get(form.get('delivery_format'), 'مخزون نصي — تلقائي')
            self.send(chat, f"🧾 مراجعة بيانات المنتج\n\n🛍 الاسم: {form['name']}\n💰 السعر: {form['price']} {form['currency']}\n🚚 التسليم: {delivery_label}\n\n📝 الوصف:\n{form['description'] or 'بدون وصف'}\n\nاضغط «حفظ المنتج» لإضافته إلى المتجر.", buttons([[('✅ حفظ المنتج', 'adm:confirmproduct'), ('❌ إلغاء', 'adm:home')]]))
        elif kind == 'stock_email':
            email = text.strip()
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
                raise StoreError('أدخل بريدًا إلكترونيًا صحيحًا للحساب.')
            form.update(kind='stock_password', email=email)
            self.save_form(form)
            self.send(chat, '🔑 كلمة مرور الحساب\n\nأرسل كلمة المرور في رسالة واحدة دون أسطر جديدة.\nسيُحفظ البريد الإلكتروني وكلمة المرور كقطعة واحدة في المخزون.', buttons([[('❌ إلغاء', 'adm:home')]]))
        elif kind == 'stock_password':
            if not text.strip() or '\n' in text or '\r' in text or len(text) > 1000:
                raise StoreError('أدخل كلمة مرور غير فارغة في سطر واحد، بحد أقصى 1000 حرف.')
            store.add_stock(form['product'], 'Email: ' + form['email'] + '\nPassword: ' + text)
            self.clear_form()
            self.send(chat, '✅ تمت إضافة الحساب إلى المخزون.\n\nسيُسلّم البريد الإلكتروني وكلمة المرور معًا عند الشراء.')
            self.admin_item(chat, form['currency'], form['product'])
        elif kind in ('price', 'stock', 'image', 'name', 'description'):
            if kind == 'price':
                store.set_price(form['product'], text)
            elif kind == 'image':
                store.set_image(form['product'], '' if text == '-' else text)
            elif kind in ('name', 'description'):
                store.set_product_text(form['product'], kind, '' if text == '-' and kind == 'description' else text)
            else:
                store.add_stock(form['product'], text)
            self.clear_form()
            self.send(chat, '✅ تم حفظ التعديلات بنجاح.')
            self.admin_item(chat, form['currency'], form['product'])
        elif kind == 'supplier_name':
            if not re.fullmatch(r'[A-Za-z0-9]{1,24}', text) or text in ('local', 'manual'):
                raise StoreError('الاسم بحروف إنجليزي وأرقام، بحد أقصى 24.')
            form.update(kind='supplier_url', supplier=text)
            self.save_form(form)
            self.send(chat, '🌐 رابط المورد\n\nأدخل رابط الموقع، مثل:\nhttps://canboso.com\n\nℹ️ الربط الحالي يدعم واجهات الموردين المتوافقة مع Canboso.')
        elif kind == 'supplier_url':
            if not text.startswith('https://') or len(text) > 300:
                raise StoreError('الرابط لازم يبدأ بـ https://')
            form.update(kind='supplier_env', base_url=text.rstrip('/'))
            self.save_form(form)
            self.send(chat, '🔑 متغير مفتاح المورد\n\nأدخل اسم المتغير في ملف .env، مثل:\nSUPPLIER_API_KEY\n\n🔒 أدخل اسم المتغير فقط؛ احتفظ بالمفتاح نفسه في إعدادات السيرفر.')
        elif kind == 'supplier_env':
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,80}', text):
                raise StoreError('ابعت اسم المتغير فقط مثل SUPPLIER_TWO_KEY.')
            store.add_supplier(form['supplier'], {'adapter': 'canboso', 'base_url': form['base_url'], 'key_env': text})
            self.clear_form()
            self.send(chat, '✅ تم حفظ المورد.' + ('' if os.environ.get(text) else '\nضع مفتاحه في متغير البيئة المحدد وأعد التشغيل.'), buttons([[('🔄 استيراد المنتجات', f"adm:sync:{form['currency']}:{form['supplier']}"), ('الموردون', 'adm:suppliers')]]))
        elif kind == 'sync_percent':
            store.pricing(0, 0, text)
            form.update(kind='sync_fixed', percent=text)
            self.save_form(form)
            self.send(chat, 'الربح الثابت لكل قطعة بـ ' + store.currency + '؟ اكتب 0 لو من غير مبلغ ثابت.')
        elif kind == 'sync_fixed':
            money(text)
            self.send(chat, '⏳ جارٍ تحديث منتجات المورد…\n\nيرجى الانتظار حتى اكتمال المزامنة.')
            count = store.sync(form['supplier'], text, form['percent'])
            self.clear_form()
            self.send(chat, f'✅ تم تحديث {count} منتج. المنتجات بتظهر للجميع مهما كانت عملة المحفظة.', buttons([[('📦 المنتجات', 'adm:products:0'), ('الموردون', 'adm:suppliers')]]))
        elif kind == 'deliver':
            customer = store.fulfill(form['order'], text)
            self.clear_form()
            self.send(chat, '✅ تم تسليم الطلب وتحديث حالته.')
            self.notify(customer, json.dumps(store.order(customer, form['order']), ensure_ascii=False, indent=2))
        elif kind == 'refund':
            with store.lock:
                order = store.db.execute('SELECT state,customer FROM orders WHERE id=?', (form['order'],)).fetchone()
            if not order or order['state'] != 'waiting_admin':
                raise StoreError('الرد متاح للطلبات اليدوية المنتظرة فقط.')
            result = store.refund(form['order'], text, manual_only=True)
            self.clear_form()
            self.send(chat, '✅ تم إرجاع الرصيد إلى محفظة العميل.')
            self.notify(order['customer'], json.dumps(result, ensure_ascii=False, indent=2))
        elif kind in ('payment', 'payment_en', 'support', 'whatsapp'):
            if kind == 'support' and not re.fullmatch(r'@?[A-Za-z0-9_]{5,32}', text):
                raise StoreError('اكتب يوزر تلجرام صحيح.')
            if len(text) > 1500:
                raise StoreError('البيانات بحد أقصى 1500 حرف.')
            if kind == 'whatsapp':
                text = re.sub(r'[\s()+-]', '', text)
                if re.fullmatch(r'01[0125][0-9]{8}', text):
                    text = '20' + text[1:]
                elif text.startswith('00'):
                    text = text[2:]
                if not re.fullmatch(r'[1-9][0-9]{7,14}', text):
                    raise StoreError('اكتب رقم واتساب صحيح مع كود الدولة.')
            name = {'payment': 'MANUAL_PAYMENT_DETAILS', 'payment_en': 'MANUAL_PAYMENT_DETAILS_EN', 'support': 'SUPPORT_USERNAME', 'whatsapp': 'SUPPORT_WHATSAPP'}[kind]
            self.db.execute('INSERT OR REPLACE INTO shop_options VALUES (?,?)', (name, text.lstrip('@') if kind == 'support' else text))
            self.db.commit()
            self.clear_form()
            self.send(chat, '✅ تم حفظ إعدادات المتجر بنجاح.', buttons([[('⬅️ لوحة الإدارة', 'adm:home')]]))
        else:
            self.send(chat, 'ℹ️ استخدم الأزرار لإكمال الخطوة الحالية.\n\nللإلغاء والعودة إلى القائمة: /cancel')

    def admin_records(self, chat, kind):
        total = 0
        for currency, store in self.stores.items():
            if kind == 'topups':
                for row in store.pending_topups():
                    total += 1
                    self.send(chat, f"💳 طلب شحن يدوي\n\n👤 العميل: {row['customer']}\n💰 المبلغ: {display(row['amount'])} {currency}\n\n🧾 رقم الطلب:\n{row['id']}\n\n📎 إثبات التحويل:\n{row['proof']}", self.topup_buttons(currency, row['id']))
                    if row['proof'].startswith('photo:'):
                        self.tg('sendPhoto', chat_id=chat, photo=row['proof'].splitlines()[0][6:])
            elif kind == 'orders':
                with store.lock:
                    rows = [dict(r) for r in store.db.execute("SELECT * FROM orders WHERE state NOT IN ('quoted','completed','refunded') ORDER BY created DESC LIMIT 30")]
                for row in rows:
                    total += 1
                    markup = None
                    if row['state'] == 'waiting_admin':
                        markup = buttons([[('📦 تسليم', f"adm:deliver:{currency}:{row['id']}"), ('↩️ رد الرصيد', f"adm:refund:{currency}:{row['id']}")]])
                    state = self.t(self.owner, row['state']) if row['state'] in ('quoted', 'reserved', 'processing', 'uncertain', 'waiting_admin', 'supplier_pending', 'completed', 'refunded', 'cancelled') else row['state']
                    self.send(chat, f"🛒 متابعة الطلب\n\n👤 العميل: {row['customer']}\n💰 المبلغ: {display(row['price'])} {currency}\n📌 الحالة: {state}\n\n🧾 رقم الطلب:\n{row['id']}", markup)
            elif kind == 'tickets':
                with store.lock:
                    rows = [dict(r) for r in store.db.execute("SELECT * FROM tickets WHERE state='open' LIMIT 30")]
                for row in rows:
                    total += 1
                    self.send(chat, f"🛡 طلب ضمان\n\n👤 العميل: {row['customer']}\n\n🧾 رقم الطلب الأصلي:\n{row['order_id']}\n\n🛡 رقم طلب الضمان:\n{row['id']}\n\n📝 وصف المشكلة:\n{row['message']}", buttons([[('✅ إغلاق الطلب', f"adm:closeticket:{currency}:{row['id']}")]]))
        self.send(chat, '📋 عدد السجلات المعروضة: ' + str(total), buttons([[('⬅️ لوحة الإدارة', 'adm:home')]]))

    def admin_summary(self, chat):
        customers = set()
        lines = ['📊 ملخص المتجر']
        for currency, store in self.stores.items():
            with store.lock:
                customers.update(row[0] for row in store.db.execute('SELECT id FROM customers'))
                pending = store.db.execute("SELECT count(*) FROM topups WHERE state='pending'").fetchone()[0]
                waiting = store.db.execute("SELECT count(*) FROM orders WHERE state='waiting_admin'").fetchone()[0]
                completed, sales = store.db.execute("SELECT count(*),coalesce(sum(price),0) FROM orders WHERE state='completed'").fetchone()
                balance = store.db.execute('SELECT coalesce(sum(balance),0) FROM customers').fetchone()[0]
            lines += [f'\n💱 محفظة {currency}\n', f'🛍 المنتجات الظاهرة: {len(store.catalog())}', f'⏳ طلبات شحن قيد المراجعة: {pending}', f'📦 طلبات بانتظار التسليم: {waiting}', f'✅ الطلبات المكتملة: {completed}', f'💰 المبيعات المكتملة: {display(sales)} {currency}', f'👛 أرصدة العملاء: {display(balance)} {currency}']
        lines += [f'\n👥 إجمالي الحسابات: {len(customers)}', '\n⚙️ جاهزية المتجر\n', '✅ تعليمات التحويل بالعربية' if self.option('MANUAL_PAYMENT_DETAILS') else '▫️ تعليمات التحويل بالعربية: غير محددة', '✅ تعليمات التحويل بالإنجليزية' if self.option('MANUAL_PAYMENT_DETAILS_EN') else '▫️ تعليمات التحويل بالإنجليزية: غير محددة', '✅ حساب الدعم مُعدّ' if self.option('SUPPORT_USERNAME') else '▫️ حساب الدعم: غير محدد']
        lines += ['\n💳 طرق الدفع\n',
                  '🟡 Binance Pay: ' + ('متاح' if self.binance.currencies() else 'غير متاح حاليًا'),
                  '🔴 فودافون كاش: ' + ('متاح للعملاء' if self.cash.ready() and os.environ.get('VODAFONE_TEST_ONLY', '1') != '1' else 'متاح للأدمن فقط' if self.cash_available(self.owner) else 'غير متاح حاليًا'),
                  '📱 اتصال هاتف الكاش: ' + ('متصل' if self.cash.ready() else 'غير متصل أو الخدمة غير مفعّلة'),
                  '💰 الحد الأدنى لفودافون كاش: 5 جنيه']
        self.send(chat, '\n'.join(lines), buttons([[('⚙️ إعدادات المتجر', 'adm:settings'), ('⬅️ لوحة الإدارة', 'adm:home')]]))

    def binance_settings(self, chat):
        enabled = self.option('BINANCE_ENABLED', '0') == '1'
        lines = ['🟡 شحن Binance Pay', 'الحالة: ' + ('مفعّل' if self.binance.currencies() else 'غير متاح للعملاء'),
                 'رقم التحويل: ' + (self.option('BINANCE_PAY_ID') or 'غير محدد'),
                 'UID المستلم: ' + (self.option('BINANCE_RECEIVER_UID') or 'غير محدد'),
                 'مفتاح القراءة: ' + ('موجود' if os.environ.get('BINANCE_API_KEY') else 'ناقص في .env'),
                 'Secret: ' + ('موجود' if os.environ.get('BINANCE_API_SECRET') else 'ناقص في .env')]
        for currency in self.stores:
            rate = self.binance.rate(currency)
            lines.append(f'كل 1 USDT = {rate} {currency}' if rate else f'سعر {currency}: غير محدد')
        lines += ['\nالمطلوب من Binance API قراءة السجل فقط. مفيش استخدام لصلاحيات تداول أو سحب.', 'ضع BINANCE_API_KEY وBINANCE_API_SECRET في .env محليًا، ثم أعد تشغيل البوت. لا ترسل المفاتيح في المحادثة.', 'اضبط الرقمين والأسعار، واختبر الاتصال وتحويل وارد قبل التفعيل.']
        self.send(chat, '\n'.join(lines), buttons([[('رقم التحويل Pay ID / UID', 'adm:bn_payid'), ('UID المستلم', 'adm:bn_uid')], [('سعر الجنيه', 'adm:bn_rate_EGP'), ('سعر رصيد الدولار', 'adm:bn_rate_USD')], [('🔎 اختبار قراءة السجل', 'adm:bn_test')], [('⏸ إيقاف Binance' if enabled else '▶️ تفعيل Binance', 'adm:bn_toggle')], [('⬅️ الإعدادات', 'adm:settings')]]))
