# Ishtiraki Plus

Arabic digital subscription storefront built with React, TanStack Start and Vite.

## Development

Use Node.js 22.13 or newer. Install with `npm ci`.

For the cloud-connected storefront, configure the Supabase environment variables from `.env.example` locally, then run `npm run dev`.

For separate local accounts without email confirmation, run `npm run dev:local` and open http://127.0.0.1:5173. See LOCAL-ACCOUNTS.md for scope and storage details. Local accounts and their SQLite database are never part of production deployments.

## Build and checks

- `npm run build`
- `npx tsc --noEmit`
- `node --test scripts/local-auth.test.mjs`

## Brand assets

The logo and 24 subscription artworks are in `public/images`. Generation prompts are recorded in `scripts/generated-images-manifest.json`. Product artwork is selected by service identity in `src/lib/product-artwork.ts`.

## Lovable sync

Uploading this repository to GitHub does not by itself connect it to an existing Lovable project. Changes sync only when Lovable is explicitly linked to this repository and branch. Publish the reviewed version through Lovable after synchronization. The cloud environment must provide the project's existing Supabase and Lovable email configuration.

The previous bot project is retained in Git history.
