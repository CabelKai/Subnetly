import hashlib

# Palette tuned for readable text on these backgrounds (16 entries → power-of-two mod)
_PALETTE = [
    "#FCA5A5", "#FDBA74", "#FCD34D", "#A7F3D0", "#86EFAC",
    "#7DD3FC", "#A5B4FC", "#C4B5FD", "#F0ABFC", "#FDA4AF",
    "#FEF08A", "#BEF264", "#67E8F9", "#93C5FD", "#D8B4FE",
    "#99F6E4",
]


def color_for(name: str) -> str:
    """Stable color hex for an application name."""
    if not name:
        return "#E5E7EB"
    h = hashlib.md5(name.encode("utf-8")).digest()
    return _PALETTE[h[0] % len(_PALETTE)]
