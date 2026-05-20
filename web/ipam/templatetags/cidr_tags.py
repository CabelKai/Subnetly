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


def _popover_wrapper(body, panel_id):
    """Wrap pre-built body markup in the standard popover='auto' div.

    Single source of truth for the outer container (Tailwind classes,
    attribute order). Body must already be a complete, escaped HTML
    fragment. panel_id is escaped here; do not pre-escape.
    """
    safe_id = escape(str(panel_id))
    return (
        f'<div popover="auto" id="{safe_id}" '
        'class="info-panel bg-slate-900 text-white text-xs font-mono '
        'rounded shadow-lg px-3 py-2 normal-case font-normal m-0 '
        'max-w-xs whitespace-nowrap">'
        f'{body}'
        '</div>'
    )


def _info_panel_html(lines, panel_id):
    body = "<br>".join(
        f"<span class='inline-block w-28'>{escape(k)}:</span>{escape(v)}"
        for k, v in lines
    )
    return _popover_wrapper(body, panel_id)


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


@register.simple_tag
def cidr_info_trigger(cidr, panel_id):
    """Render only the trigger attributes for a CIDR popover.

    Caller spreads these attributes onto an existing element (e.g. an
    <a> wrapping a grid block). Caller must also render
    cidr_info_panel with the SAME panel_id as a sibling.

    Returns empty string for invalid CIDR (no popover rendered).
    """
    if _tooltip_lines(cidr) is None:
        return ""
    pid = escape(str(panel_id))
    return mark_safe(
        f'data-info-trigger="{pid}" aria-describedby="{pid}"'
    )


@register.simple_tag
def cidr_info_panel(cidr, panel_id):
    """Render only the popover panel <div> for a CIDR.

    Caller provides panel_id and places the panel as a sibling of the
    element bearing the matching cidr_info_trigger attributes.

    Returns empty string for invalid CIDR.
    """
    lines = _tooltip_lines(cidr)
    if lines is None:
        return ""
    return mark_safe(_info_panel_html(lines, panel_id))


@register.simple_tag
def free_suggestions_info_panel(suggestions, size, panel_id):
    """Popover panel for a free grid block, listing aligned-subnet suggestions.

    Returns empty string if suggestions is empty.
    """
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
    return mark_safe(_popover_wrapper(body, panel_id))
