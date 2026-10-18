# Binance Pay internal-transfer top-ups

This integrates the signed, read-only Binance Pay history endpoint, **not** the separate Binance Pay Merchant API, on-chain deposits, P2P fiat trades, or browser automation. Availability depends on the account, API permissions and region. The code does not initiate transfers, trades, withdrawals or refunds.

## Configuration

1. Find your account's **UID** in Binance. Set `BINANCE_RECEIVER_UID` to that UID. It must match the `receiverInfo.binanceId` on incoming Pay records.
2. Set `BINANCE_PAY_ID` to the public Pay ID or UID customers will transfer to. A Pay ID can differ from the account UID; do not assume they are interchangeable when checking a receipt.
3. Create a dedicated API key with reading access. Do not enable trading or withdrawals for this integration. Store `BINANCE_API_KEY` and `BINANCE_API_SECRET` in `bot/.env`, never in chat or source code. Restart the bot after changing these secrets.
4. In **Admin → Settings → Binance**, set the receiving IDs and the explicit credit rates: `BINANCE_USDT_EGP_RATE` and `BINANCE_USDT_USD_RATE`. Each says how much store wallet credit **1 USDT** buys. Neither rate has an implicit default or market quote. A currency without a valid rate is unavailable for Binance top-ups. Admin settings override the same values in `.env`.
5. Use the read-history test. Test a small internal incoming transfer and confirm the receiver UID, transaction ID and exact credited amount before making the feature available to customers. Toggle Binance on when configuration is ready. `BINANCE_ENABLED=0` is the default.

Signed read-only access and recipient UID were verified against the configured account. A real incoming receipt's numeric app Order ID was also matched exactly to its API record. That historical transfer was not credited to any wallet. A fresh request-to-credit payment test has not been completed. Setting a toggle alone does not establish full payment-flow compatibility.

## Customer flow

Wallet → Top up → Binance Pay → destination wallet → USDT amount → exact transfer instructions → numeric **Order ID** from the Binance transfer details → automatic verification.

The entered USDT amount accepts up to two decimal places and is preserved exactly; no identifying fraction or extra cents are added. Different customers and credit currencies may use the same amount. Matching uses the customer's submitted exact Order ID and the existing globally unique receipt claim, never amount alone. The displayed rate converts the full received amount into the chosen wallet. Rates and wallet are locked to each request; customers may return to choose a different credit wallet before paying without changing their catalog or saved wallet preference. Amounts/credits use Decimal and integer accounting; credit is rounded down to six decimal places. Existing requests retain their original quoted amounts.

Each request has a 30-minute transfer window. Matching transfers within that window can be claimed within 24 hours of request creation. There are at most three active requests per customer. The request must exist **before** the transfer; old transfers need manual support review. Leaving the input form does not cancel an already displayed transfer request or discard a verified receipt. Its original Enter Order ID / Check buttons remain usable by its owner.

The verifier requires all of:

- A successful signed history response from the configured receiving account.
- Exact app-facing `orderId`, positive incoming amount, order type C2C or PAY, and asset USDT. The live response has this numeric field even though the published response example may omit it. It is compared as an exact string without floating-point conversion. Missing or ambiguous IDs never fall back to amount matching.
- Exact displayed amount and receiver UID.
- Transfer timestamp within the request's original validity window.
- A transaction not claimed by any other request, customer or currency.

Receipt numbers are not by themselves identity proof. This API's receiver-side records can omit the sender UID. Request ownership, exact server-generated amounts, timestamps and global duplicate protection bind credits to the pre-created request; a transfer made before a quote or with the wrong exact amount is not automatically assigned. For stronger payer authentication or business checkout, a separate Binance Pay Merchant integration with merchant-linked orders is needed.

## Recovery and limitations

A verified receipt is first durably bound to its request in `binance_pay.sqlite3`. The numeric Order ID and internal Transaction ID are stored as aliases of the same receipt. Customer input and confirmations use the Order ID; the internal Transaction ID remains the canonical claim and unique ledger reference. Replaying either ID cannot credit a different request, customer or wallet. Legacy saved Transaction ID submissions can finish recovery without becoming a second receipt. Retrying after a crash between commits completes the original credit exactly once. There is no shared SQLite transaction across the databases. Keep the payment database and wallet databases together in backups; restoring only one can break the claim/ledger relationship. `bot/backup.py` backs up all local SQLite databases; stop the bot before taking a cross-database recovery snapshot.

The history endpoint returns up to 100 records and has no documented pagination parameter. This implementation requests the previous 24 hours and caches results for 60 seconds. Busy accounts may have older transfers outside that returned set: these are left uncredited for support review, never guessed. Binance `Retry-After` is honored. No automatic conversion of USDT to fiat is performed; these are store wallet credit rates chosen by the owner. The method validates internal Pay history rather than blockchain transaction hashes.

Official contract: [Binance Pay history](https://developers.binance.com/en/docs/catalog/investment-and-services-pay/api/rest-api/~). Positive `amount` means income. C2C recipient records identify the receiver using `receiverInfo.binanceId`. Signing follows [Binance Pay general information](https://developers.binance.com/en/docs/products/pay/general-info).
