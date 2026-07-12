# VaultX Stock Checker

Scrapes the [Vault X US B2B "Zip Binders" collection](https://us.b2b.vaultx.com/collections/zip-binders)
and generates a PDF report of every size and color, showing **what is in stock and the cost of each item**.

## How it works

The store runs on Shopify **B2B**, which is login-gated: anonymously, Shopify
only exposes the products published to the public online-store channel (MSRP
prices and public availability — effectively the B2C view). So the scraper has
two modes:

- **B2B mode (`--har`, recommended):** walks the
  [B2B collection page](https://us.b2b.vaultx.com/collections/zip-binders) with
  your logged-in company session to enumerate every product your account can
  buy, then reads each authenticated `/products/<handle>.js` for per-variant
  **B2B availability** and **B2B pricing** (1+ and volume breaks).
- **Public fallback (no `--har`):** reads the anonymous
  `products.json` feed — only the publicly published subset, MSRP-only.

- Each **product** = a size (9-Pocket, 12-Pocket, 4-Pocket, 12-Pocket XL,
  16-Pocket XXL, plus Metallic and ME4 editions).
- Each **variant** = a color/edition, with its price and `available` flag.

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

## B2B catalog & pricing (`--har`)

The public endpoints only expose the MSRP and the publicly published subset of
products. The real B2B catalog — the full product list, its stock status, and
the discounted pricing (per-item `1+` price and quantity-break/`Volume`
price) — is only returned when the request carries your logged-in company
session. To scrape it:

1. Log in at `us.b2b.vaultx.com` so you can see your pricing.
2. Open any product page, press **F12 -> Network**, tick **Preserve log**,
   and reload the page.
3. Right-click the request list -> **Save all as HAR with content** and save
   the `.har` file.
4. Run with `--har`:

   ```sh
   py scrape_vaultx.py --all --har "path/to/session.har" --out VaultX_Stock_B2B.pdf
   ```

The script reads the session cookie from the HAR, enumerates the collection as
your company sees it, then fetches `/products/<handle>.js` for every product to
get each variant's availability, `1+` price, and volume breaks. The PDF then
shows **1+ (ea) | Volume (ea) | MSRP** columns.

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

## Orders page (PII-free)

[`web/orders.html`](web/orders.html) shows order contents and totals with **all
PII omitted** (no name, email, company, address or payment). The order **status
is highlighted** as the headline, with this rule: an order is **"Shipped" only
if it has a tracking number** — otherwise it stays **Confirmed** (a carrier
status with no tracking shows "awaiting tracking #").

Two ways to add/update an order:

- **Paste on the page:** the Orders page has a paste box — paste the VaultX order
  page and it renders a PII-free view in your browser (nothing uploaded). Good
  for a quick look; not saved.
- **Save + deploy with `update_orders.py`:** the order portal is behind your
  login, so this runs **locally on demand** (not in the cron). Capture the order
  as text or a HAR, then:

  ```sh
  py update_orders.py --text order.txt     # paste the order page into a .txt
  py update_orders.py --har order.har       # or a HAR of the order page
  py update_orders.py --text order.txt --no-deploy
  ```

  It parses only non-PII fields (products, qty, prices, totals, status,
  tracking #), upserts the order into `web/orders.js` by order number, and
  deploys. Re-run when a status changes.

> Why not in the cron? The order portal requires login and B2B sessions expire,
> so it can't run unattended like the public stock job. If your portal serves
> orders via a JSON API (rather than HTML), send a HAR and the parser can be
> adapted to it.

## Daily auto-update (GitHub Actions)

[`.github/workflows/update-stock.yml`](.github/workflows/update-stock.yml) runs
daily (13:00 UTC), runs the tests, regenerates the snapshot, commits it only if
it changed, and redeploys to Vercel.

One-time setup — add a repo secret so the job can deploy:

1. Create a token at https://vercel.com/account/tokens.
2. Repo **Settings → Secrets and variables → Actions → New repository secret**,
   name `VERCEL_TOKEN`, paste the token.

The Vercel project/org IDs are already in the workflow (they aren't secrets).
Trigger a manual run from the **Actions** tab to test.

**Optional — B2B data in the daily job:** add a second secret,
`VAULTX_B2B_COOKIE`, containing the raw `Cookie` header from a logged-in
`us.b2b.vaultx.com` request (F12 → Network → any request → copy the `Cookie`
header value). While the session is valid, the daily snapshot uses the true B2B
catalog, availability and pricing; when it expires, the job logs a warning and
falls back to the public/MSRP feed. Refresh the secret whenever that happens —
or automate it (below), or use `make_b2b_site.py` to refresh the site on demand.

### Automated cookie refresh (`refresh_cookie.py`)

The B2B store uses Shopify's passwordless accounts (email + 6-digit code), so
a login can't simply be scripted with stored credentials. Instead
`refresh_cookie.py` keeps a **persistent logged-in browser profile** alive:
Shopify sessions renew on use and only expire when idle, so a daily visit from
the same profile stays logged in indefinitely. Each run verifies the session
(products actually visible on the B2B collection), extracts the cookies, and
updates the `VAULTX_B2B_COOKIE` repo secret via the `gh` CLI.

```sh
# one-time: install deps + authenticate gh
py -m pip install playwright && py -m playwright install chromium
gh auth login

# one-time: opens a visible browser - log in (email + code) when it appears
py refresh_cookie.py --setup

# test a refresh without touching the secret, then for real
py refresh_cookie.py --no-push
py refresh_cookie.py
```

Schedule it daily (before the 13:00 UTC stock job) on any always-on machine:

```powershell
schtasks /Create /SC DAILY /ST 06:30 /TN VaultXCookieRefresh /TR "py C:\path\to\VaultXStockChecker\refresh_cookie.py"
```

If a run reports it's not logged in (Shopify forced a re-auth - rare), just
run `--setup` again. The profile lives in the git-ignored `.browser-profile/`
directory; treat it like a password. Use `--headed` if headless runs get
blocked by bot protection.

## Notes

- Without `--har`, prices are the public MSRP and availability reflects the
  public online-store channel, which can differ from your B2B catalog.
- Run the tests with `py -m pip install -r requirements-dev.txt && py -m pytest`.
- The same script works for any Vault X collection by passing `--collection`
  with the collection's handle (the slug in its URL).
- Pre-order/drop products (e.g. the ME4 editions) have no `.js` pricing
  endpoint, so they fall back to MSRP and appear in the Pre-Order section.
