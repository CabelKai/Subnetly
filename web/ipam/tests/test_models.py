import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ipam.models import Assignment, Customer, Pool


@pytest.mark.django_db
def test_pool_v4_auto_sets_ip_version(pool_v4):
    assert pool_v4.ip_version == 4


@pytest.mark.django_db
def test_pool_v6_auto_sets_ip_version(pool_v6):
    assert pool_v6.ip_version == 6


@pytest.mark.django_db
def test_pool_cidr_unique(pool_v4):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pool.objects.create(name="dup", cidr="217.61.248.0/23")


@pytest.mark.django_db
def test_customer_name_unique():
    Customer.objects.create(name="BINSS")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.create(name="BINSS")


@pytest.mark.django_db
def test_assignment_basic_create(pool_v4):
    c = Customer.objects.create(name="BINSS")
    a = Assignment.objects.create(
        pool=pool_v4,
        customer=c,
        cidr="217.61.249.0/28",
        gateway="217.61.249.1",
        notes="Router .1, Switch .2",
    )
    a.refresh_from_db()
    assert a.cidr.prefixlen == 28
    assert str(a.gateway) == "217.61.249.1"


@pytest.mark.django_db
def test_assignment_orders_by_cidr(pool_v4):
    c = Customer.objects.create(name="X")
    Assignment.objects.create(pool=pool_v4, customer=c, cidr="217.61.249.16/28")
    Assignment.objects.create(pool=pool_v4, customer=c, cidr="217.61.249.0/28")
    cidrs = [str(a.cidr) for a in pool_v4.assignments.all()]
    assert cidrs == ["217.61.249.0/28", "217.61.249.16/28"]


@pytest.mark.django_db
def test_assignment_must_be_inside_pool(pool_v4):
    c = Customer.objects.create(name="Outsider")
    a = Assignment(pool=pool_v4, customer=c, cidr="10.0.0.0/24")
    with pytest.raises(ValidationError) as exc:
        a.full_clean()
    assert "innerhalb" in str(exc.value).lower() or "inside" in str(exc.value).lower()


@pytest.mark.django_db
def test_assignment_ip_family_must_match_pool(pool_v4):
    c = Customer.objects.create(name="V6User")
    a = Assignment(pool=pool_v4, customer=c, cidr="2a05:ed80:100:1::/64")
    with pytest.raises(ValidationError):
        a.full_clean()


@pytest.mark.django_db
def test_assignments_in_same_pool_cannot_overlap(pool_v4):
    c1 = Customer.objects.create(name="A")
    c2 = Customer.objects.create(name="B")
    Assignment.objects.create(pool=pool_v4, customer=c1, cidr="217.61.249.0/28")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(pool=pool_v4, customer=c2, cidr="217.61.249.8/29")


@pytest.mark.django_db
def test_assignments_in_different_pools_can_overlap_logically(pool_v4, pool_v6):
    # Different pools = different rows in the EXCLUDE constraint partition,
    # so logically overlapping CIDRs in unrelated pools are allowed.
    # Use CIDRs that match each pool's family.
    c = Customer.objects.create(name="Z")
    Assignment.objects.create(pool=pool_v4, customer=c, cidr="217.61.249.0/28")
    Assignment.objects.create(pool=pool_v6, customer=c, cidr="2a05:ed80:100:1::/64")
