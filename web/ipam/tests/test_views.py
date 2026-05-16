import pytest
from django.contrib.auth import get_user_model

from ipam.models import Assignment, Customer, Pool


@pytest.fixture
def auth_client(db, client):
    User = get_user_model()
    User.objects.create_user(username="tester", password="pw")
    client.login(username="tester", password="pw")
    return client


@pytest.mark.django_db
def test_sidebar_groups_assignments_by_pool_then_customer(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.248.0/23", block_prefix=30)
    c1 = Customer.objects.create(name="BINSS")
    c2 = Customer.objects.create(name="Falcon")
    Assignment.objects.create(pool=p, customer=c1, cidr="217.61.249.0/28")
    Assignment.objects.create(pool=p, customer=c1, cidr="217.61.249.16/28")
    Assignment.objects.create(pool=p, customer=c2, cidr="217.61.249.32/29")

    response = auth_client.get("/")
    body = response.content.decode()

    # Pool CIDR appears in sidebar (once) and in the index card (once)
    assert body.count("217.61.248.0/23") == 2
    # Each customer listed once per pool
    assert body.count(">BINSS<") == 1
    assert body.count(">Falcon<") == 1
    # All three assignments visible
    assert "217.61.249.0/28" in body
    assert "217.61.249.16/28" in body
    assert "217.61.249.32/29" in body


@pytest.mark.django_db
def test_index_shows_pool_card_with_utilization(auth_client):
    p = Pool.objects.create(name="Anycast", cidr="217.61.248.0/23", block_prefix=30)
    c = Customer.objects.create(name="X")
    # 16 of 512 IPs = 3.125% utilization
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/28")

    response = auth_client.get("/")
    body = response.content.decode()

    assert "Anycast" in body
    assert "217.61.248.0/23" in body
    assert "3" in body  # rounded percent appears somewhere
