import pytest
from netaddr import IPNetwork

from ipam.services.blocks import compute_blocks
from ipam.services.colors import color_for


def _assigned(cidr, label):
    return {"cidr": IPNetwork(cidr), "label": label}


def test_no_assignments_is_one_free_block():
    blocks = compute_blocks(IPNetwork("217.61.248.0/30"), [])
    assert len(blocks) == 1
    b = blocks[0]
    assert b["kind"] == "free"
    assert b["cidr"] == IPNetwork("217.61.248.0/30")
    assert b["span"] == 1  # block_prefix == pool prefix → 1 cell


def test_fully_assigned_pool_has_no_free_block():
    pool = IPNetwork("217.61.248.0/30")  # 4 IPs
    blocks = compute_blocks(pool, [_assigned("217.61.248.0/30", "X")])
    assert len(blocks) == 1
    assert blocks[0]["kind"] == "assigned"
    assert blocks[0]["span"] == 1


def test_assignment_in_middle_creates_three_blocks():
    pool = IPNetwork("217.61.248.0/28")  # 16 IPs, block_prefix=30 → 4 cells
    blocks = compute_blocks(pool, [_assigned("217.61.248.4/30", "X")], block_prefix=30)
    kinds = [b["kind"] for b in blocks]
    assert kinds == ["free", "assigned", "free"]
    # spans: free .0-.3 = 1 cell; assigned .4-.7 = 1 cell; free .8-.15 = 2 cells
    assert [b["span"] for b in blocks] == [1, 1, 2]


def test_larger_assignment_spans_multiple_cells():
    pool = IPNetwork("217.61.248.0/25")  # 128 IPs, block_prefix=30 → 32 cells
    blocks = compute_blocks(
        pool,
        [_assigned("217.61.248.0/28", "BINSS")],  # 16 IPs → 4 cells
        block_prefix=30,
    )
    assert blocks[0]["kind"] == "assigned"
    assert blocks[0]["span"] == 4
    # 16-127 = 112 IPs free = 28 cells, expressed as one block
    assert blocks[1]["kind"] == "free"
    assert blocks[1]["span"] == 28


def test_free_gap_between_two_assignments():
    pool = IPNetwork("217.61.249.0/28")  # 16 IPs, block_prefix=30 → 4 cells
    blocks = compute_blocks(
        pool,
        [
            _assigned("217.61.249.0/30", "A"),
            _assigned("217.61.249.8/30", "B"),
        ],
        block_prefix=30,
    )
    assert [b["kind"] for b in blocks] == ["assigned", "free", "assigned", "free"]
    assert [b["span"] for b in blocks] == [1, 1, 1, 1]


def test_color_stable_for_same_name():
    assert color_for("BINSS") == color_for("BINSS")
    assert color_for("BINSS") != color_for("Falcon")


def test_color_returns_hex():
    c = color_for("X")
    assert c.startswith("#") and len(c) == 7
