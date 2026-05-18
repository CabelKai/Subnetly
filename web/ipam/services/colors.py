import hashlib

# Tailwind 200-tone palette: all colors meet WCAG AAA contrast against
# text-slate-900 (10:1 or better). 16 entries (power-of-two mod for good
# hash distribution).
_PALETTE = [
    "#FECACA",  # red-200
    "#FED7AA",  # orange-200
    "#FEF08A",  # yellow-200
    "#D9F99D",  # lime-200
    "#BBF7D0",  # green-200
    "#A7F3D0",  # emerald-200
    "#99F6E4",  # teal-200
    "#BAE6FD",  # sky-200
    "#BFDBFE",  # blue-200
    "#C7D2FE",  # indigo-200
    "#DDD6FE",  # violet-200
    "#E9D5FF",  # purple-200
    "#F5D0FE",  # fuchsia-200
    "#FBCFE8",  # pink-200
    "#FECDD3",  # rose-200
    "#E4D88A",  # warm khaki (kept for variety)
]


def color_for(name: str) -> str:
    """Stable color hex for an application name (md5-based, may collide)."""
    if not name:
        return "#E5E7EB"
    h = hashlib.md5(name.encode("utf-8")).digest()
    return _PALETTE[h[0] % len(_PALETTE)]


def colors_for_set(names) -> dict:
    """Assign a distinct color per name from the palette, for a set of names.

    Names are sorted alphabetically (case-insensitive) and then assigned
    palette entries by position — so within a single view, no two names share
    a color as long as the count fits in the palette. Beyond palette length,
    colors wrap.

    The same set of names always produces the same color mapping (sort makes
    it deterministic).
    """
    unique = sorted({n for n in names if n}, key=str.casefold)
    return {n: _PALETTE[i % len(_PALETTE)] for i, n in enumerate(unique)}
