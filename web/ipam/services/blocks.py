from typing import List, Optional

from netaddr import IPNetwork


def largest_aligned_subnets(first: int, last: int, version: int, max_count: int = 3) -> list:
    """Return up to max_count aligned subnets that fit within [first, last],
    sorted by size DESC. Each entry: {'prefix': int, 'network_int': int, 'size': int}.

    This greedily walks the range, at each position picking the largest aligned
    subnet that fits both alignment (position must be on prefix boundary) and
    size (subnet must not exceed remaining space), then advancing. The full
    decomposition is computed, then the top max_count by size are returned.
    """
    total_bits = 32 if version == 4 else 128
    subnets = []
    pos = first
    while pos <= last:
        max_size = last - pos + 1
        # alignment: largest e such that pos % 2^e == 0
        if pos == 0:
            e_align = total_bits
        else:
            # (pos & -pos) isolates the lowest set bit; its bit-length-1 is the alignment exponent
            e_align = (pos & -pos).bit_length() - 1
        # size fit: largest e such that 2^e <= max_size
        e_size = max_size.bit_length() - 1
        e = min(e_align, e_size, total_bits)
        prefix = total_bits - e
        size = 1 << e
        subnets.append({"prefix": prefix, "network_int": pos, "size": size})
        pos += size
    subnets.sort(key=lambda s: -s["size"])
    return subnets[:max_count]


def compute_blocks(
    pool: IPNetwork,
    assignments: List[dict],
    block_prefix: Optional[int] = None,
) -> List[dict]:
    """Compute block list for a pool's visual grid.

    Each assignment is a dict with at least:
      - 'cidr': IPNetwork
      - 'label': str
    Returns list of dicts:
      - {'kind': 'assigned', 'cidr': IPNetwork, 'label': str, 'span': int}
      - {'kind': 'free',     'cidr': IPNetwork, 'span': int, 'size': int}

    `block_prefix` is the cell-size prefix length (e.g. 30 = each cell is /30).
    Defaults to the pool's own prefix length (= 1 cell total).
    `span` is the number of grid cells the block occupies.

    Free regions are emitted as one block per contiguous gap. The block's
    `cidr` is the smallest network covering that gap when the gap is itself
    a valid CIDR; otherwise the largest aligned subnet starting at the gap's
    first IP (caller can ignore — `span` is the source of truth for layout).
    """
    if block_prefix is None:
        block_prefix = pool.prefixlen

    total_bits = 32 if pool.version == 4 else 128
    cell_size = 2 ** (total_bits - block_prefix)

    sorted_assigns = sorted(assignments, key=lambda a: a["cidr"].first)
    blocks: List[dict] = []
    pos = pool.first

    for a in sorted_assigns:
        a_first = a["cidr"].first
        a_last = a["cidr"].last
        if pos < a_first:
            blocks.append(_free_block(pos, a_first - 1, cell_size, pool.version))
        blocks.append({
            "kind": "assigned",
            "cidr": a["cidr"],
            "label": a["label"],
            "span": max(1, a["cidr"].size // cell_size),
        })
        pos = a_last + 1

    if pos <= pool.last:
        blocks.append(_free_block(pos, pool.last, cell_size, pool.version))

    return blocks


def _free_block(first_int: int, last_int: int, cell_size: int, version: int) -> dict:
    size = last_int - first_int + 1
    span = max(1, size // cell_size)
    suggestions_raw = largest_aligned_subnets(first_int, last_int, version, max_count=3)
    from netaddr import IPAddress
    suggestions = [
        {
            "prefix": s["prefix"],
            "network": str(IPAddress(s["network_int"], version=version)),
            "size": s["size"],
            "cidr": f"{IPAddress(s['network_int'], version=version)}/{s['prefix']}",
        }
        for s in suggestions_raw
    ]
    return {
        "kind": "free",
        "size": size,
        "span": span,
        "suggestions": suggestions,
    }
