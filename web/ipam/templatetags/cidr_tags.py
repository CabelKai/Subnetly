from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from netaddr import IPNetwork

register = template.Library()


@register.simple_tag
def cidr_tooltip(cidr):
    """Render a CIDR string with a hover-tooltip showing network details."""
    try:
        net = IPNetwork(str(cidr))
    except Exception:
        return escape(str(cidr))

    if net.version == 4:
        if net.prefixlen >= 31:
            lines = [
                ("Network",  str(net.network)),
                ("Prefix",   f"/{net.prefixlen} ({net.size} Adressen)"),
            ]
        else:
            first = net.network + 1
            last = net.broadcast - 1
            lines = [
                ("Network",       str(net.network)),
                ("Nutzbare IPs",  f"{first} – {last}"),
                ("Broadcast",     str(net.broadcast)),
            ]
    else:
        lines = [
            ("Network",  str(net.network)),
            ("Prefix",   f"/{net.prefixlen}"),
            ("Adressen", f"2^{128 - net.prefixlen}"),
        ]

    tooltip_html = "<br>".join(
        f"<span class='inline-block w-28'>{escape(k)}:</span>{escape(v)}"
        for k, v in lines
    )
    cidr_display = escape(str(cidr))

    html = (
        f'<span class="group relative cursor-help inline-block">'
        f'{cidr_display}'
        f'<span class="invisible group-hover:visible absolute bottom-full left-0 mb-1 '
        f'px-3 py-2 bg-slate-900 text-white text-xs font-mono rounded shadow-lg '
        f'whitespace-nowrap z-50 normal-case font-normal pointer-events-none">'
        f'{tooltip_html}'
        f'</span>'
        f'</span>'
    )
    return mark_safe(html)
