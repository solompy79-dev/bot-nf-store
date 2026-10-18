"""Private-origin JSON API; put HTTPS reverse proxy in front for public access."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from store import StoreError


def make_server(stores, host='127.0.0.1', port=8080):
    buckets = {}
    guard = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = 'ShopAPI'

        def log_message(self, *args):
            pass  # No access logs containing customer details.

        def reply(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            if code == 429:
                self.send_header('Retry-After', '60')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self.route()

        def do_POST(self):
            self.route()

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def route(self):
            try:
                now = time.monotonic()
                ip = self.client_address[0]
                with guard:
                    if len(buckets) > 10000:
                        expired = [key for key, value in buckets.items() if now - value[0] >= 60]
                        for key in expired:
                            del buckets[key]
                    bucket = buckets.get(ip, [now, 0])
                    if now - bucket[0] >= 60:
                        bucket = [now, 0]
                    bucket[1] += 1
                    buckets[ip] = bucket
                if bucket[1] > 60:
                    return self.reply(429, {'error': 'rate_limited'})
                parts = urlsplit(self.path).path.strip('/').split('/')
                if len(parts) < 3 or parts[0] != 'v1' or parts[1] not in stores:
                    return self.reply(404, {'error': 'not_found'})
                store = stores[parts[1]]
                auth = self.headers.get('Authorization', '')
                if not auth.startswith('Bearer ') or len(auth) > 256:
                    return self.reply(401, {'error': 'unauthorized'})
                user = store.authenticate(auth[7:])
                if user is None:
                    return self.reply(401, {'error': 'unauthorized'})
                endpoint = '/'.join(parts[2:])
                if self.command == 'GET' and endpoint == 'products':
                    return self.reply(200, {'products': store.catalog()})
                if self.command == 'GET' and endpoint == 'balance':
                    return self.reply(200, store.balance(user))
                if self.command == 'GET' and endpoint == 'orders':
                    return self.reply(200, {'orders': store.orders(user)})
                if self.command == 'GET' and len(parts) == 4 and parts[2] == 'orders':
                    return self.reply(200, store.order(user, parts[3]))
                if self.command == 'POST' and endpoint == 'purchase':
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 4096:
                        return self.reply(413, {'error': 'invalid_body_size'})
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict) or set(body) != {'product_id'} or not isinstance(body['product_id'], str):
                        return self.reply(400, {'error': 'send_product_id_only; one unit per request'})
                    result = store.purchase(user, body['product_id'], self.headers.get('Idempotency-Key', ''))
                    return self.reply(200, result)
                self.reply(404, {'error': 'not_found'})
            except StoreError as exc:
                self.reply(409, {'error': str(exc)})
            except (ValueError, TypeError, KeyError):
                self.reply(400, {'error': 'invalid_request'})
            except Exception:
                self.reply(503, {'error': 'temporarily_unavailable; retry with same Idempotency-Key'})

    return ThreadingHTTPServer((host, port), Handler)
