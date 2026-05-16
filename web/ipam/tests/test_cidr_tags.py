import pytest
from django.template import Context, Template


def render(cidr):
    t = Template("{% load cidr_tags %}{% cidr_tooltip cidr %}")
    return t.render(Context({"cidr": cidr}))


def test_ipv4_standard_prefix_shows_network_usable_broadcast():
    out = render("217.61.249.0/28")
    assert "217.61.249.0/28" in out
    assert "217.61.249.0" in out          # network
    assert "217.61.249.1" in out          # first usable
    assert "217.61.249.14" in out         # last usable
    assert "217.61.249.15" in out         # broadcast
    assert "Network" in out
    assert "Nutzbare IPs" in out
    assert "Broadcast" in out
    assert "group-hover" in out           # tailwind hover class present


def test_ipv4_slash30_shows_network_usable_broadcast():
    out = render("10.0.0.0/30")
    assert "10.0.0.0/30" in out
    assert "10.0.0.1" in out
    assert "10.0.0.2" in out
    assert "10.0.0.3" in out
    assert "Nutzbare IPs" in out


def test_ipv4_slash31_omits_usable_and_broadcast():
    out = render("10.0.0.0/31")
    assert "10.0.0.0/31" in out
    assert "Nutzbare IPs" not in out
    assert "Broadcast" not in out
    assert "Prefix" in out
    assert "2 Adressen" in out


def test_ipv4_slash32_omits_usable_and_broadcast():
    out = render("10.0.0.5/32")
    assert "10.0.0.5/32" in out
    assert "Nutzbare IPs" not in out
    assert "Broadcast" not in out
    assert "1 Adressen" in out


def test_ipv6_shows_network_prefix_and_address_count():
    out = render("2a05:ed80:100:400::/64")
    assert "2a05:ed80:100:400::/64" in out
    assert "2a05:ed80:100:400::" in out
    assert "Network" in out
    assert "Prefix" in out
    assert "2^64" in out
    assert "Broadcast" not in out
    assert "Nutzbare IPs" not in out


def test_invalid_input_returns_escaped_text_without_crash():
    out = render("not-a-cidr")
    assert "not-a-cidr" in out
    # No tooltip markup because we bailed early
    assert "group-hover" not in out


def test_html_escapes_user_input():
    out = render("<script>alert(1)</script>")
    assert "<script>" not in out  # raw must be escaped
    assert "&lt;script&gt;" in out
