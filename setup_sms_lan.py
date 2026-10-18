"""Prepare private LAN pairing without enabling customer cash payments."""
import re
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent
env = root / '.env'
text = env.read_text(encoding='utf-8')
existing = re.search(r'^SMS_BRIDGE_TOKEN=(.+)$', text, flags=re.M)
token = existing[1].strip().strip('\"\'') if existing else ''
if len(token) < 32:
    token = secrets.token_urlsafe(32)
settings = {'SMS_BRIDGE_ENABLED': '1', 'SMS_BRIDGE_HOST': '192.168.1.9',
            'SMS_BRIDGE_PORT': '8091', 'SMS_BRIDGE_TOKEN': token,
            'VODAFONE_ENABLED': '0', 'VODAFONE_WALLET': '01044266974'}
for key, value in settings.items():
    pattern = r'^' + re.escape(key) + r'=.*$'
    line = key + '=' + value
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, lambda _: line, text, flags=re.M)
    else:
        text = text.rstrip('\r\n') + '\n' + line + '\n'
env.write_text(text, encoding='utf-8')
(root / 'sms-pairing.txt').write_text(
    'Private phone pairing - do not share with customers\n\n'
    'Test URL: http://192.168.1.9:8091/sms/heartbeat\n'
    'SMS URL: http://192.168.1.9:8091/sms/vodafone\n'
    'Method: POST\n\nHeader name:\nAuthorization\n\nHeader value:\nBearer ' + token + '\n', encoding='utf-8')
print('LAN pairing prepared. Customer cash payments remain disabled. Token saved locally only.')
