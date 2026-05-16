import pytest


@pytest.fixture
def pool_v4(db):
    from ipam.models import Pool
    return Pool.objects.create(
        name="Anycast 217.61.248.0/23",
        cidr="217.61.248.0/23",
        block_prefix=30,
    )


@pytest.fixture
def pool_v6(db):
    from ipam.models import Pool
    return Pool.objects.create(
        name="IPv6 2a05:ed80:100::/48",
        cidr="2a05:ed80:100::/48",
    )
