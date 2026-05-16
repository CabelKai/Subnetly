from pathlib import Path

from ipam.services.wiki_parser import parse

SAMPLE = (Path(__file__).parent / "fixtures" / "wiki_sample.txt").read_text()


def test_parse_returns_customer_with_cidr_entries():
    results = parse(SAMPLE)
    by_customer = {r["customer"]: [] for r in results}
    for r in results:
        by_customer[r["customer"]].append(r["cidr"])

    assert "BINSS" in by_customer
    assert "217.61.249.0/28" in by_customer["BINSS"]
    assert "217.61.249.16/28" in by_customer["BINSS"]


def test_parse_handles_dual_stack():
    results = parse(SAMPLE)
    cyter = [r for r in results if r["customer"] == "Cyter/Checkov Kommunikation"]
    cidrs = {r["cidr"] for r in cyter}
    assert "45.151.168.0/30" in cidrs
    assert any(c.startswith("2a05:ed80:100:1613") for c in cidrs)


def test_parse_expands_comma_listed_ips_to_slash32():
    results = parse(SAMPLE)
    clausberg = sorted(r["cidr"] for r in results if r["customer"] == "Clausberg")
    assert clausberg == ["185.91.196.6/32", "185.91.196.7/32", "185.91.196.8/32"]


def test_parse_captures_inline_note():
    results = parse(SAMPLE)
    swe = [r for r in results if r["customer"] == "SWE" and r["cidr"] == "217.61.249.192/30"]
    assert len(swe) == 1
    assert "MT Router" in swe[0]["notes"]


def test_parse_single_ip_without_prefix_becomes_slash32():
    results = parse(SAMPLE)
    varia = [r for r in results if r["cidr"] == "217.61.249.218/32"]
    assert len(varia) == 1
    assert varia[0]["customer"] == "SWE"
    assert "Varia" in varia[0]["notes"]


def test_parse_falcon_extracts_both_v4_and_v6_networks():
    results = parse(SAMPLE)
    falcon = sorted(r["cidr"] for r in results if r["customer"] == "Falcon")
    assert "217.61.249.32/29" in falcon
    assert "217.61.249.64/28" in falcon
    assert any(c.startswith("2a05:ed80:100:400") for c in falcon)


def test_parse_does_not_double_count_host_ip_lines():
    # "Host-IPs: 217.61.249.1 - 217.61.249.14" must NOT produce 14 /32 entries
    # because the /28 above already covers them.
    results = parse(SAMPLE)
    binss_v4 = [r["cidr"] for r in results if r["customer"] == "BINSS"]
    # Just the two /28 nets, no /32 expansions
    assert all("/28" in c for c in binss_v4)
