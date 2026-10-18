# Reseller API v1

Base URL: your configured HTTPS origin followed by `/v1/EGP` or `/v1/USD`.

Generate a key through Telegram after selecting the currency. Every request requires `Authorization: Bearer YOUR_KEY`. A key only accesses its customer's wallet, orders and deliveries in that currency. Rotation invalidates the previous key.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/products` | Catalog and selling prices |
| GET | `/balance` | Customer balance and currency |
| POST | `/purchase` | Buy exactly one item |
| GET | `/orders` | Up to 30 recent customer orders |
| GET | `/orders/ORDER_ID` | One customer order and private delivery |

Purchase body:

```json
{"product_id":"PRODUCT_ID"}
```

Required header: `Idempotency-Key: a-unique-checkout-id` (8–128 characters). Persist the ID before sending. Reuse it for every retry of that exact purchase, including after timeouts, 409 or 503. Never generate another key for an uncertain charge. An ID cannot purchase a different product.

Example response:

```json
{"id":"ORDER_ID","product_id":"PRODUCT_ID","state":"completed","amount":"20","currency":"EGP","delivery":"private delivery data"}
```

Orders also include `product_name` and `created_at` (Unix seconds). States: `reserved`, `processing`, `uncertain`, `waiting_admin`, `supplier_pending`, `completed`, `refunded`, `cancelled`. Cancelled Telegram quotes cannot charge their old confirmation. Repeating a completed purchase returns the same order. Manual services await owner fulfillment. Retry uncertain supplier purchases with the original purchase and key. Poll an order without creating a new purchase.

Errors: 400 invalid request; 401 invalid key; 404 unknown route; 409 business validation or inaccessible order; 413 invalid body size; 429 rate limit (respect `Retry-After`); 503 temporarily unavailable. Error shape: `{"error":"message"}`. A 409 may describe an uncertain charge: funds remain reserved; keep the original key.

Top-ups and key issuance use Telegram. No supplier secrets, payment approval, stock management or payment callbacks are exposed through this API.
