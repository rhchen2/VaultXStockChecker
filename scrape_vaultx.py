#!/usr/bin/env python3
"""
VaultX Zip Binder stock checker.

Scrapes the Vault X US B2B "Zip Binders" collection (a Shopify storefront),
walking every size (product) and every color (variant), and produces a PDF
report listing what is in stock and the cost of each item.

Shopify exposes a public `products.json` endpoint per collection that returns
all products, their variants, prices and an `available` flag - no scraping of
rendered HTML required.

Usage:
    py scrape_vaultx.py
    py scrape_vaultx.py --collection zip-binders --out VaultX_Stock.pdf
    py scrape_vaultx.py --all   # include out-of-stock items in the report
"""

import argparse
import datetime as dt
import sys
import time

import requests

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)

BASE_URL = "https://us.b2b.vaultx.com"
DEFAULT_COLLECTION = "zip-binders"
HEADERS = {"User-Agent": "Mozilla/5.0 (VaultXStockChecker; +https://github.com/rhchen2)"}


def fetch_products(collection, base_url=BASE_URL):
    """Return all products in a Shopify collection via the public products.json API.

    Pages through results until an empty page is returned.
    """
    products = []
    page = 1
    while True:
        url = f"{base_url}/collections/{collection}/products.json"
        params = {"limit": 250, "page": page}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        batch = resp.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
        if len(batch) < 250:
            break
        page += 1
        time.sleep(0.5)  # be polite
    return products


def build_rows(products):
    """Flatten products/variants into a list of dicts: one row per size+color.

    Each product is a "size" (e.g. 9-Pocket, 12-Pocket XL); each variant is a
    "color"/edition.
    """
    rows = []
    for p in products:
        size = p.get("title", "").strip()
        tags = {t.lower() for t in p.get("tags", [])}
        # Shopify marks pre-order / drop variants as available:true even though
        # there's no physical inventory, and these don't show in the normal
        # collection grid. Treat them as a separate "pre-order" status.
        is_preorder = bool(tags & {"pre-order", "preorder", "drop"})
        for v in p.get("variants", []):
            color = v.get("option1") or v.get("title") or ""
            price = v.get("price")
            try:
                price_val = float(price)
            except (TypeError, ValueError):
                price_val = None
            available = bool(v.get("available"))
            if not available:
                status = "Sold Out"
            elif is_preorder:
                status = "Pre-Order"
            else:
                status = "In Stock"
            rows.append(
                {
                    "size": size,
                    "color": color.strip(),
                    "sku": v.get("sku") or "",
                    "price": price_val,
                    "available": available,
                    "status": status,
                }
            )
    return rows


def fmt_price(price):
    return f"${price:,.2f}" if price is not None else "-"


def ascii_safe(text):
    """Strip characters the Windows console can't encode (e.g. the (R) symbol).

    Only used for console output; the PDF keeps the full Unicode text.
    """
    return text.encode("ascii", "replace").decode("ascii")


def build_pdf(rows, out_path, collection, include_oos=False):
    """Render the stock report to a PDF."""
    in_stock = [r for r in rows if r["status"] == "In Stock"]
    preorder = [r for r in rows if r["status"] == "Pre-Order"]
    out_stock = [r for r in rows if r["status"] == "Sold Out"]

    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="VaultX Zip Binder Stock Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleBig", parent=styles["Title"], fontSize=20, spaceAfter=4
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6
    )

    story = []
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    story.append(Paragraph("Vault X &mdash; Zip Binder Stock Report", title_style))
    story.append(
        Paragraph(
            f"Collection: <b>{collection}</b> &nbsp;|&nbsp; Source: {BASE_URL} "
            f"&nbsp;|&nbsp; Generated: {now}",
            sub_style,
        )
    )
    summary = f"{len(in_stock)} of {len(rows)} size/color combinations in stock."
    if preorder:
        summary += f" {len(preorder)} available as pre-order/drop."
    story.append(Paragraph(summary, sub_style))
    story.append(Spacer(1, 0.15 * inch))

    def make_table(data_rows, accent_hex="#1b5e20"):
        header = ["Size / Product", "Color", "SKU", "Price", "Status"]
        table_data = [header]
        for r in data_rows:
            table_data.append(
                [
                    r["size"],
                    r["color"],
                    r["sku"],
                    fmt_price(r["price"]),
                    r["status"],
                ]
            )
        tbl = Table(
            table_data,
            colWidths=[2.4 * inch, 1.5 * inch, 1.4 * inch, 0.85 * inch, 0.9 * inch],
            repeatRows=1,
        )
        accent = colors.HexColor(accent_hex)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (3, 0), (4, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        tbl.setStyle(TableStyle(style))
        return tbl

    # In-stock section
    story.append(Paragraph("In Stock", section_style))
    if in_stock:
        in_stock_sorted = sorted(in_stock, key=lambda r: (r["size"], r["color"]))
        story.append(make_table(in_stock_sorted, accent_hex="#1b5e20"))
    else:
        story.append(Paragraph("Nothing currently in stock.", styles["Normal"]))

    # Pre-order / drop section
    if preorder:
        pre_sorted = sorted(preorder, key=lambda r: (r["size"], r["color"]))
        story.append(Paragraph("Pre-Order / Drops", section_style))
        story.append(
            Paragraph(
                "These are listed as orderable on Shopify but are pre-order/drop "
                "items, so they do not appear in the normal collection grid.",
                sub_style,
            )
        )
        story.append(Spacer(1, 0.06 * inch))
        story.append(make_table(pre_sorted, accent_hex="#9a6a00"))

    # Out-of-stock section (optional)
    if include_oos and out_stock:
        out_sorted = sorted(out_stock, key=lambda r: (r["size"], r["color"]))
        story.append(Paragraph("Out of Stock", section_style))
        story.append(make_table(out_sorted, accent_hex="#7f1d1d"))

    doc.build(story)


def main():
    parser = argparse.ArgumentParser(description="VaultX zip binder stock -> PDF")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION,
                        help="Shopify collection handle (default: zip-binders)")
    parser.add_argument("--out", default="VaultX_Stock_Report.pdf",
                        help="Output PDF path")
    parser.add_argument("--all", action="store_true", dest="include_oos",
                        help="Include out-of-stock items in the report")
    args = parser.parse_args()

    print(f"Fetching collection '{args.collection}' from {BASE_URL} ...")
    try:
        products = fetch_products(args.collection)
    except requests.RequestException as e:
        print(f"ERROR fetching products: {e}", file=sys.stderr)
        return 1

    if not products:
        print("No products returned. Check the collection handle.", file=sys.stderr)
        return 1

    rows = build_rows(products)
    in_stock = sum(1 for r in rows if r["status"] == "In Stock")
    preorder = sum(1 for r in rows if r["status"] == "Pre-Order")
    print(f"Found {len(products)} products / {len(rows)} size+color combos "
          f"({in_stock} in stock, {preorder} pre-order/drop).")

    # Console summary
    for r in sorted(rows, key=lambda r: (r["size"], r["color"])):
        if r["status"] == "In Stock":
            line = f"  [IN STOCK]  {r['size']} - {r['color']} : {fmt_price(r['price'])}"
            print(ascii_safe(line))
        elif r["status"] == "Pre-Order":
            line = f"  [PRE-ORDER] {r['size']} - {r['color']} : {fmt_price(r['price'])}"
            print(ascii_safe(line))

    build_pdf(rows, args.out, args.collection, include_oos=args.include_oos)
    print(f"PDF written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
