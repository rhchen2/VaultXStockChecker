"""Unit tests for refresh_cookie's pure logic (no browser, no gh)."""

import refresh_cookie as rc


def test_format_cookie_header_joins_pairs():
    cookies = [
        {"name": "_shopify_y", "value": "abc", "domain": ".vaultx.com"},
        {"name": "_secure_session_id", "value": "123", "domain": "us.b2b.vaultx.com"},
    ]
    assert rc.format_cookie_header(cookies) == (
        "_shopify_y=abc; _secure_session_id=123")


def test_looks_logged_in_true_when_products_render():
    html = '<a href="/collections/zip-binders/products/some-binder">x</a>'
    assert rc.looks_logged_in(html) is True


def test_looks_logged_in_false_on_login_wall():
    assert rc.looks_logged_in("<html>please log in</html>") is False
