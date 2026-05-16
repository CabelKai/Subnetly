from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from netaddr import IPNetwork

register = template.Library()


def _tooltip_lines(cidr):
    try:
        net = IPNetwork(str(cidr))
    except Exception:
        return None
    if net.version == 4:
        if net.prefixlen >= 31:
            return [
                ("Network", str(net.network)),
                ("Prefix",  f"/{net.prefixlen} ({net.size} Adressen)"),
            ]
        first = net.network + 1
        last = net.broadcast - 1
        return [
            ("Network",      str(net.network)),
            ("Nutzbare IPs", f"{first} – {last}"),
            ("Broadcast",    str(net.broadcast)),
        ]
    return [
        ("Network",  str(net.network)),
        ("Prefix",   f"/{net.prefixlen}"),
        ("Adressen", f"2^{128 - net.prefixlen}"),
    ]


def _panel_html(lines):
    body = "<br>".join(
        f"<span class='inline-block w-28'>{escape(k)}:</span>{escape(v)}"
        for k, v in lines
    )
    return (
        '<span class="invisible group-hover:visible absolute bottom-full left-0 mb-1 '
        'px-3 py-2 bg-slate-900 text-white text-xs font-mono rounded shadow-lg '
        'whitespace-nowrap z-50 normal-case font-normal pointer-events-none">'
        f'{body}'
        '</span>'
    )


@register.simple_tag
def cidr_tooltip(cidr):
    """Render a CIDR as text with a hover-tooltip (self-contained wrapper)."""
    lines = _tooltip_lines(cidr)
    cidr_display = escape(str(cidr))
    if lines is None:
        return cidr_display
    return mark_safe(
        '<span class="group relative cursor-help inline-block">'
        f'{cidr_display}'
        f'{_panel_html(lines)}'
        '</span>'
    )


@register.simple_tag
def cidr_tooltip_panel(cidr):
    """Render ONLY the tooltip panel; caller must apply 'group relative' to its parent."""
    lines = _tooltip_lines(cidr)
    if lines is None:
        return ""
    return mark_safe(_panel_html(lines))
