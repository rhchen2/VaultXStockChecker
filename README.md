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

## Notes

- Prices come from the public storefront listing. If you need account-specific
  B2B pricing you'd have to authenticate, which this script does not do.
- The same script works for any Vault X collection by passing `--collection`
  with the collection's handle (the slug in its URL).
