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
