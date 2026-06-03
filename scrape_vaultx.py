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


def load_har_session(har_path):
    """Extract the logged-in session Cookie (and User-Agent) from a HAR file.

    The B2B catalog pricing (per-item price + quantity breaks) is only returned
    by Shopify when the request carries the logged-in company session, so we
    reuse the cookies the browser captured in the HAR.
    """
    import json
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    cookie = None
    user_agent = None
    for entry in har["log"]["entries"]:
        if "us.b2b.vaultx.com" not in entry["request"]["url"]:
            continue
        for h in entry["request"]["headers"]:
            name = h["name"].lower()
            if name == "cookie" and h["value"]:
                cookie = h["value"]
            elif name == "user-agent" and h["value"]:
                user_agent = h["value"]
        if cookie:
            break
    if not cookie:
        raise ValueError("No session cookie found in HAR for us.b2b.vaultx.com")
    return cookie, user_agent or HEADERS["User-Agent"]


def fetch_b2b_pricing(products, cookie, user_agent, base_url=BASE_URL):
    """Fetch per-variant B2B pricing via the authenticated /products/<handle>.js.

    Returns a dict keyed by SKU:
        {sku: {"min1": float, "breaks": [(min_qty, price_float), ...]}}
    Prices in the .js endpoint are integer cents.
    """
    pricing = {}
    headers = {"Cookie": cookie, "User-Agent": user_agent,
               "Accept": "application/json"}
    for p in products:
        handle = p.get("handle")
        if not handle:
            continue
        url = f"{base_url}/products/{handle}.js"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(ascii_safe(f"  warning: could not fetch B2B pricing for "
                             f"{handle}: {e}"), file=sys.stderr)
            continue
        for v in data.get("variants", []):
            sku = v.get("sku")
            if not sku:
                continue
            breaks = [
                (b.get("minimum_quantity"), b.get("price", 0) / 100.0)
                for b in (v.get("quantity_price_breaks") or [])
                if b.get("minimum_quantity")
            ]
            breaks.sort(key=lambda x: x[0])
            pricing[sku] = {
                "min1": (v.get("price") or 0) / 100.0,
                "breaks": breaks,
            }
        time.sleep(0.3)  # be polite
    return pricing


def build_rows(products, b2b_map=None):
    """Flatten products/variants into a list of dicts: one row per size+color.

    Each product is a "size" (e.g. 9-Pocket, 12-Pocket XL); each variant is a
    "color"/edition. ``price`` is the public MSRP. If ``b2b_map`` (keyed by SKU)
    is supplied, each row also gets ``b2b_min1`` and ``b2b_breaks``.
    """
    b2b_map = b2b_map or {}
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
            sku = v.get("sku") or ""
            b2b = b2b_map.get(sku)
            rows.append(
                {
                    "size": size,
                    "color": color.strip(),
                    "sku": sku,
                    "price": price_val,  # public MSRP
                    "available": available,
                    "status": status,
                    "b2b_min1": b2b["min1"] if b2b else None,
                    "b2b_breaks": b2b["breaks"] if b2b else [],
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
    # Cell styles so long text wraps within its column instead of overflowing.
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"], fontSize=9, leading=11
    )
    cell_header_style = ParagraphStyle(
        "CellHeader", parent=styles["Normal"], fontSize=9, leading=11,
        textColor=colors.white, fontName="Helvetica-Bold",
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
    has_b2b_summary = any(r.get("b2b_min1") is not None for r in rows)
    summary = f"{len(in_stock)} of {len(rows)} size/color combinations in stock."
    if preorder:
        summary += f" {len(preorder)} available as pre-order/drop."
    story.append(Paragraph(summary, sub_style))
    if has_b2b_summary:
        story.append(
            Paragraph(
                "Pricing shown is your B2B account pricing: <b>1+ (ea)</b> = price "
                "per item, <b>Volume (ea)</b> = discounted price at the listed "
                "quantity, <b>MSRP</b> = retail price.",
                sub_style,
            )
        )
    story.append(Spacer(1, 0.15 * inch))

    def esc(text):
        return (str(text).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    has_b2b = any(r.get("b2b_min1") is not None for r in rows)

    def volume_cell(r):
        """Render the quantity price breaks (e.g. '12+  $16.69') for a row."""
        breaks = r.get("b2b_breaks") or []
        if not breaks:
            return Paragraph("&ndash;", cell_style)
        lines = [f"{q}+&nbsp;&nbsp;{fmt_price(p)}" for q, p in breaks]
        return Paragraph("<br/>".join(lines), cell_style)

    def make_table(data_rows, accent_hex="#1b5e20"):
        if has_b2b:
            cols = ["Size / Product", "Color", "SKU",
                    "1+ (ea)", "Volume (ea)", "MSRP", "Status"]
            col_widths = [1.9, 1.0, 1.2, 0.62, 1.0, 0.66, 0.72]
        else:
            cols = ["Size / Product", "Color", "SKU", "Price", "Status"]
            col_widths = [2.3, 1.35, 1.4, 0.8, 0.85]
        header = [Paragraph(h, cell_header_style) for h in cols]
        table_data = [header]
        for r in data_rows:
            base = [
                Paragraph(esc(r["size"]), cell_style),
                Paragraph(esc(r["color"]), cell_style),
                Paragraph(esc(r["sku"]), cell_style),
            ]
            if has_b2b:
                base += [
                    fmt_price(r.get("b2b_min1")),
                    volume_cell(r),
                    fmt_price(r["price"]),
                    r["status"],
                ]
            else:
                base += [fmt_price(r["price"]), r["status"]]
            table_data.append(base)
        tbl = Table(
            table_data,
            colWidths=[w * inch for w in col_widths],
            repeatRows=1,
        )
        accent = colors.HexColor(accent_hex)
        price_cols_start = 3  # first numeric/status column
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (price_cols_start, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
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
    parser.add_argument("--har", default=None,
                        help="Path to a HAR file from a logged-in us.b2b.vaultx.com "
                             "session; adds B2B per-item pricing (1+, volume, MSRP)")
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

    b2b_map = None
    if args.har:
        print(f"Loading B2B session from HAR: {args.har}")
        try:
            cookie, user_agent = load_har_session(args.har)
            print(f"Fetching B2B pricing for {len(products)} products ...")
            b2b_map = fetch_b2b_pricing(products, cookie, user_agent)
            print(f"Got B2B pricing for {len(b2b_map)} variants.")
        except (OSError, ValueError) as e:
            print(f"ERROR loading B2B pricing from HAR: {e}", file=sys.stderr)
            print("Continuing with public (MSRP) pricing only.", file=sys.stderr)

    rows = build_rows(products, b2b_map=b2b_map)
    in_stock = sum(1 for r in rows if r["status"] == "In Stock")
    preorder = sum(1 for r in rows if r["status"] == "Pre-Order")
    print(f"Found {len(products)} products / {len(rows)} size+color combos "
          f"({in_stock} in stock, {preorder} pre-order/drop).")

    # Console summary
    def price_str(r):
        if r.get("b2b_min1") is not None:
            s = f"1+ {fmt_price(r['b2b_min1'])}"
            for q, p in r.get("b2b_breaks", []):
                s += f" / {q}+ {fmt_price(p)}"
            s += f" (MSRP {fmt_price(r['price'])})"
            return s
        return fmt_price(r["price"])

    for r in sorted(rows, key=lambda r: (r["size"], r["color"])):
        tag = {"In Stock": "[IN STOCK] ", "Pre-Order": "[PRE-ORDER]"}.get(r["status"])
        if tag:
            line = f"  {tag} {r['size']} - {r['color']} : {price_str(r)}"
            print(ascii_safe(line))

    build_pdf(rows, args.out, args.collection, include_oos=args.include_oos)
    print(f"PDF written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
