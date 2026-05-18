import pytest
from netaddr import IPAddress, IPNetwork

from ipam.services.blocks import compute_blocks, largest_aligned_subnets
from ipam.services.colors import color_for, colors_for_set


def _assigned(cidr, label):
    return {"cidr": IPNetwork(cidr), "label": label}


def test_no_assignments_is_one_free_block():
    blocks = compute_blocks(IPNetwork("217.61.248.0/30"), [])
    assert len(blocks) == 1
    b = blocks[0]
    assert b["kind"] == "free"
    assert b["suggestions"][0]["cidr"] == "217.61.248.0/30"
    assert b["size"] == 4


def test_fully_assigned_pool_has_no_free_block():
    pool = IPNetwork("217.61.248.0/30")  # 4 IPs
    blocks = compute_blocks(pool, [_assigned("217.61.248.0/30", "X")])
    assert len(blocks) == 1
    assert blocks[0]["kind"] == "assigned"
    assert blocks[0]["size"] == 4


def test_assignment_in_middle_creates_three_blocks():
    pool = IPNetwork("217.61.248.0/28")  # 16 IPs
    blocks = compute_blocks(pool, [_assigned("217.61.248.4/30", "X")])
    kinds = [b["kind"] for b in blocks]
    assert kinds == ["free", "assigned", "free"]
    # sizes: free .0-.3 = 4 IPs; assigned .4-.7 = 4 IPs; free .8-.15 = 8 IPs
    assert [b["size"] for b in blocks] == [4, 4, 8]



def test_free_gap_between_two_assignments():
    pool = IPNetwork("217.61.249.0/28")  # 16 IPs
    blocks = compute_blocks(
        pool,
        [
            _assigned("217.61.249.0/30", "A"),
            _assigned("217.61.249.8/30", "B"),
        ],
    )
    assert [b["kind"] for b in blocks] == ["assigned", "free", "assigned", "free"]
    assert [b["size"] for b in blocks] == [4, 4, 4, 4]


def test_color_stable_for_same_name():
    assert color_for("BINSS") == color_for("BINSS")
    assert color_for("BINSS") != color_for("Falcon")


def test_color_returns_hex():
    c = color_for("X")
    assert c.startswith("#") and len(c) == 7


def test_colors_for_set_stable_when_other_names_added():
    # Adding a new application must NOT change colors of existing ones.
    before = colors_for_set(["BINSS", "Falcon"])
    after = colors_for_set(["BINSS", "Falcon", "SWE"])
    assert before["BINSS"] == after["BINSS"]
    assert before["Falcon"] == after["Falcon"]


def test_colors_for_set_equals_color_for_each_name():
    # The set mapping uses the same per-name stable hash as color_for().
    names = ["BINSS", "Falcon", "SWE"]
    mapping = colors_for_set(names)
    for n in names:
        assert mapping[n] == color_for(n)


def test_colors_for_set_deterministic_regardless_of_input_order():
    a = colors_for_set(["BINSS", "Falcon", "SWE"])
    b = colors_for_set(["SWE", "BINSS", "Falcon"])
    assert a == b


def test_colors_for_set_ignores_empty_names():
    mapping = colors_for_set(["BINSS", "", None, "Falcon"])
    assert set(mapping.keys()) == {"BINSS", "Falcon"}


def test_largest_aligned_subnets_perfect_alignment():
    # /24 starting at .0 — one suggestion
    result = largest_aligned_subnets(0, 255, 4, max_count=3)
    assert len(result) == 1
    assert result[0] == {"prefix": 24, "network_int": 0, "size": 256}


def test_largest_aligned_subnets_misaligned_start():
    # 45.151.168.4 - 45.151.171.255 — the bug example
    first = int(IPAddress("45.151.168.4"))
    last = int(IPAddress("45.151.171.255"))
    result = largest_aligned_subnets(first, last, 4, max_count=3)
    # Top 3 by size: /23 at .170.0, /24 at .169.0, /25 at .168.128
    assert len(result) == 3
    assert result[0]["prefix"] == 23
    assert IPAddress(result[0]["network_int"], version=4) == IPAddress("45.151.170.0")
    assert result[0]["size"] == 512
    assert result[1]["prefix"] == 24
    assert IPAddress(result[1]["network_int"], version=4) == IPAddress("45.151.169.0")
    assert result[1]["size"] == 256
    assert result[2]["prefix"] == 25
    assert IPAddress(result[2]["network_int"], version=4) == IPAddress("45.151.168.128")
    assert result[2]["size"] == 128


def test_largest_aligned_subnets_single_ip():
    result = largest_aligned_subnets(100, 100, 4, max_count=3)
    assert len(result) == 1
    assert result[0]["prefix"] == 32
    assert result[0]["size"] == 1


def test_largest_aligned_subnets_returns_largest_first():
    # Ensure sort DESC by size
    result = largest_aligned_subnets(4, 31, 4, max_count=5)
    sizes = [s["size"] for s in result]
    assert sizes == sorted(sizes, reverse=True)


def test_free_block_carries_suggestions_not_misleading_cidr():
    pool = IPNetwork("45.151.168.0/22")  # /22
    assignments = [{"cidr": IPNetwork("45.151.168.0/30"), "label": "Existing"}]
    blocks = compute_blocks(pool, assignments)
    free = [b for b in blocks if b["kind"] == "free"]
    assert len(free) == 1
    # No misleading cidr
    assert "cidr" not in free[0]
    # Suggestions present, largest first
    suggestions = free[0]["suggestions"]
    assert len(suggestions) <= 3
    assert suggestions[0]["prefix"] == 23
    assert suggestions[0]["cidr"] == "45.151.170.0/23"


def test_palette_uses_tailwind_200_tones():
    """B1: Color palette uses 200-tone Tailwind colors for WCAG AAA contrast vs slate-900."""
    from ipam.services.colors import _PALETTE
    # Spot-check three known 200-tone hex values
    assert "#FECACA" in _PALETTE  # red-200
    assert "#BBF7D0" in _PALETTE  # green-200
    assert "#BFDBFE" in _PALETTE  # blue-200
    # Make sure none of the old 300-tone hex values remain
    assert "#FCA5A5" not in _PALETTE  # red-300 (old)
    assert "#86EFAC" not in _PALETTE  # green-300 (old)
    assert "#7DD3FC" not in _PALETTE  # sky-300 (old)
