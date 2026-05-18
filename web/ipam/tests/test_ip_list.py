import pytest
from ipam.models import Application, Assignment, IPAssignment, Pool
from ipam.services.ip_list import build_ip_rows


@pytest.fixture
def small_subnet(db):
    pool = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    app = Application.objects.create(name="A")
    asgn = Assignment.objects.create(pool=pool, cidr="217.61.249.0/30")
    asgn.applications.add(app)
    return asgn, app


@pytest.fixture
def large_subnet(db):
    pool = Pool.objects.create(name="P2", cidr="217.61.248.0/22")
    app = Application.objects.create(name="A")
    asgn = Assignment.objects.create(pool=pool, cidr="217.61.249.0/24")
    asgn.applications.add(app)
    return asgn, app


@pytest.mark.django_db
def test_build_ip_rows_full_mode_includes_all_addresses_with_gaps(small_subnet):
    asgn, app = small_subnet
    IPAssignment.objects.create(assignment=asgn, address="217.61.249.1", application=app)
    rows = build_ip_rows(asgn)
    addresses = [r["address"] for r in rows]
    assert addresses == ["217.61.249.0", "217.61.249.1", "217.61.249.2", "217.61.249.3"]
    assert all(r["is_full_mode"] for r in rows)
    assert rows[1]["ip_assignment"] is not None
    assert rows[0]["ip_assignment"] is None


@pytest.mark.django_db
def test_build_ip_rows_sparse_mode_only_returns_existing(large_subnet):
    asgn, app = large_subnet
    IPAssignment.objects.create(assignment=asgn, address="217.61.249.10", application=app)
    IPAssignment.objects.create(assignment=asgn, address="217.61.249.20", application=app)
    rows = build_ip_rows(asgn)
    addresses = [r["address"] for r in rows]
    assert addresses == ["217.61.249.10", "217.61.249.20"]
    assert all(not r["is_full_mode"] for r in rows)


@pytest.mark.django_db
def test_build_ip_rows_marks_network_and_broadcast_in_v4(small_subnet):
    asgn, _ = small_subnet  # /30, four addresses
    rows = build_ip_rows(asgn)
    kinds = [r["reserved_kind"] for r in rows]
    assert kinds == ["network", None, None, "broadcast"]


@pytest.mark.django_db
def test_build_ip_rows_does_not_mark_reserved_for_slash31_and_slash32(db):
    pool = Pool.objects.create(name="P31", cidr="10.0.0.0/24")
    a31 = Assignment.objects.create(pool=pool, cidr="10.0.0.0/31")
    a32 = Assignment.objects.create(pool=pool, cidr="10.0.0.4/32")
    for r in build_ip_rows(a31):
        assert r["reserved_kind"] is None
    for r in build_ip_rows(a32):
        assert r["reserved_kind"] is None


@pytest.mark.django_db
def test_build_ip_rows_does_not_mark_reserved_for_ipv6(db):
    pool = Pool.objects.create(name="P6", cidr="2001:db8::/32")
    a = Assignment.objects.create(pool=pool, cidr="2001:db8:1::/126")
    for r in build_ip_rows(a):
        assert r["reserved_kind"] is None
