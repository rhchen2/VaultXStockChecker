"""Unit tests for the pure logic in scrape_vaultx / build_web_data.

No network: fetch_* functions are exercised only through their parsing and
normalization helpers.
"""

import sys

import pytest
import requests

import build_web_data
import scrape_vaultx as vx


class FakeResp:
    def __init__(self, status=200, json_data=None, text="", headers=None):
        self.status_code = status
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


# ---------------------------------------------------------------- handles

COLLECTION_HTML = """
<a href="/collections/zip-binders/products/9-pocket-exo-tec-zip-binder">A</a>
<a href="/collections/zip-binders/products/9-pocket-exo-tec-zip-binder">dup</a>
<a href="/collections/zip-binders/products/12-pocket-exo-tec-zip-binder?variant=1">B</a>
<a href="/collections/other/products/should-not-match">nav</a>
<a href="/products/bare-link-ignored-when-scoped-exist">C</a>
"""


def test_extract_handles_scoped_and_deduped():
    handles = vx.extract_handles(COLLECTION_HTML, "zip-binders")
    assert handles == [
        "9-pocket-exo-tec-zip-binder",
        "12-pocket-exo-tec-zip-binder",
    ]


def test_extract_handles_falls_back_to_bare_product_links():
    html = '<a href="/products/only-bare-link">x</a>'
    assert vx.extract_handles(html, "zip-binders") == ["only-bare-link"]


def test_extract_handles_empty_page():
    assert vx.extract_handles("<html>login wall</html>", "zip-binders") == []


# ---------------------------------------------------------------- msrp_map


def test_msrp_map_skips_bad_prices_and_missing_skus():
    products = [{
        "variants": [
            {"sku": "A", "price": "31.99"},
            {"sku": "B", "price": None},
            {"sku": "", "price": "9.99"},
        ]
    }]
    assert vx.msrp_map(products) == {"A": 31.99}


# ------------------------------------------------------ normalize_js_product

JS_PRODUCT = {
    "title": "9-Pocket Exo-Tec Zip Binder",
    "handle": "9-pocket-exo-tec-zip-binder",
    "tags": ["binder"],
    "variants": [
        {
            "sku": "VX-09BK",
            "option1": "Signature Black",
            "title": "Signature Black",
            "price": 1944,  # B2B account price, cents
            "compare_at_price": 3199,
            "available": True,
            "quantity_price_breaks": [
                {"minimum_quantity": 24, "price": 1650},
                {"minimum_quantity": 12, "price": 1749},
            ],
        },
        {
            "sku": "VX-09BL",
            "options": ["Royal Blue"],
            "title": "Royal Blue",
            "price": 1944,
            "compare_at_price": None,
            "available": False,
            "quantity_price_breaks": [],
        },
    ],
}


def test_normalize_js_product_builds_rows_shape_and_pricing():
    product, pricing = vx.normalize_js_product(JS_PRODUCT)
    assert product["title"] == "9-Pocket Exo-Tec Zip Binder"
    assert product["tags"] == ["binder"]

    black, blue = product["variants"]
    assert black["option1"] == "Signature Black"
    assert black["available"] is True
    assert black["price"] == pytest.approx(31.99)  # compare_at_price fallback
    assert blue["option1"] == "Royal Blue"  # from options[0]
    assert blue["available"] is False
    assert blue["price"] is None  # no MSRP source at all

    assert pricing["VX-09BK"]["min1"] == pytest.approx(19.44)
    # breaks sorted ascending by quantity
    assert pricing["VX-09BK"]["breaks"] == [(12, 17.49), (24, 16.50)]
    assert pricing["VX-09BL"]["breaks"] == []


def test_normalize_js_product_prefers_public_msrp_over_compare_at():
    product, _ = vx.normalize_js_product(JS_PRODUCT, {"VX-09BK": 29.99})
    assert product["variants"][0]["price"] == pytest.approx(29.99)


# ---------------------------------------------------------------- build_rows


def test_build_rows_statuses_from_b2b_normalized_product():
    product, pricing = vx.normalize_js_product(JS_PRODUCT)
    rows = vx.build_rows([product], b2b_map=pricing)
    by_sku = {r["sku"]: r for r in rows}
    assert by_sku["VX-09BK"]["status"] == "In Stock"
    assert by_sku["VX-09BK"]["b2b_min1"] == pytest.approx(19.44)
    assert by_sku["VX-09BL"]["status"] == "Sold Out"


def test_build_rows_marks_preorder_tags():
    product, _ = vx.normalize_js_product(dict(JS_PRODUCT, tags=["Pre-Order"]))
    rows = vx.build_rows([product])
    assert rows[0]["status"] == "Pre-Order"  # available + preorder tag
    assert rows[1]["status"] == "Sold Out"  # unavailable stays sold out


# ---------------------------------------------------------------- extra_rows


def test_extra_rows_skips_skus_already_scraped():
    all_skus = {e["sku"] for e in build_web_data.EXTRA_ROWS}
    some = next(iter(all_skus))
    rows = build_web_data.extra_rows(include_b2b=True, existing_skus={some})
    assert some not in {r["sku"] for r in rows}
    assert len(rows) == len(all_skus) - 1


def test_extra_rows_public_view_strips_b2b_pricing():
    rows = build_web_data.extra_rows(include_b2b=False)
    assert all(r["b2b_min1"] is None and r["b2b_breaks"] == [] for r in rows)


# ------------------------------------------------------------ get_with_retry


def test_get_with_retry_retries_429_then_succeeds(monkeypatch):
    calls = []
    responses = [FakeResp(429, headers={"Retry-After": "1"}),
                 FakeResp(429), FakeResp(200, json_data={"ok": True})]
    monkeypatch.setattr(vx.requests, "get",
                        lambda url, **kw: calls.append(url) or responses[len(calls) - 1])
    monkeypatch.setattr(vx.time, "sleep", lambda s: None)
    resp = vx.get_with_retry("https://x/y")
    assert resp.json() == {"ok": True}
    assert len(calls) == 3


def test_get_with_retry_raises_after_exhausting(monkeypatch):
    monkeypatch.setattr(vx.requests, "get", lambda url, **kw: FakeResp(429))
    monkeypatch.setattr(vx.time, "sleep", lambda s: None)
    with pytest.raises(requests.HTTPError):
        vx.get_with_retry("https://x/y")


# ------------------------------------------- mocked end-to-end (no network)

PUBLIC_FEED = {
    "products": [{
        "title": "9-Pocket Exo-Tec Zip Binder",
        "handle": "9-pocket-exo-tec-zip-binder",
        "tags": [],
        "variants": [{
            "sku": "VX-09BK", "option1": "Signature Black",
            "title": "Signature Black", "price": "29.99", "available": True,
        }],
    }],
}

B2B_COLLECTION_HTML = (
    '<a href="/collections/zip-binders/products/9-pocket-exo-tec-zip-binder">x</a>'
)


def route_requests(monkeypatch):
    """Serve the public feed, B2B collection HTML and product .js from fixtures."""
    def fake_get(url, **kw):
        params = kw.get("params") or {}
        if url.endswith("/products.json"):
            return FakeResp(json_data=PUBLIC_FEED if params.get("page") == 1
                            else {"products": []})
        if url.endswith("/collections/zip-binders"):
            return FakeResp(text=B2B_COLLECTION_HTML if params.get("page") == 1
                            else "<html>no more</html>")
        if url.endswith("/products/9-pocket-exo-tec-zip-binder.js"):
            return FakeResp(json_data=JS_PRODUCT)
        raise AssertionError(f"unexpected URL: {url}")
    monkeypatch.setattr(vx.requests, "get", fake_get)
    monkeypatch.setattr(vx.time, "sleep", lambda s: None)


def test_fetch_b2b_catalog_end_to_end(monkeypatch):
    route_requests(monkeypatch)
    products, pricing = vx.fetch_b2b_catalog(
        "zip-binders", "cookie", "UA", vx.msrp_map(PUBLIC_FEED["products"]))
    assert [p["handle"] for p in products] == ["9-pocket-exo-tec-zip-binder"]
    # public MSRP wins over compare_at_price; B2B price goes to pricing map
    assert products[0]["variants"][0]["price"] == pytest.approx(29.99)
    assert pricing["VX-09BK"]["min1"] == pytest.approx(19.44)


def test_fetch_b2b_catalog_expired_session_raises(monkeypatch):
    monkeypatch.setattr(vx.requests, "get",
                        lambda url, **kw: FakeResp(text="<html>login wall</html>"))
    monkeypatch.setattr(vx.time, "sleep", lambda s: None)
    with pytest.raises(ValueError, match="expired"):
        vx.fetch_b2b_catalog("zip-binders", "stale-cookie", "UA")


def test_build_web_data_b2b_mode_via_cookie_env(monkeypatch, tmp_path):
    route_requests(monkeypatch)
    monkeypatch.setenv("VAULTX_B2B_COOKIE", "session=abc")
    out = tmp_path / "data.js"
    monkeypatch.setattr(sys, "argv", ["build_web_data.py", "--out", str(out)])
    build_web_data.main()
    text = out.read_text(encoding="utf-8")
    assert '"b2b_min1": 19.44' in text
    assert '"VX-EX01-04MPK"' in text  # extra rows still appended when missing


def test_build_web_data_falls_back_to_public_feed(monkeypatch, tmp_path):
    route_requests(monkeypatch)
    monkeypatch.delenv("VAULTX_B2B_COOKIE", raising=False)
    out = tmp_path / "data.js"
    monkeypatch.setattr(sys, "argv", ["build_web_data.py", "--out", str(out)])
    build_web_data.main()
    text = out.read_text(encoding="utf-8")
    assert '"msrp": 29.99' in text
    assert '"b2b_min1": null' in text
