# VaultX Stock Checker

Scrapes the [Vault X US B2B "Zip Binders" collection](https://us.b2b.vaultx.com/collections/zip-binders)
and generates a PDF report of every size and color, showing **what is in stock and the cost of each item**.

## How it works

The store runs on Shopify, which exposes a public `products.json` endpoint per
collection. The script reads that JSON directly (no HTML scraping / browser
needed), so it's fast and reliable:

- Each **product** = a size (9-Pocket, 12-Pocket, 4-Pocket, 12-Pocket XL,
  16-Pocket XXL, plus Metallic and ME4 editions).
- Each **variant** = a color/edition, with its `price` and `available` flag.

It walks every size and every color, then builds a PDF with an **In Stock**
table (size, color, SKU, price, status). Use `--all` to also append an
**Out of Stock** section.

## Setup

```sh
py -m pip install -r requirements.txt
```

## Usage

```sh
# Default: zip-binders collection -> VaultX_Stock_Report.pdf (in-stock only)
py scrape_vaultx.py

# Include out-of-stock items too
py scrape_vaultx.py --all

# Different collection or output file
py scrape_vaultx.py --collection deck-boxes --out DeckBoxes.pdf
```

## B2B account pricing (`--har`)

The public endpoints only expose the MSRP. The discounted B2B pricing
(per-item `1+` price and quantity-break/`Volume` price) is only returned when
the request carries your logged-in company session. To include it:

1. Log in at `us.b2b.vaultx.com` so you can see your pricing.
2. Open any product page, press **F12 -> Network**, tick **Preserve log**,
   and reload the page.
3. Right-click the request list -> **Save all as HAR with content** and save
   the `.har` file.
4. Run with `--har`:

   ```sh
   py scrape_vaultx.py --all --har "path/to/session.har" --out VaultX_Stock_B2B.pdf
   ```

The script reads the session cookie from the HAR, then fetches
`/products/<handle>.js` for every product to get each variant's `1+` price,
volume breaks, and quantity rule. The PDF then shows **1+ (ea) | Volume (ea) |
MSRP** columns.

> The session expires, so re-capture the HAR when pricing stops coming through.
> `*.har` is git-ignored and never committed (it contains session tokens).

## Post to a Discord channel

Post a summary message (grouped by size, with B2B pricing when `--har` is used)
and attach the PDF to a Discord channel via a webhook.

1. In Discord: **Channel -> Edit Channel -> Integrations -> Webhooks ->
   New Webhook -> Copy Webhook URL**.
2. Provide the URL via the `VAULTX_DISCORD_WEBHOOK` env var (keeps it out of
   shell history) or the `--discord-webhook` flag, then run as normal:

   ```powershell
   $env:VAULTX_DISCORD_WEBHOOK = "https://discord.com/api/webhooks/XXXX/YYYY"
   py scrape_vaultx.py --all --har "session.har" --out VaultX_Stock_B2B.pdf
   ```

   ```sh
   # or pass it directly
   py scrape_vaultx.py --discord-webhook "https://discord.com/api/webhooks/XXXX/YYYY"
   ```

> A webhook URL is a secret - anyone with it can post to that channel. Don't
> commit it; rotate it in Discord if it leaks.

## Web front-end

A static page in [`web/`](web/) displays the stock from a hard-coded snapshot
(`web/data.js`) — grouped by size, with In-stock/Pre-order/Sold-out badges,
pricing, an in-stock/show-all toggle, and search. No backend or database.

**Live:** https://web-five-lyart-32.vercel.app/

Rebuild the snapshot and (re)deploy:

```sh
# Public/MSRP snapshot (matches the daily auto-update)
py build_web_data.py            # regenerates web/data.js
cd web && npx vercel deploy --prod

# Snapshot WITH your B2B 1+/volume pricing, then deploy, in one command
py make_b2b_site.py             # auto-detects the newest *.har, deploys
py make_b2b_site.py --no-deploy # rebuild web/data.js only
```

> The clean URL `vaultx-stock-tracker.vercel.app` is gated by Vercel
> Deployment Protection (returns 401). To make it public, disable it in
> *Vercel → Project → Settings → Deployment Protection*. The generated
> `web-five-lyart-32.vercel.app` domain is public regardless.

## Daily auto-update (GitHub Actions)

[`.github/workflows/update-stock.yml`](.github/workflows/update-stock.yml) runs
daily (13:00 UTC), regenerates the **public** snapshot, commits it only if it
changed, and redeploys to Vercel.

One-time setup — add a repo secret so the job can deploy:

1. Create a token at https://vercel.com/account/tokens.
2. Repo **Settings → Secrets and variables → Actions → New repository secret**,
   name `VERCEL_TOKEN`, paste the token.

The Vercel project/org IDs are already in the workflow (they aren't secrets).
Trigger a manual run from the **Actions** tab to test. The auto-updates are
public/MSRP-only so they run unattended; use `make_b2b_site.py` to refresh the
live site with B2B pricing on demand (the next daily run reverts it to public).

## Notes

- Without `--har`, prices are the public MSRP from the storefront listing.
- The same script works for any Vault X collection by passing `--collection`
  with the collection's handle (the slug in its URL).
- Pre-order/drop products (e.g. the ME4 editions) have no `.js` pricing
  endpoint, so they fall back to MSRP and appear in the Pre-Order section.
