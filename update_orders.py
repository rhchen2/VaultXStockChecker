#!/usr/bin/env python3
"""
Local, on-demand order-status updater (no cron, no stored credentials).

The VaultX order portal is behind your login, so this can't run unattended.
Instead you capture the order yourself - either a HAR of the order page or a
copied-text file - and this script parses it (PII-free: only products, qty,
prices, totals, status and tracking #), upserts it into web/orders.js, and
optionally deploys.

The "Shipped" status REQUIRES a tracking number; otherwise it stays Confirmed.

    py update_orders.py --text order.txt          # paste the order page into a .txt
    py update_orders.py --har order.har           # or a HAR of the order page
    py update_orders.py --text order.txt --no-deploy
"""

import argparse
import glob
import html as htmllib
import json
import os
import re
import subprocess
import sys

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
ORDERS_JS = os.path.join(WEB_DIR, "orders.js")
PRODUCT_RE = re.compile(r"(pocket|binder|deck box|exo-?tec|sleeve|holder)", re.I)


def money(s):
    return float(re.sub(r"[^0-9.]", "", s))


def parse_order(text):
    """Parse order text -> dict. Mirrors the browser parser in orders.html.

    Reads ONLY non-PII fields. Names/emails/addresses/payment are never used.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    def m1(pat):
        m = re.search(pat, text, re.I)
        return m.group(1) if m else ""

    number = m1(r"Order\s*#\s*([A-Za-z0-9-]+)")
    statuses = ["Delivered", "Out for delivery", "On its way", "Shipped",
                "Processing", "Confirmed", "Cancelled"]
    status = next((s for s in statuses
                   if re.search(r"\b" + s.replace(" ", r"\s+") + r"\b", text, re.I)), "Order")
    confirmed = m1(r"Confirmed\s*\n?\s*([A-Z][a-z]{2}\s*\d{1,2})")
    paid = m1(r"Paid\s*([A-Z][a-z]{2}\s*\d{1,2})")
    shipping_method = m1(r"Shipping method\s*\n?\s*([^\n$]+?)\s*(?:\n|$)").strip()

    # Tracking (required for Shipped).
    carrier = m1(r"\b(UPS|USPS|FedEx|DHL|OnTrac|Canada Post|Royal Mail)\b") or None
    tnum = m1(r"tracking(?:\s*(?:number|no\.?|#))?\s*[:#-]?\s*\n?\s*([A-Z0-9][A-Z0-9-]{7,40})") or None
    if not tnum:
        tnum = m1(r"\b(1Z[0-9A-Z]{16})\b") or None
    if not tnum and re.search(r"(tracking|ups|usps|fedex|dhl)", text, re.I):
        tnum = m1(r"\b(\d{12,22})\b") or None
    turl = (re.search(r"https?://\S*track\S*", text, re.I) or [None])
    turl = turl.group(0) if hasattr(turl, "group") else None
    tracking = {"number": tnum, "carrier": carrier, "url": turl} if tnum else None

    # Line items: anchor on "$X/ea".
    items = []
    for i, line in enumerate(lines):
        ea_m = re.search(r"\$?\s*([\d,]+\.\d{2})\s*/\s*ea", line, re.I)
        if not ea_m:
            continue
        ea = money(ea_m.group(1))
        total = None
        for j in range(i + 1, min(i + 3, len(lines))):
            t_m = re.match(r"^\$?\s*([\d,]+\.\d{2})\s*(USD)?$", lines[j], re.I)
            if t_m:
                total = money(t_m.group(1))
                break
        color = lines[i - 1] if i >= 1 else ""
        product = lines[i - 2] if i >= 2 else ""
        if not PRODUCT_RE.search(product):
            for k in range(i - 2, max(-1, i - 6), -1):
                if k >= 0 and PRODUCT_RE.search(lines[k]):
                    product = lines[k]
                    break
        qty = round(total / ea) if (ea and total) else 0
        if not qty:
            for k in range(i - 3, max(-1, i - 7), -1):
                if k >= 0 and re.match(r"^\d{1,4}$", lines[k]):
                    qty = int(lines[k])
                    break
        if ea and total and PRODUCT_RE.search(product or ""):
            items.append({"product": product, "color": color, "qty": qty,
                          "ea": round(ea, 2), "total": round(total, 2)})

    def amount_after(label_re):
        for i, line in enumerate(lines):
            if not re.search(label_re, line):
                continue
            same = re.search(r"\$\s*([\d,]+\.\d{2})", line)
            if same:
                return money(same.group(1))
            for j in range(i + 1, min(i + 3, len(lines))):
                if re.search(r"free", lines[j], re.I):
                    return 0.0
                n = re.search(r"\$\s*([\d,]+\.\d{2})", lines[j])
                if n:
                    return money(n.group(1))
        return None

    cnt_m = re.search(r"Subtotal[^\d]*([\d,]+)\s*items", text, re.I)
    item_count = int(cnt_m.group(1).replace(",", "")) if cnt_m else sum(i["qty"] for i in items)
    subtotal = amount_after(r"^Subtotal")
    shipping = amount_after(r"^Shipping$") or 0
    taxes = amount_after(r"^Tax(es)?$") or 0
    total = amount_after(r"^Total")
    if total is None and subtotal is not None:
        total = subtotal + shipping + taxes

    items_complete = (
        subtotal is not None
        and abs(sum(i["total"] for i in items) - subtotal) < 0.01
        and abs(sum(i["qty"] for i in items) - item_count) < 0.5
    )

    timeline = []
    sd = re.search(status.replace(" ", r"\s+") + r"\s*\n?\s*([A-Z][a-z]{2}\s*\d{1,2})", text, re.I)
    if status not in ("Confirmed", "Order") and sd:
        timeline.append({"label": status, "date": sd.group(1)})
    if confirmed:
        timeline.append({"label": "Confirmed", "date": confirmed})

    return {
        "number": number, "status": status, "tracking": tracking,
        "timeline": timeline, "paid": paid, "shippingMethod": shipping_method,
        "items": items, "itemsComplete": items_complete,
        "summary": {"itemCount": item_count, "subtotal": round(subtotal or 0, 2),
                    "shipping": shipping, "taxes": taxes, "total": round(total or 0, 2)},
    }


def html_to_text(s):
    s = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(div|p|li|tr|td|th|h\d|span|section|article)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmllib.unescape(s)
    return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in s.split("\n"))


def text_from_har(har_path):
    har = json.load(open(har_path, encoding="utf-8"))
    best = None
    for e in har["log"]["entries"]:
        c = e.get("response", {}).get("content", {})
        body = c.get("text") or ""
        if not body or "/ea" not in body and "Subtotal" not in body and "Order #" not in body:
            continue
        txt = html_to_text(body) if "html" in (c.get("mimeType") or "") else body
        score = txt.count("/ea") + (1 if "Subtotal" in txt else 0)
        if best is None or score > best[0]:
            best = (score, txt)
    return best[1] if best else ""


def read_existing_orders():
    if not os.path.exists(ORDERS_JS):
        return []
    code = ("const fs=require('fs');"
            "eval(fs.readFileSync(%r,'utf8').replace('const ORDERS','global.ORDERS'));"
            "process.stdout.write(JSON.stringify(ORDERS||[]));" % ORDERS_JS)
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True,
                         shell=(os.name == "nt"))
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        print("Warning: couldn't read existing orders.js; starting fresh.", file=sys.stderr)
        return []


def write_orders_js(orders):
    header = (
        "// Hard-coded VaultX order snapshots for the Orders page.\n"
        "//\n"
        "// PII IS INTENTIONALLY EXCLUDED. Managed by update_orders.py - do not\n"
        "// add customer name, email, company, address or payment here.\n"
        "// \"Shipped\" requires a tracking number; otherwise it stays Confirmed.\n\n"
    )
    with open(ORDERS_JS, "w", encoding="utf-8") as f:
        f.write(header + "const ORDERS = " + json.dumps(orders, ensure_ascii=False, indent=2) + ";\n")


def main():
    p = argparse.ArgumentParser(description="Update order status in web/orders.js (PII-free)")
    p.add_argument("--text", help="A copied-text file of the order page")
    p.add_argument("--har", help="A HAR of the order page (default: newest *.har)")
    p.add_argument("--no-deploy", action="store_true")
    args = p.parse_args()

    if args.text:
        text = open(args.text, encoding="utf-8").read()
    else:
        har = args.har or (max(glob.glob(os.path.join(os.path.dirname(ORDERS_JS), "..", "*.har")),
                               key=os.path.getmtime, default=None))
        if not har or not os.path.exists(har):
            print("ERROR: provide --text FILE or --har FILE (no HAR found).", file=sys.stderr)
            return 1
        print(f"Reading order from HAR: {har}")
        text = text_from_har(har)
        if not text:
            print("ERROR: couldn't find order content in the HAR. The portal may use a\n"
                  "JSON API - send me that HAR and I'll adapt the parser, or use --text.",
                  file=sys.stderr)
            return 1

    order = parse_order(text)
    if not order["number"] or not order["items"]:
        print("ERROR: couldn't parse an order (need an order # and line items).", file=sys.stderr)
        return 1

    st = "Shipped" if (order["tracking"] and order["tracking"]["number"]) else "Confirmed (awaiting tracking)" \
        if re.search(r"ship|on its way|delivered|transit", order["status"], re.I) else order["status"]
    print(f"Parsed order #{order['number']}: {len(order['items'])} line items, "
          f"status -> {st}"
          + (f", tracking {order['tracking']['number']}" if order['tracking'] else ""))

    orders = read_existing_orders()
    orders = [o for o in orders if o.get("number") != order["number"]]
    orders.insert(0, order)
    write_orders_js(orders)
    print(f"Updated {ORDERS_JS} ({len(orders)} order(s)).")

    if args.no_deploy:
        print("Skipping deploy (--no-deploy).")
        return 0
    print("Deploying to Vercel ...")
    try:
        subprocess.run(["npx", "--yes", "vercel", "deploy", "--prod", "--yes"],
                       cwd=WEB_DIR, check=True, shell=(os.name == "nt"))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR deploying: {e}. orders.js was updated; deploy from web/ manually.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
