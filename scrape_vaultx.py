#!/usr/bin/env python3
"""
VaultX Zip Binder stock checker.

Scrapes the Vault X US B2B "Zip Binders" collection (a Shopify B2B storefront),
walking every size (product) and every color (variant), and produces a PDF
report listing what is in stock and the cost of each item.

The B2B storefront is login-gated: anonymously, Shopify only exposes the
products published to the public online-store channel (MSRP + public
availability - effectively the B2C view). With --har (a capture from a
logged-in us.b2b.vaultx.com session) the scraper instead walks the B2B
collection page as your company sees it and reads each product's
authenticated /products/<handle>.js, so the product list, stock status AND
pricing (1+/volume) all come from the B2B catalog.

Usage:
    py scrape_vaultx.py --har session.har   # true B2B catalog + pricing
    py scrape_vaultx.py                     # public (MSRP-only) fallback
    py scrape_vaultx.py --all               # include out-of-stock items
"""

import argparse
import datetime as dt
import re
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


def get_with_retry(url, retries=3, **kwargs):
    """requests.get that retries polite-style on 429 (honours Retry-After)."""
    for attempt in range(retries):
        resp = requests.get(url, timeout=30, **kwargs)
        if resp.status_code != 429 or attempt == retries - 1:
            resp.raise_for_status()
            return resp
        wait = min(int(resp.headers.get("Retry-After") or 5), 60)
        print(f"  rate-limited (429) on {url}; retrying in {wait}s ...",
              file=sys.stderr)
        time.sleep(wait)


def fetch_products(collection, base_url=BASE_URL):
    """Return all products in a Shopify collection via the public products.json API.

    Pages through results until an empty page is returned.
    """
    products = []
    page = 1
    while True:
        url = f"{base_url}/collections/{collection}/products.json"
        params = {"limit": 250, "page": page}
        resp = get_with_retry(url, params=params, headers=HEADERS)
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


def extract_handles(html, collection):
    """Return product handles linked from a rendered collection page, in order.

    Prefers links scoped to the collection (/collections/<c>/products/<h>) so
    nav/recommendation links elsewhere on the page don't leak in; falls back to
    bare /products/<h> links for themes that don't scope product-card URLs.
    """
    scoped = rf'href="[^"]*/collections/{re.escape(collection)}/products/([a-z0-9][a-z0-9_-]*)'
    handles = re.findall(scoped, html)
    if not handles:
        handles = re.findall(r'href="[^"]*/products/([a-z0-9][a-z0-9_-]*)', html)
    return list(dict.fromkeys(handles))


def msrp_map(products):
    """Map SKU -> MSRP (float) from a public products.json product list."""
    out = {}
    for p in products:
        for v in p.get("variants", []):
            sku = v.get("sku")
            try:
                price = float(v.get("price"))
            except (TypeError, ValueError):
                continue
            if sku:
                out[sku] = price
    return out


def normalize_js_product(data, msrp_by_sku=None):
    """Convert an authenticated /products/<handle>.js payload into the
    products.json-like shape build_rows() expects, plus its B2B pricing.

    In the .js endpoint prices are integer cents and, for a logged-in B2B
    session, ``price`` is your account's 1+ price while ``compare_at_price``
    (when set) is retail. MSRP is taken from ``msrp_by_sku`` (the public feed)
    first since B2B-only products often have no compare_at_price.

    Returns (product_dict, {sku: {"min1": float, "breaks": [(qty, price)]}}).
    """
    msrp_by_sku = msrp_by_sku or {}
    variants = []
    pricing = {}
    for v in data.get("variants", []):
        sku = v.get("sku") or ""
        options = v.get("options") or []
        color = v.get("option1") or (options[0] if options else "") or v.get("title") or ""
        msrp = msrp_by_sku.get(sku)
        if msrp is None and v.get("compare_at_price"):
            msrp = v["compare_at_price"] / 100.0
        variants.append({
            "sku": sku,
            "option1": color,
            "title": v.get("title") or "",
            "price": msrp,
            "available": bool(v.get("available")),
        })
        if sku:
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
    product = {
        "title": data.get("title", ""),
        "handle": data.get("handle", ""),
        "tags": data.get("tags") or [],
        "variants": variants,
    }
    return product, pricing


def fetch_b2b_catalog(collection, cookie, user_agent, msrp_by_sku=None,
                      base_url=BASE_URL, max_pages=20):
    """Fetch the collection as the logged-in B2B company sees it.

    Walks the rendered collection pages (they're empty without a session) to
    enumerate product handles, then reads each authenticated
    /products/<handle>.js for variants, B2B availability and B2B pricing.

    Returns (products, pricing) suitable for build_rows(products, pricing).
    Raises ValueError if the session shows no products (expired cookie).
    """
    headers = {"Cookie": cookie, "User-Agent": user_agent}
    handles = []
    for page in range(1, max_pages + 1):
        resp = get_with_retry(f"{base_url}/collections/{collection}",
                              params={"page": page}, headers=headers)
        new = [h for h in extract_handles(resp.text, collection)
               if h not in handles]
        if not new:
            break
        handles.extend(new)
        time.sleep(0.5)  # be polite
    if not handles:
        raise ValueError(
            f"No products visible at {base_url}/collections/{collection} with "
            "this session - the B2B login has likely expired. Capture a fresh HAR.")

    products = []
    pricing = {}
    js_headers = dict(headers, Accept="application/json")
    for handle in handles:
        try:
            resp = get_with_retry(f"{base_url}/products/{handle}.js",
                                  headers=js_headers)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(ascii_safe(f"  warning: could not fetch B2B product "
                             f"{handle}: {e}"), file=sys.stderr)
            continue
        product, p = normalize_js_product(data, msrp_by_sku)
        products.append(product)
        pricing.update(p)
        time.sleep(0.3)  # be polite
    return products, pricing


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


def build_discord_summary(rows, collection):
    """Build a compact Discord message summarising in-stock items + pricing.

    One line per size, listing the in-stock colors and the price tiers
    (B2B 1+/volume if available, otherwise MSRP). Kept under Discord's 2000
    character limit.
    """
    in_stock = [r for r in rows if r["status"] == "In Stock"]
    preorder = [r for r in rows if r["status"] == "Pre-Order"]
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"**Vault X — {collection} stock**  ({now})",
        f"{len(in_stock)} of {len(rows)} size/color combos in stock"
        + (f", {len(preorder)} pre-order/drop." if preorder else "."),
        "",
    ]

    # Group by size, preserving sorted order.
    by_size = {}
    for r in sorted(in_stock, key=lambda r: (r["size"], r["color"])):
        by_size.setdefault(r["size"], []).append(r)

    for size, items in by_size.items():
        colors_list = ", ".join(i["color"] for i in items)
        sample = items[0]
        if sample.get("b2b_min1") is not None:
            price = f"1+ {fmt_price(sample['b2b_min1'])}"
            for q, p in sample.get("b2b_breaks", []):
                price += f" / {q}+ {fmt_price(p)}"
        else:
            price = fmt_price(sample["price"])
        line = f"• **{size}** — {colors_list} — {price}"
        lines.append(line)

    content = "\n".join(lines)
    # Discord hard limit is 2000 chars for `content`.
    if len(content) > 1990:
        content = content[:1985] + "\n…"
    return content


def post_to_discord(webhook_url, pdf_path, rows, collection):
    """Post the summary message with the PDF attached to a Discord webhook."""
    import json
    content = build_discord_summary(rows, collection)
    payload = {"content": content, "username": "VaultX Stock Checker"}
    with open(pdf_path, "rb") as fh:
        files = {"file": ("VaultX_Stock_Report.pdf", fh, "application/pdf")}
        data = {"payload_json": json.dumps(payload)}
        resp = requests.post(webhook_url, data=data, files=files, timeout=30)
    resp.raise_for_status()
    return resp.status_code


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
                             "session; scrapes the B2B catalog (product list, "
                             "availability AND 1+/volume pricing) instead of the "
                             "public online-store feed")
    parser.add_argument("--discord-webhook", default=None,
                        help="Discord webhook URL to post the summary + PDF to. "
                             "Falls back to the VAULTX_DISCORD_WEBHOOK env var.")
    args = parser.parse_args()

    import os
    webhook = args.discord_webhook or os.environ.get("VAULTX_DISCORD_WEBHOOK")

    print(f"Fetching public collection '{args.collection}' from {BASE_URL} ...")
    products = []
    try:
        products = fetch_products(args.collection)
    except requests.RequestException as e:
        print(f"ERROR fetching public products: {e}", file=sys.stderr)
        if not args.har:
            return 1

    b2b_map = None
    if args.har:
        print(f"Loading B2B session from HAR: {args.har}")
        try:
            cookie, user_agent = load_har_session(args.har)
            print("Fetching the B2B collection as your logged-in company ...")
            products, b2b_map = fetch_b2b_catalog(
                args.collection, cookie, user_agent, msrp_map(products))
            print(f"B2B catalog: {len(products)} products, "
                  f"pricing for {len(b2b_map)} variants.")
        except (OSError, ValueError, requests.RequestException) as e:
            print(f"ERROR fetching B2B catalog: {e}", file=sys.stderr)
            if not products:
                return 1
            print("Continuing with the public catalog (MSRP + public "
                  "availability) only.", file=sys.stderr)

    if not products:
        print("No products returned. Check the collection handle.", file=sys.stderr)
        return 1

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

    if webhook:
        print("Posting report to Discord webhook ...")
        try:
            code = post_to_discord(webhook, args.out, rows, args.collection)
            print(f"Posted to Discord (HTTP {code}).")
        except requests.RequestException as e:
            print(f"ERROR posting to Discord: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
