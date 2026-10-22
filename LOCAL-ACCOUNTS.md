# Local accounts

Run `npm run dev:local` with Node.js 22.13 or newer. Open http://127.0.0.1:5173.

This development mode stores accounts and hashed session tokens in `.local/accounts.sqlite`. Passwords use salted scrypt hashes. Sessions use HttpOnly, SameSite=Strict cookies and expire after seven days. Changing a password requires the current password and revokes previous sessions. Signup does not send confirmation email. Phone is optional.

The database is excluded from source control and blocked from Vite file serving. Keep this folder when restarting to retain accounts. Do not delete it to fix login problems.

These accounts are separate from Lovable/Supabase. Existing cloud accounts, orders, balances, checkout, admin tools and email recovery have not been migrated. Product listings still come from the existing product service. Local accounts do not authorize access to cloud data.

`npm run dev` and production builds continue using cloud authentication. The local auth API runs only in the explicitly enabled Vite development server and is not included as a production authentication service.

Run `node --test scripts/local-auth.test.mjs` to check authentication, account isolation, CSRF checks, session invalidation and password changes.
