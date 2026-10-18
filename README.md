# Telegram store and reseller API

Python 3.10+, standard library only. Run one bot process. Administration uses owner-only Telegram commands.

## Start

Customer message presentation uses Telegram bold entities with UTF-16 offsets,
clear first-line headings and the original spacing, without decorative dividers. No HTML/Markdown parsing is
applied to merchant text, account passwords, links or API keys. Photo captions
respect their 1024-unit limit, including during media edits. Styling lives in
`message_style.py` and is applied consistently by the Telegram transport.

**Free services:** the customer menu has a separate 🎁 section. The owner uses
`🎁 إضافة خدمة مجانية`, enters a name, chooses link/account/manual delivery, and
adds a description; pricing is skipped. Add stock using the same existing forms.
Free services have an explicit `free_services` record and a zero price; they require
no wallet funds and create no debit ledger entry. Positive-priced products remain
in the paid catalog, and ordinary products still cannot have a zero selling price.
The `/product` JSON shortcut accepts `"is_free": true` for local/manual services.

Completed deliveries containing one valid HTTP(S) URL are shown in Telegram with
an activation button (`اضغط هنا للتفعيل`) rather than a raw URL. It appears only
after delivery, including manual fulfillment notifications and order history.
Reseller API responses retain the original delivery URL. Link stock is consumed
one item per order, including free services; accounts deliver email and password
together, and manual services go through the existing administrator queue.

Customer navigation keeps one tracked temporary menu per chat in `navigation_message`. Text screens edit that message; photo/text transitions or reply keyboards send the replacement before deleting the old menu. Delivery details, order messages, payment instructions, API keys and payment confirmations are sent as permanent records and never tracked for menu cleanup. Deletion failures leave the replacement usable. Navigation tracking persists through restarts; untracked historical messages are not bulk-deleted.

Owner product creation offers **رابط / إيميل وباسورد / تسليم يدوي** after the product name. Links and accounts use automatic stock delivery; manual products enter the existing administrator delivery queue. Add a link as one stock item. Account stock uses two guided steps (email, then password) and stores/delivers the pair together. Empty or malformed values are rejected. Existing products retain their previous free-text stock format. The optional `/product` field `delivery_format` accepts `link`, `account`, `text`, or `manual`; `manual` requires `source=manual`, and other formats require `source=local`.

1. Copy `bot/.env.example` to `bot/.env`.
2. Set `TELEGRAM_BOT_TOKEN`, `ADMIN_TELEGRAM_ID`, `SUPPORT_USERNAME`, and `MANUAL_PAYMENT_DETAILS` (one line of payment method, recipient and reference instructions).
3. Add supplier keys as environment entries, for example `SUPPLIER_API_KEY=...`. Replace the key previously shared in chat. Do not send secrets in Telegram commands.
4. Run `python bot/main.py`, open the bot, send `/start`, then `/admin` as the owner.
5. Optional reseller API: set `API_ENABLED=1`. It binds to localhost:8080 by default. Set `PUBLIC_API_URL` after configuring an HTTPS reverse proxy. Public hosting, certificates and real payment processing are not configured here.

Customers have **independent EGP and USD wallets**. Currency selects the wallet for top-ups and API key creation. Telegram displays **all products together**, regardless of that preference; checkout charges the wallet matching the product's displayed price currency. No automatic exchange or wallet conversion is implemented. The reseller API paths remain scoped to their currency. Selling USD supplier products in EGP requires an explicit exchange-rate policy and implementation.

On first contact, the bot asks the customer to choose **العربية / English** before displaying the menu. Arabic selects the EGP wallet by default; English selects USD. Language and wallet preferences persist. Returning `/start` opens the saved menu. The Language button or `/language` reopens the choice, and selecting a language resets the preferred wallet to that language's default. The Currency button overrides the wallet independently afterward. Choosing either language never converts balances, revokes API keys, or filters products. Customer navigation, checkout, wallet instructions, order statuses, warranty instructions and deposit decisions are localized. Owner administration stays in Arabic. Merchant-written product descriptions, delivery data and manual payment instructions are shown as entered; optionally configure `MANUAL_PAYMENT_DETAILS_EN` for English payment instructions.

The welcome screen uses `STORE_NAME` (default NF STORE). Support shows direct Telegram and WhatsApp buttons from `SUPPORT_USERNAME` and `SUPPORT_WHATSAPP`; shop settings in the database override `.env`. WhatsApp numbers are stored with country code and without `+`, for example `201101560023`. The admin accepts Egyptian local mobile numbers and converts them to the international form. Contact numbers are used for support only; manual payment instructions must be configured separately.

The owner has a **⚙️ لوحة الإدارة** button after `/start`. The button and every admin callback are restricted to `ADMIN_TELEGRAM_ID`. Guided forms add products and stock, edit names/descriptions/prices/photos, hide/show products, register compatible suppliers by environment variable name, synchronize products with markup, approve/reject deposits, fulfill/refund manual orders, close warranty tickets, and edit Arabic/English payment instructions and support details. The Summary button shows sales totals separately per currency, pending work and missing payment/support settings. Forms and settings persist across restarts. `/cancel` returns home. Commands below remain available as shortcuts.

Products appear as full-width buttons, one product per row, eight per page. Recognized services have public custom-emoji logo IDs in `product_icons.py`, matched by the supplier's brand hint or product name. Custom button logos require Telegram eligibility (a Premium bot creator or an eligible additional bot username purchased through Fragment). The admin Settings panel can toggle custom logos and ordinary symbols. If Telegram rejects a custom-icon keyboard, the catalog retries using ordinary emoji symbols. No Premium subscription or paid username is purchased by this project. See https://core.telegram.org/bots/api#inlinekeyboardbutton.

Opening a product shows its supplier photo above the details and purchase controls when available. Relative supplier image paths are resolved against the supplier origin. Missing or inaccessible photos fall back to text. In the admin product screen, **🖼 إضافة / تغيير الصورة** accepts an uploaded Telegram photo or direct HTTPS image URL; `-` hides the image. Admin images override supplier pictures and survive later syncs. No substitute photo is invented for a product without an image.

## Manual payment

Wallet shows instructions, balances and pending top-ups. **Top up wallet** guides the customer through currency, amount, photo/reference and confirmation; it creates a pending request, never an automatic credit. The requested currency is captured with the form. Navigation or `/cancel` abandons the current form. `/topup 100 reference` remains an alternative. The owner receives the request and receipt. Verify the transfer externally before approving. Approval credits the exact wallet once; repeated decisions do not resend customer notifications. `/pending EGP` recovers requests if a notification failed.

Screenshots and manual references never credit funds automatically. A separate Binance Pay verifier is available but remains disabled until configured and tested; see [BINANCE.md](BINANCE.md).

## Products and administration

Send commands as normal text (JSON without Markdown fences):

```text
/product EGP {"name":"My product","source":"local","cost":"100","percent":"5","fixed":"10"}
/stock EGP PRODUCT_ID one delivery payload for one item
/product USD {"name":"Manual service","source":"manual","price":"8.5"}
/supplier USD vendor1 {"adapter":"canboso","base_url":"https://canboso.com","key_env":"SUPPLIER_API_KEY"}
/sync USD vendor1 10 0.5
/queue EGP
/deliver EGP ORDER_ID delivery details
/refund EGP ORDER_ID reason
/hide EGP PRODUCT_ID
/tickets EGP
```

Pricing is `cost × (1 + percent/100) + fixed`. Percentage and fixed profit work together. Explicit `price` sets a local product's selling price directly. Money is stored as integers with six decimal places. Each purchase buys one unit. Quotes expire in 15 minutes. Catalog changes invalidate quoted prices. Cancelling a quote prevents its old confirmation button from charging the wallet.

`local` products deliver private stock automatically; `/stock` adds one piece. `manual` products deduct the balance and wait for `/deliver`. `/refund` cancels a waiting manual order and returns its balance once; the state is rechecked in the same transaction as the credit. `/queue` shows outstanding Telegram and API orders. My orders combines both wallets, newest first, in pages of six (up to 30 recent per wallet). Opening an order shows delivery details, refresh, a retry of its exact original checkout if uncertain, and a warranty button for completed orders. Warranty requests are checked for ownership regardless of selected currency; repeated requests reuse an open ticket. `/claim ORDER_ID description` remains available. Warranty resolution is manual.

Configure multiple suppliers with distinct IDs and environment variables. The included adapter implements the **Canboso buyer contract**. Other API contracts need documentation and a dedicated adapter; changing the URL does not support an incompatible API. Existing supplier IDs cannot be reassigned to another configuration. Do not change a key's underlying buyer account while orders remain unresolved.

Synchronization is explicit through the supplier panel or `/sync`, not scheduled. It imports all positively priced products in the matching currency and applies the chosen markup. Ordinary account products have automatic checkout. Slot, upgrade and other products requiring additional inputs are displayed with a contact-support button; no balance is deducted for those inquiries. Imported stock is a snapshot until the next synchronization. Hidden products remain hidden through later syncs. Synchronization reapplies its markup and overwrites per-product price edits for that supplier. Before the first supplier purchase attempt, current upstream price and stock are checked. Changed products are refunded and require re-syncing. The supplier purchase contract has no maximum-price field, so a price change between check and purchase cannot be prevented atomically.

Purchase attempts use persistent idempotency IDs. A network error leaves funds reserved; retry the **same** confirmation button or API idempotency key. Ambiguous supplier charges are never refunded automatically. Supplier orders that remain pending need owner follow-up. Automatic completion polling and slot/upgrade checkout are not implemented.

## Reseller API and data

See [API.md](API.md). Keys are issued and rotated from Telegram separately per currency and stored as hashes. Rotation now requires a separate confirmation before revoking the old key. API and Telegram purchases share the customer wallet. Supplier secrets, costs and order references are not exposed.

Keep `.env`, SQLite databases, stock, deliveries and backups private. The HTTP API must sit behind HTTPS for public use. Its built-in limiter counts 60 requests/minute per connecting IP. Reverse proxies using localhost share that quota unless trusted-proxy rate limiting is configured separately. No live supplier purchase was made in development.

`python bot/backup.py` creates consistent, integrity-checked SQLite backups in `bot/backups/`, outside version control. It does not copy `.env`. The polling runtime skips a malformed update after reporting an error, stores its offset, handles Telegram rate-limit waits, and splits long delivery text by UTF-16 length. Error logs contain exception types rather than message payloads or credentials. Keep the machine and bot process running during use; automatic startup and external hosting are not configured.

Validation:

```powershell
python -m unittest discover -s bot -p 'test_*.py' -v
```
