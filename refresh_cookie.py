#!/usr/bin/env python3
"""
Keep the VAULTX_B2B_COOKIE GitHub secret fresh.

Vault X's B2B store uses Shopify's passwordless customer accounts, so there is
no password to replay. Instead, this script keeps a persistent logged-in
browser profile alive: Shopify sessions renew on use (they only expire when
idle), so visiting the store daily from the same profile keeps the login valid
indefinitely. Each run harvests the profile's current cookies and pushes them
to the repo secret the daily GitHub Actions job scrapes with.

One-time setup (opens a visible browser - log in when it appears, including
the emailed 6-digit code):
    py refresh_cookie.py --setup

Then schedule a daily refresh, e.g. Windows Task Scheduler:
    schtasks /Create /SC DAILY /ST 07:30 /TN VaultXCookieRefresh
        /TR "py C:\\path\\to\\VaultXStockChecker\\refresh_cookie.py"

Requires:
    py -m pip install playwright && py -m playwright install chromium
    gh CLI authenticated with access to this repo (gh auth login)
"""

import argparse
import os
import subprocess
import sys
import time

import scrape_vaultx as vx

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROFILE = os.path.join(REPO_DIR, ".browser-profile")
COLLECTION_URL = f"{vx.BASE_URL}/collections/{vx.DEFAULT_COLLECTION}"
SECRET_NAME = "VAULTX_B2B_COOKIE"
SETUP_TIMEOUT_S = 900  # waiting for the emailed code can take a while


def format_cookie_header(cookies):
    """Build a Cookie request-header value from Playwright cookie dicts."""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def looks_logged_in(html):
    """A logged-out B2B collection page renders zero product links."""
    return bool(vx.extract_handles(html, vx.DEFAULT_COLLECTION))


def _goto(page, url):
    """page.goto that tolerates Shopify's instant redirect to the hosted
    login domain (which interrupts the navigation and raises)."""
    from playwright.sync_api import Error as PlaywrightError
    try:
        page.goto(url, wait_until="domcontentloaded")
    except PlaywrightError as e:
        if "interrupted by another navigation" not in str(e):
            raise
        try:
            page.wait_for_load_state("domcontentloaded")
        except PlaywrightError:
            pass


def _collection_shows_products(page):
    """True once the storefront collection shows products; navigates there if
    needed. Swallows mid-navigation races."""
    from playwright.sync_api import Error as PlaywrightError
    try:
        if not page.url.startswith(vx.BASE_URL):
            return False
        if looks_logged_in(page.content()):
            return True
        _goto(page, COLLECTION_URL)
        return looks_logged_in(page.content())
    except PlaywrightError:
        return False


def _wait_for_login(page, timeout_s):
    """Passively wait for the user to finish logging in.

    The login flow bounces between the hosted-accounts domain and the
    storefront, so navigating while it's in progress kicks the user back to
    the start. This loop only watches; it nudges to the collection page just
    once the browser has sat on the storefront for several consecutive ticks
    without showing products (e.g. parked on the homepage after login).
    """
    from playwright.sync_api import Error as PlaywrightError
    deadline = time.time() + timeout_s
    storefront_ticks = 0
    while time.time() < deadline:
        time.sleep(3)
        try:
            on_storefront = page.url.startswith(vx.BASE_URL)
            if on_storefront and looks_logged_in(page.content()):
                return True
        except PlaywrightError:
            continue  # page mid-navigation; check again next tick
        storefront_ticks = storefront_ticks + 1 if on_storefront else 0
        if storefront_ticks >= 5:  # ~15s settled without products
            _goto(page, COLLECTION_URL)
            storefront_ticks = 0
    return False


def harvest_cookie(profile_dir, setup=False, headed=False):
    """Open the persistent profile, ensure the session is live, return the
    Cookie header string. In setup mode, waits for the user to log in."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            profile_dir, headless=not (setup or headed))
        try:
            page = context.pages[0] if context.pages else context.new_page()
            _goto(page, COLLECTION_URL)

            if setup:
                print("Log in in the browser window (email + 6-digit code). "
                      "Waiting for the B2B collection to show products ...")
                _wait_for_login(page, SETUP_TIMEOUT_S)

            if not _collection_shows_products(page):
                raise RuntimeError(
                    "Not logged in (no products visible on the B2B collection). "
                    "Run:  py refresh_cookie.py --setup")

            return format_cookie_header(
                context.cookies(vx.BASE_URL))
        finally:
            context.close()


def push_secret(cookie):
    """Update the repo secret via gh, passing the value on stdin so it never
    appears in a process command line."""
    subprocess.run(["gh", "secret", "set", SECRET_NAME],
                   input=cookie, text=True, check=True, cwd=REPO_DIR)


def main():
    parser = argparse.ArgumentParser(
        description=f"Refresh the {SECRET_NAME} GitHub secret from a "
                    "persistent logged-in browser profile")
    parser.add_argument("--setup", action="store_true",
                        help="open a visible browser for the one-time login")
    parser.add_argument("--headed", action="store_true",
                        help="run the refresh with a visible browser (use if "
                             "headless gets blocked by bot protection)")
    parser.add_argument("--profile", default=DEFAULT_PROFILE,
                        help=f"browser profile dir (default: {DEFAULT_PROFILE})")
    parser.add_argument("--no-push", action="store_true",
                        help="capture and validate the cookie but don't "
                             "update the GitHub secret")
    args = parser.parse_args()

    try:
        cookie = harvest_cookie(args.profile, setup=args.setup,
                                headed=args.headed)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"Session is live; captured cookie ({len(cookie)} chars).")

    if args.no_push:
        print("Skipping secret update (--no-push).")
        return 0
    try:
        push_secret(cookie)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR updating secret via gh: {e}", file=sys.stderr)
        print("Is the gh CLI installed and authenticated (gh auth login)?",
              file=sys.stderr)
        return 1
    print(f"GitHub secret {SECRET_NAME} updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
