from main import load_env, ApiError
from storefront import Storefront

load_env()
bot = Storefront()
try:
    member = bot.tg('getChatMember', chat_id=bot.owner, user_id=bot.owner)
    print('OWNER_PREMIUM=' + str(member.get('user', {}).get('is_premium', False)))
except ApiError:
    print('OWNER_PREMIUM=unknown')
for store in bot.stores.values():
    store.db.close()
bot.db.close()
