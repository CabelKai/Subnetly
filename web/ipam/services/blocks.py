from typing import List, Optional

from netaddr import IPNetwork


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
    # Represent the gap with a best-effort CIDR (first IP / largest aligned prefix
    # that fits). Layout only depends on `span`/`size`.
    from netaddr import IPAddress
    return {
        "kind": "free",
        "cidr": IPNetwork(f"{IPAddress(first_int, version=version)}/{_prefix_for(size, version)}"),
        "size": size,
        "span": span,
    }


def _prefix_for(size: int, version: int) -> int:
    total = 32 if version == 4 else 128
    bits = 0
    while (1 << bits) < size:
        bits += 1
    return total - bits
