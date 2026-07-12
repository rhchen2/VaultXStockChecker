#!/usr/bin/env python3
"""
One-command refresh of the web front-end *with B2B pricing*, then deploy.

Pulls your logged-in B2B session from a browser HAR capture, scrapes the B2B
catalog (full product list, availability and 1+/volume pricing), rebuilds
web/data.js, and deploys to Vercel. The daily GitHub Actions job does the same
when the VAULTX_B2B_COOKIE secret holds a valid session; otherwise it falls
back to the public/MSRP feed.

    py make_b2b_site.py                       # auto-detect newest *.har, deploy
    py make_b2b_site.py --har session.har     # explicit HAR
    py make_b2b_site.py --no-deploy           # rebuild data.js only

Note: if the daily cron has no valid VAULTX_B2B_COOKIE it will overwrite the
site back to public/MSRP data on its next run, so re-run this (with a fresh HAR
when the session expires - see README) to restore the B2B view.
"""

import argparse
import glob
import os
import subprocess
import sys

import requests

import scrape_vaultx as vx
from build_web_data import write_web_data, extra_rows

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def newest_har():
    """Return the most recently modified *.har in the repo, or None."""
    hars = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.har"))
    return max(hars, key=os.path.getmtime) if hars else None


def main():
    parser = argparse.ArgumentParser(description="Rebuild web/data.js with B2B pricing and deploy")
    parser.add_argument("--har", default=None,
                        help="HAR file from a logged-in session (default: newest *.har)")
    parser.add_argument("--collection", default=vx.DEFAULT_COLLECTION)
    parser.add_argument("--out", default=os.path.join(WEB_DIR, "data.js"))
    parser.add_argument("--no-deploy", action="store_true",
                        help="Rebuild data.js but skip the Vercel deploy")
    args = parser.parse_args()

    har = args.har or newest_har()
    if not har or not os.path.exists(har):
        print("ERROR: no HAR file found. Capture one (see README) or pass --har.",
              file=sys.stderr)
        return 1
    print(f"Using HAR: {har}")

    public_products = []
    try:
        public_products = vx.fetch_products(args.collection)  # MSRP enrichment
    except requests.RequestException as e:
        print(f"WARNING: public feed unavailable ({e}); MSRP column may be "
              "blank.", file=sys.stderr)

    try:
        cookie, user_agent = vx.load_har_session(har)
        products, b2b_map = vx.fetch_b2b_catalog(
            args.collection, cookie, user_agent, vx.msrp_map(public_products))
        print(f"Scraped B2B catalog: {len(products)} products, pricing for "
              f"{len(b2b_map)} variants.")
    except (OSError, ValueError, requests.RequestException) as e:
        print(f"ERROR scraping B2B catalog: {e}", file=sys.stderr)
        return 1

    rows = vx.build_rows(products, b2b_map=b2b_map)
    # login-gated products not already covered by the B2B scrape
    rows += extra_rows(include_b2b=True, existing_skus={r["sku"] for r in rows})
    write_web_data(rows, args.collection, args.out, generated_by="make_b2b_site.py")

    if args.no_deploy:
        print("Skipping deploy (--no-deploy).")
        return 0

    print("Deploying to Vercel ...")
    try:
        subprocess.run(
            ["npx", "--yes", "vercel", "deploy", "--prod", "--yes"],
            cwd=WEB_DIR, check=True, shell=(os.name == "nt"),
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR deploying to Vercel: {e}", file=sys.stderr)
        print("data.js was rebuilt; you can deploy manually from web/.", file=sys.stderr)
        return 1
    print("Done. Live site now shows B2B pricing (until the next daily run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
