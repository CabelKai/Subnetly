import hashlib

# Palette tuned for readable dark text on these light backgrounds.
# 16 entries (power-of-two mod for good hash distribution). Skewed warm,
# only one green and one blue, so the grid doesn't drown in cool tones.
_PALETTE = [
    "#FCA5A5",  # red-300
    "#F87171",  # red-400
    "#FDBA74",  # orange-300
    "#FB923C",  # orange-400
    "#FCD34D",  # amber-300
    "#FDE047",  # yellow-300
    "#E4D88A",  # warm khaki
    "#BEF264",  # lime-300       (only "yellowy-green")
    "#86EFAC",  # green-300      (only true green)
    "#5EEAD4",  # teal-300
    "#7DD3FC",  # sky-300        (only blue)
    "#C4B5FD",  # violet-300
    "#E9D5FF",  # purple-200
    "#F0ABFC",  # fuchsia-300
    "#F9A8D4",  # pink-300
    "#FB7185",  # rose-400
]


def color_for(name: str) -> str:
    """Stable color hex for an application name."""
    if not name:
        return "#E5E7EB"
    h = hashlib.md5(name.encode("utf-8")).digest()
    return _PALETTE[h[0] % len(_PALETTE)]
