import os

from main import load_env, ApiError
from storefront import Storefront

load_env()
os.environ['API_ENABLED'] = '0'
bot = Storefront()
with bot.db:
    for name, value in {'STORE_NAME': 'NF STORE', 'SUPPORT_USERNAME': 'T8TS8', 'SUPPORT_WHATSAPP': '201101560023'}.items():
        bot.db.execute('INSERT OR REPLACE INTO shop_options VALUES (?,?)', (name, value))

profiles = {
    '': (
        'Welcome to NF STORE 🛍️\nBrowse digital products, top up your wallet and track your orders.\nTap Start to choose Arabic or English.\nSupport: @T8TS8\nWhatsApp: +201101560023',
        'NF STORE 🛍️ Digital products | Support: @T8TS8 | WhatsApp: +201101560023',
    ),
    'ar': (
        'أهلًا بيك في NF STORE 🛍️\nتصفح منتجاتنا الرقمية، اشحن محفظتك وتابع طلباتك من مكان واحد.\nاضغط ابدأ واختار لغتك عشان نبدأ.\nالدعم: @T8TS8\nواتساب: +201101560023',
        'NF STORE 🛍️ منتجات رقمية | الدعم: @T8TS8 | واتساب: +201101560023',
    ),
    'en': (
        'Welcome to NF STORE 🛍️\nBrowse digital products, top up your wallet and track your orders.\nTap Start and choose your language to get started.\nSupport: @T8TS8\nWhatsApp: +201101560023',
        'NF STORE 🛍️ Digital products | Support: @T8TS8 | WhatsApp: +201101560023',
    ),
}
for language, (description, short) in profiles.items():
    operations = [
        ('setMyName', {'name': 'NF STORE', 'language_code': language}),
        ('setMyDescription', {'description': description, 'language_code': language}),
        ('setMyShortDescription', {'short_description': short, 'language_code': language}),
        ('setMyCommands', {'commands': [
            {'command': 'start', 'description': 'القائمة الرئيسية' if language == 'ar' else 'Open NF STORE'},
            {'command': 'language', 'description': 'تغيير اللغة' if language == 'ar' else 'Change language'},
            {'command': 'cancel', 'description': 'إلغاء الخطوة الحالية' if language == 'ar' else 'Cancel the current step'},
        ], 'language_code': language}),
    ]
    for method, body in operations:
        try:
            print(method, language or 'default', bool(bot.tg(method, **body)))
        except ApiError as exc:
            print(method, language or 'default', 'unavailable', exc.code)

print('Local contact settings saved.')
print('Telegram profile name:', bot.tg('getMe')['first_name'])
for store in bot.stores.values():
    store.db.close()
bot.db.close()
