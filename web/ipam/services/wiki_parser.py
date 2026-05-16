import re
from typing import List

# Headers like ==== Name ====
_HEADER = re.compile(r"^={2,}\s*(.+?)\s*={2,}\s*$")

# CIDR (IPv4 or IPv6) with explicit prefix length
_CIDR = re.compile(
    r"(?<![\w.:])("
    r"(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}"
    r"|"
    r"[0-9a-fA-F:]+:[0-9a-fA-F:]*/\d{1,3}"
    r")"
)

# Bare IPv4 (no prefix)
_BARE_V4 = re.compile(r"(?<![\w./:])((?:\d{1,3}\.){3}\d{1,3})(?!/\d)(?![\w.:])")

# Lines we should NOT scan for bare IPs (already-covered host enumerations,
# gateways, broadcasts, "nutzbare IPs"). These are descriptive only.
_SKIP_LINE_PATTERNS = (
    re.compile(r"^\s*host-?ips?\s*:", re.IGNORECASE),
    re.compile(r"^\s*nutzbare\s+ips?\s*:", re.IGNORECASE),
    re.compile(r"^\s*broadcast\s*:", re.IGNORECASE),
    re.compile(r"^\s*gateway\s*:", re.IGNORECASE),
)

# Shorthand: "185.91.196.6, 7, 8" → expand to .6, .7, .8
_COMMA_TAIL = re.compile(r"((?:\d{1,3}\.){3})(\d{1,3})\s*,\s*(\d{1,3}(?:\s*,\s*\d{1,3})*)")


def parse(text: str) -> List[dict]:
    """Parse a dokuwiki-style IP allocation text.

    Returns a list of {application, cidr, notes} dicts.
    """
    results: List[dict] = []
    current = None

    for raw in text.splitlines():
        line = raw.rstrip()
        m = _HEADER.match(line)
        if m:
            current = m.group(1).strip()
            continue
        if current is None:
            continue
        if not line.strip():
            continue
        if any(p.match(line) for p in _SKIP_LINE_PATTERNS):
            continue

        # 1) Comma-tail shorthand: convert "a.b.c.6, 7, 8" → three /32 entries.
        cm = _COMMA_TAIL.search(line)
        if cm:
            prefix = cm.group(1)
            first = cm.group(2)
            rest = [x.strip() for x in cm.group(3).split(",") if x.strip()]
            for octet in [first, *rest]:
                results.append({
                    "application": current,
                    "cidr": f"{prefix}{octet}/32",
                    "notes": "",
                })
            continue

        # 2) Explicit CIDRs on the line.
        found_any = False
        for cm in _CIDR.finditer(line):
            cidr = cm.group(1)
            # Normalize IPv6 hosts written with /64 etc. — keep as-is, the
            # DB layer will accept; if the address is not the network address
            # netaddr will still parse, and the DB stores the network part.
            note = _extract_note(line, cm.span())
            results.append({"application": current, "cidr": cidr, "notes": note})
            found_any = True
        if found_any:
            continue

        # 3) Single bare IPv4 → /32.
        for cm in _BARE_V4.finditer(line):
            ip = cm.group(1)
            note = _extract_note(line, cm.span())
            results.append({"application": current, "cidr": f"{ip}/32", "notes": note})

    return results


def _extract_note(line: str, match_span) -> str:
    """Return text on the line excluding the matched CIDR/IP, trimmed."""
    start, end = match_span
    before = line[:start].strip(" \t:,")
    after = line[end:].strip(" \t:,")
    # Drop boilerplate labels like "Netz", "IP Netz", "IP Netz2"
    before = re.sub(r"^(IP\s*)?Netz\d*\s*$", "", before, flags=re.IGNORECASE).strip()
    parts = [p for p in (before, after) if p]
    return " ".join(parts)
