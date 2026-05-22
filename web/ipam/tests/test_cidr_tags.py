import re
import pytest
from django.template import Context, Template


def render_tpl(template_str, ctx=None):
    t = Template("{% load cidr_tags %}" + template_str)
    return t.render(Context(ctx or {}))


def test_cidr_info_renders_trigger_and_panel():
    out = render_tpl("{% cidr_info '10.0.0.0/24' %}")
    assert "10.0.0.0/24" in out
    assert 'data-info-trigger="cidr-info-' in out
    assert 'aria-describedby="cidr-info-' in out
    assert 'popover="auto"' in out
    assert 'role="button"' in out
    assert 'tabindex="0"' in out


def test_cidr_info_panel_contains_lines():
    out = render_tpl("{% cidr_info '10.0.0.0/24' %}")
    assert "Network" in out
    assert "10.0.0.0" in out
    assert "10.0.0.1" in out
    assert "10.0.0.254" in out
    assert "Broadcast" in out


def test_cidr_info_uses_no_legacy_hover_classes():
    out = render_tpl("{% cidr_info '10.0.0.0/24' %}")
    assert "group-hover:" not in out
    assert "pointer-events-none" not in out


def test_cidr_info_invalid_input_renders_text_without_popover():
    out = render_tpl("{% cidr_info 'not-a-cidr' %}")
    assert "not-a-cidr" in out
    assert "popover" not in out
    assert "data-info-trigger" not in out


def test_cidr_info_escapes_user_input():
    out = render_tpl("{% cidr_info '<script>alert(1)</script>' %}")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_cidr_info_panel_ids_unique_across_calls():
    out = render_tpl(
        "{% cidr_info '10.0.0.0/24' %}{% cidr_info '10.0.1.0/24' %}"
    )
    ids = re.findall(r'popover="auto" id="([^"]+)"', out)
    assert len(ids) == 2
    assert ids[0] != ids[1]


def test_cidr_info_trigger_references_panel_id():
    out = render_tpl("{% cidr_info '10.0.0.0/24' %}")
    trigger_id = re.search(r'data-info-trigger="([^"]+)"', out).group(1)
    panel_id = re.search(r'popover="auto" id="([^"]+)"', out).group(1)
    assert trigger_id == panel_id


def test_cidr_info_trigger_renders_only_attributes():
    out = render_tpl("{% cidr_info_trigger '10.0.0.0/24' 'pid-1' %}")
    assert 'data-info-trigger="pid-1"' in out
    assert 'aria-describedby="pid-1"' in out
    assert "popover" not in out
    assert "<div" not in out
    assert "<span" not in out


def test_cidr_info_trigger_invalid_returns_empty():
    out = render_tpl("{% cidr_info_trigger 'not-a-cidr' 'pid-1' %}")
    assert out.strip() == ""


def test_cidr_info_panel_uses_given_id():
    out = render_tpl("{% cidr_info_panel '10.0.0.0/24' 'my-id' %}")
    assert 'popover="auto"' in out
    assert 'id="my-id"' in out
    assert "Network" in out
    assert "Broadcast" in out


def test_cidr_info_panel_invalid_returns_empty():
    out = render_tpl("{% cidr_info_panel 'not-a-cidr' 'pid-1' %}")
    assert out.strip() == ""


def test_cidr_info_panel_does_not_include_outer_trigger():
    out = render_tpl("{% cidr_info_panel '10.0.0.0/24' 'pid-1' %}")
    assert "data-info-trigger" not in out
    assert 'role="button"' not in out


def test_cidr_info_split_tags_ids_match():
    trigger = render_tpl("{% cidr_info_trigger '10.0.0.0/24' 'block-42' %}")
    panel = render_tpl("{% cidr_info_panel   '10.0.0.0/24' 'block-42' %}")
    assert 'aria-describedby="block-42"' in trigger
    assert 'data-info-trigger="block-42"' in trigger
    assert 'id="block-42"' in panel


def test_free_suggestions_info_panel_renders_list():
    sugs = [
        {"prefix": 23, "network": "45.151.170.0", "size": 512, "cidr": "45.151.170.0/23"},
        {"prefix": 24, "network": "45.151.169.0", "size": 256, "cidr": "45.151.169.0/24"},
    ]
    out = render_tpl(
        "{% free_suggestions_info_panel suggestions 1020 'free-1' %}",
        {"suggestions": sugs},
    )
    assert 'popover="auto"' in out
    assert 'id="free-1"' in out
    assert "Frei" in out
    assert "1020 IPs" in out
    assert "Vorschläge" in out
    assert "/23" in out and "45.151.170.0" in out and "512 IPs" in out
    assert "/24" in out and "45.151.169.0" in out and "256 IPs" in out


def test_free_suggestions_info_panel_empty_returns_empty():
    out = render_tpl(
        "{% free_suggestions_info_panel suggestions 0 'free-1' %}",
        {"suggestions": []},
    )
    assert out.strip() == ""


def test_free_suggestions_info_panel_uses_no_legacy_hover_classes():
    sugs = [{"prefix": 24, "network": "10.0.0.0", "size": 256, "cidr": "10.0.0.0/24"}]
    out = render_tpl(
        "{% free_suggestions_info_panel suggestions 256 'free-1' %}",
        {"suggestions": sugs},
    )
    assert "group-hover:" not in out
    assert "pointer-events-none" not in out
