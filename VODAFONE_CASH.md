# Vodafone Cash SMS bridge

Implemented but disabled by default. This is a trusted-phone integration,
not an official Vodafone API. The store must not accept customer-submitted
SMS text, images, or a transaction number as independent payment proof.

Configured receiver: `01044266974`. Expected SMS sender: exactly `VF-Cash`.
Only EGP wallet credit is supported; no EGP/USD conversion was authorized.

## Pairing before activation

1. Keep `VODAFONE_ENABLED=0` until the Android phone and connectivity are set up.
2. Generate a random `SMS_BRIDGE_TOKEN` of at least 32 characters, save locally
   in `.env`, and pair the same token on the store phone. Never share it with buyers.
3. Expose the bridge through an authenticated private network or a trusted HTTPS
   reverse proxy. The default listener is loopback `127.0.0.1:8091`.
   Do not expose the raw HTTP port to the internet. A computer-only installation
   needs a secure reachable route before a remote phone can deliver receipts.
4. Configure the Android automation to trigger on newly received SMS messages
   from `VF-Cash` only. Send the actual SMS sender and complete body; never send
   manually entered buyer messages. JSON-encode the body correctly, including
   newlines and quotes. Filter out OTP messages and other senders.
5. Send an authenticated heartbeat every 60 seconds while SMS forwarding is
   operational. Pause heartbeats if the SMS automation or its permissions fail.
6. Set the correct Egypt UTC offset (`3` during daylight saving, `2` otherwise),
   enable `VODAFONE_ENABLED=1`, and restart the bot. This fixed offset must be
   updated at clock changes. Verify phone/PC clocks are synchronized.
7. Test a new real payment against a new quote before advertising automatic cash
   payments. No live end-to-end payment has been tested yet.

Both requests use `Authorization: Bearer <SMS_BRIDGE_TOKEN>`:

- `POST /sms/heartbeat` with an empty body.
- `POST /sms/vodafone` with `Content-Type: application/json` and JSON:

```json
{"sender":"VF-Cash","body":"COMPLETE RECEIVED SMS","received_at":1790000000}
```

`received_at` is the phone's current Unix time in **seconds**, not milliseconds.
Alternatively, for Android apps without JSON string escaping, send the complete
SMS as UTF-8 text with `Content-Type: text/plain; charset=utf-8` and
`X-SMS-Sender: VF-Cash`, plus the same Authorization header. The Android trigger
must filter the sender exactly to VF-Cash; prefer the actual SMS sender variable
for this header when available. Receipt timestamps are still checked; the server
uses its own receive time for this transport. Do not use this to submit historical
messages or allow buyers to access the paired automation.
Retry the same receipt after a network error or HTTP 503; do not replace its
transaction number. A stale queued receipt is deliberately rejected and needs
manual owner review. Do not forward old SMS history or the sample receipt.

The payment button appears only with an enabled bridge and a heartbeat within
five minutes. Heartbeats demonstrate connectivity, not that phone SMS permissions
are working; test these on the phone. Existing quotes can still be paid during an
outage, so delayed receipts may require manual review.

## Matching and recovery

The customer enters the EGP amount and sending wallet number. The bot preserves
the requested amount exactly and displays a quote valid for 30 minutes. A repeated
request for the same payer and amount returns the existing unpaid quote for the
same customer. Conflicting customers or already paid quotes must wait until the
old quote expires or select a different amount. Different payers can use the same
amount. The entire received amount is credited, with no added piastres.
Copy buttons preserve the recipient's leading zero and exact payment amount.

Validation requires the exact SMS sender, receiving wallet, payer phone, amount,
and receipt timestamp within the quote window. SMS timestamps have minute
precision, so the quote's creation minute is allowed. Transactions not matching
exactly one active request do not credit anyone. Raw SMS bodies, names, balances,
and sending phone numbers are not written to logs. The payer phone is stored
in the private quote database for matching.

The SMS transaction ID is unique in a durable receipt table and in the wallet
ledger. Receipt claims are committed before wallet credit; the background task
recovers an interrupted credit without duplicating funds. Telegram sends a credit
confirmation after successful processing; a notification can repeat after a crash,
but wallet credit cannot. Back up all SQLite databases together with `backup.py`.

SMS forwarding relies on control of the Android device, its automation, and the
bridge secret. Sender names alone are not bank cryptographic verification. Do not
describe this as an official Vodafone integration or give customers bridge access.
