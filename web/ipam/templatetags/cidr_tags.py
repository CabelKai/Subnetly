from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe
from netaddr import IPNetwork
import itertools

register = template.Library()


# Monotonic counter for unique popover ids across a single page render.
# Thread-safe in CPython thanks to the GIL.
_INFO_ID_COUNTER = itertools.count()


def _next_info_id():
    return f"cidr-info-{next(_INFO_ID_COUNTER)}"


def _info_panel_html(lines, panel_id):
    body = "<br>".join(
        f"<span class='inline-block w-28'>{escape(k)}:</span>{escape(v)}"
        for k, v in lines
    )
    return (
        f'<div popover="auto" id="{panel_id}" '
        'class="info-panel bg-slate-900 text-white text-xs font-mono '
        'rounded shadow-lg px-3 py-2 normal-case font-normal m-0 '
        'max-w-xs whitespace-nowrap">'
        f'{body}'
        '</div>'
    )


@register.simple_tag
def django_debug():
    return settings.DEBUG


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
        '<span class="hidden group-hover:block absolute bottom-full left-0 mb-1 '
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


@register.simple_tag
def free_suggestions_tooltip_panel(suggestions, size):
    """Render the tooltip panel for a free grid block, listing aligned-subnet suggestions."""
    if not suggestions:
        return ""
    lines = [f"<span class='inline-block w-28'>Frei:</span>{escape(str(size))} IPs"]
    lines.append("<span class='block mt-2 mb-1 text-slate-400'>Vorschläge:</span>")
    for s in suggestions:
        lines.append(
            f"<span class='inline-block w-12 text-slate-300'>/{escape(str(s['prefix']))}</span>"
            f"<span class='inline-block w-44'>ab {escape(str(s['network']))}</span>"
            f"({escape(str(s['size']))} IPs)"
        )
    body = "<br>".join(lines)
    return mark_safe(
        '<span class="hidden group-hover:block absolute bottom-full left-0 mb-1 '
        'px-3 py-2 bg-slate-900 text-white text-xs font-mono rounded shadow-lg '
        'whitespace-nowrap z-50 normal-case font-normal pointer-events-none">'
        f'{body}'
        '</span>'
    )


@register.simple_tag
def cidr_info(cidr):
    """Render CIDR as text with a popover info-box (self-contained).

    Trigger and panel both rendered; panel uses HTML popover='auto' for
    top-layer rendering (escapes overflow:auto containers and viewport
    edges). Hover/focus/long-press behavior bound by popover.js.
    """
    lines = _tooltip_lines(cidr)
    cidr_display = escape(str(cidr))
    if lines is None:
        return mark_safe(cidr_display)
    panel_id = _next_info_id()
    trigger = (
        f'<span data-info-trigger="{panel_id}" '
        f'aria-describedby="{panel_id}" '
        f'tabindex="0" role="button" '
        f'class="cursor-help inline-block select-none">'
        f'{cidr_display}'
        f'</span>'
    )
    panel = _info_panel_html(lines, panel_id)
    return mark_safe(trigger + panel)
