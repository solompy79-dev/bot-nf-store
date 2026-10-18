"""Telegram transport and polling runtime. Python 3.10+, no dependencies."""
import json
import math
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from message_style import style_request

ROOT = Path(os.environ.get('NF_DATA_DIR') or Path(__file__).resolve().parent).resolve()


def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                os.environ.setdefault(key.strip(), value)


class ApiError(Exception):
    def __init__(self, message, code=None, retry_after=0, not_modified=False):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after
        self.not_modified = not_modified


def request(url, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(url, data=data, headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urlopen(req, timeout=40) as response:
            result = json.load(response)
    except HTTPError as exc:
        delay = 0
        try:
            failure = json.load(exc)
            if not isinstance(failure, dict):
                failure = {}
        except (ValueError, OSError):
            failure = {}
        if exc.code == 429:
            try:
                delay = int(failure.get('parameters', {}).get('retry_after', exc.headers.get('Retry-After', '60')))
            except (ValueError, TypeError, AttributeError):
                delay = 60
        unchanged = exc.code == 400 and 'message is not modified' in str(failure.get('description', '')).lower()
        raise ApiError('الخدمة غير متاحة مؤقتًا. حاول مرة تانية بعد قليل.', code=exc.code, retry_after=max(0, delay), not_modified=unchanged) from None
    except (URLError, OSError, ValueError):
        raise ApiError('تعذر الاتصال بالخدمة. حاول مرة تانية بعد قليل.') from None
    if not isinstance(result, dict) or result.get('success') is False or result.get('ok') is False:
        raise ApiError('الخدمة لم تقبل الطلب. حاول مرة تانية بعد قليل.')
    return result


def text_chunks(text, limit=3500):
    """Respect Telegram's UTF-16 length for long receipts and delivery data."""
    chunk, units = [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > limit:
            yield ''.join(chunk)
            chunk, units = [], 0
        chunk.append(char)
        units += width
    if chunk:
        yield ''.join(chunk)


class Bot:
    def tg(self, method, **body):
        remaining = getattr(self, '_telegram_wait_until', 0) - time.monotonic()
        if remaining > 0:
            raise ApiError('الخدمة غير متاحة مؤقتًا. حاول مرة تانية بعد قليل.', code=429, retry_after=math.ceil(remaining))
        try:
            return request('https://api.telegram.org/bot' + self.token + '/' + method, style_request(method, body))['result']
        except ApiError as exc:
            if exc.code == 429:
                self._telegram_wait_until = time.monotonic() + max(1, exc.retry_after)
            raise

    def send(self, chat, text, markup=None):
        sent = None
        for index, chunk in enumerate(text_chunks(str(text))):
            body = {'chat_id': chat, 'text': chunk}
            if markup and index == 0:
                body['reply_markup'] = markup
            sent = self.tg('sendMessage', **body)
        return sent

    def process_update(self, update):
        try:
            self.handle(update)
        except Exception as exc:
            # Never log update payloads, credentials or token-bearing request URLs.
            print('Update failed:', type(exc).__name__, flush=True)
            message = update.get('message') or update.get('callback_query', {}).get('message', {})
            if message.get('chat', {}).get('type') == 'private':
                chat = message['chat']['id']
                try:
                    text = self.t(chat, 'service_error') if hasattr(self, 't') else 'Service unavailable. Please try again.'
                    self.send(chat, text)
                except Exception:
                    pass
        self.db.execute("INSERT OR REPLACE INTO settings VALUES ('offset', ?)", (str(update['update_id'] + 1),))
        self.db.commit()

    def run(self):
        row = self.db.execute("SELECT value FROM settings WHERE name='offset'").fetchone()
        offset = int(row[0]) if row else 0
        print('Bot started.', flush=True)
        while True:
            try:
                if hasattr(self, 'background_tasks'):
                    self.background_tasks()
                updates = self.tg('getUpdates', offset=offset, timeout=25, allowed_updates=['message', 'callback_query'])
                for update in updates:
                    self.process_update(update)
                    offset = update['update_id'] + 1
            except Exception as exc:
                print('Polling unavailable:', type(exc).__name__, flush=True)
                remaining = max(5, getattr(exc, 'retry_after', 0))
                while remaining:
                    delay = min(30, remaining)
                    time.sleep(delay)
                    remaining -= delay


if __name__ == '__main__':
    load_env()
    if not os.environ.get('TELEGRAM_BOT_TOKEN') or not os.environ.get('ADMIN_TELEGRAM_ID', '').isdecimal():
        raise SystemExit('Set TELEGRAM_BOT_TOKEN and numeric ADMIN_TELEGRAM_ID in bot/.env.')
    from storefront import Storefront
    Storefront().run()
