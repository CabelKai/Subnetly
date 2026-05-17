import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ipam.models import Application, Assignment, Pool


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
def test_application_name_unique():
    Application.objects.create(name="BINSS")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Application.objects.create(name="BINSS")


@pytest.mark.django_db
def test_assignment_basic_create(pool_v4):
    a_obj = Application.objects.create(name="BINSS")
    a = Assignment.objects.create(
        pool=pool_v4,
        cidr="217.61.249.0/28",
        notes="Router .1, Switch .2",
    )
    a.applications.add(a_obj)
    a.refresh_from_db()
    assert a.cidr.prefixlen == 28
    assert list(a.applications.values_list("name", flat=True)) == ["BINSS"]


@pytest.mark.django_db
def test_assignment_orders_by_cidr(pool_v4):
    a_obj = Application.objects.create(name="X")
    a1 = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.16/28")
    a1.applications.add(a_obj)
    a2 = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/28")
    a2.applications.add(a_obj)
    cidrs = [str(a.cidr) for a in pool_v4.assignments.all()]
    assert cidrs == ["217.61.249.0/28", "217.61.249.16/28"]


@pytest.mark.django_db
def test_assignment_must_be_inside_pool(pool_v4):
    a = Assignment(pool=pool_v4, cidr="10.0.0.0/24")
    with pytest.raises(ValidationError) as exc:
        a.full_clean()
    assert "innerhalb" in str(exc.value).lower() or "inside" in str(exc.value).lower()


@pytest.mark.django_db
def test_assignment_ip_family_must_match_pool(pool_v4):
    a = Assignment(pool=pool_v4, cidr="2a05:ed80:100:1::/64")
    with pytest.raises(ValidationError):
        a.full_clean()


@pytest.mark.django_db
def test_assignments_in_same_pool_cannot_overlap(pool_v4):
    Application.objects.create(name="A")
    Application.objects.create(name="B")
    Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/28")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(pool=pool_v4, cidr="217.61.249.8/29")


@pytest.mark.django_db
def test_assignments_in_different_pools_can_overlap_logically(pool_v4, pool_v6):
    Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/28")
    Assignment.objects.create(pool=pool_v6, cidr="2a05:ed80:100:1::/64")


@pytest.mark.django_db
def test_ip_assignment_basic_create(pool_v4):
    from ipam.models import IPAssignment
    app = Application.objects.create(name="Router-A")
    asgn = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/30")
    asgn.applications.add(app)
    ip = IPAssignment.objects.create(
        assignment=asgn, address="217.61.249.1", application=app,
    )
    ip.refresh_from_db()
    assert str(ip.address) == "217.61.249.1"
    assert ip.is_gateway is False
    assert ip.label == ""
