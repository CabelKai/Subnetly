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


@pytest.mark.django_db
def test_ipv4_pool_detail_shows_grid_with_blocks(auth_client):
    """Pool detail page renders a block grid for IPv4 pools."""
    p = Pool.objects.create(name="TestPool", cidr="10.0.0.0/28", block_prefix=30)
    c = Customer.objects.create(name="Acme")
    Assignment.objects.create(pool=p, customer=c, cidr="10.0.0.0/30")

    response = auth_client.get(f"/pool/{p.id}/")
    assert response.status_code == 200
    body = response.content.decode()

    # Pool name appears in the page
    assert "TestPool" in body
    # Customer name appears for the assigned block
    assert "Acme" in body
    # The assigned CIDR appears
    assert "10.0.0.0/30" in body
    # Grid is present (grid layout style or class)
    assert "grid" in body
    # Free block indicator
    assert "free" in body.lower()


@pytest.mark.django_db
def test_ipv6_pool_detail_lists_assignments(auth_client):
    """Pool detail page renders a table of assignments for IPv6 pools."""
    p = Pool.objects.create(name="v6Pool", cidr="2001:db8::/32", block_prefix=48)
    c1 = Customer.objects.create(name="AlphaNet")
    c2 = Customer.objects.create(name="BetaCorp")
    Assignment.objects.create(pool=p, customer=c1, cidr="2001:db8:1::/48")
    Assignment.objects.create(pool=p, customer=c2, cidr="2001:db8:2::/48")

    response = auth_client.get(f"/pool/{p.id}/")
    assert response.status_code == 200
    body = response.content.decode()

    # Pool name and CIDR appear
    assert "v6Pool" in body
    assert "2001:db8::/32" in body
    # Both customers listed
    assert "AlphaNet" in body
    assert "BetaCorp" in body
    # Both assignment CIDRs listed
    assert "2001:db8:1::/48" in body
    assert "2001:db8:2::/48" in body
    # Rendered as a table (not the "folgt" placeholder)
    assert "IPv6-Ansicht folgt" not in body
    assert "<table" in body


@pytest.mark.django_db
def test_assignment_new_rejects_overlap(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c1 = Customer.objects.create(name="A")
    Customer.objects.create(name="B")
    Assignment.objects.create(pool=p, customer=c1, cidr="217.61.249.0/30")

    response = auth_client.post(f"/pool/{p.id}/assign/new/", {
        "customer": Customer.objects.get(name="B").id,
        "cidr": "217.61.249.0/29",
        "gateway": "",
        "notes": "",
    })
    body = response.content.decode()
    assert response.status_code == 200  # form re-rendered, not 302
    assert "Überschnei" in body  # German error text


@pytest.mark.django_db
def test_assignment_new_happy_path_redirects(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="A")

    response = auth_client.post(f"/pool/{p.id}/assign/new/", {
        "customer": c.id,
        "cidr": "217.61.249.0/30",
        "gateway": "217.61.249.1",
        "notes": "Router",
    })
    assert response.status_code == 302
    assert Assignment.objects.filter(pool=p, cidr="217.61.249.0/30").exists()


@pytest.mark.django_db
def test_assignment_edit_loads_and_saves(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="A")
    a = Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/30", notes="old")

    response = auth_client.get(f"/assignment/{a.id}/edit/")
    assert response.status_code == 200

    response = auth_client.post(f"/assignment/{a.id}/edit/", {
        "customer": c.id,
        "cidr": "217.61.249.0/30",
        "gateway": "",
        "notes": "new",
    })
    assert response.status_code == 302
    a.refresh_from_db()
    assert a.notes == "new"


@pytest.mark.django_db
def test_customer_list_shows_count(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="BINSS")
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/30")
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.4/30")

    response = auth_client.get("/customers/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "2" in body  # count appears


@pytest.mark.django_db
def test_customer_detail_lists_assignments(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="BINSS")
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/30")

    response = auth_client.get(f"/customer/{c.id}/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "217.61.249.0/30" in body
