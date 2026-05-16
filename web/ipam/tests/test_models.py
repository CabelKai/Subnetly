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
