import pytest
from django.contrib.auth import get_user_model

from ipam.models import Application, Assignment, Pool


@pytest.fixture
def auth_client(db, client):
    User = get_user_model()
    User.objects.create_user(username="tester", password="pw")
    client.login(username="tester", password="pw")
    return client


@pytest.mark.django_db
def test_sidebar_groups_assignments_by_pool_then_application(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.248.0/23", block_prefix=30)
    a1 = Application.objects.create(name="BINSS")
    a2 = Application.objects.create(name="Falcon")
    Assignment.objects.create(pool=p, application=a1, cidr="217.61.249.0/28")
    Assignment.objects.create(pool=p, application=a1, cidr="217.61.249.16/28")
    Assignment.objects.create(pool=p, application=a2, cidr="217.61.249.32/29")

    response = auth_client.get("/")
    body = response.content.decode()

    # Pool CIDR appears in sidebar (once) and in the index card (once)
    assert body.count("217.61.248.0/23") == 2
    # Each application listed once per pool
    assert body.count(">BINSS<") == 1
    assert body.count(">Falcon<") == 1
    # All three assignments visible
    assert "217.61.249.0/28" in body
    assert "217.61.249.16/28" in body
    assert "217.61.249.32/29" in body


@pytest.mark.django_db
def test_index_shows_pool_card_with_utilization(auth_client):
    p = Pool.objects.create(name="Anycast", cidr="217.61.248.0/23", block_prefix=30)
    a = Application.objects.create(name="X")
    # 16 of 512 IPs = 3.125% utilization
    Assignment.objects.create(pool=p, application=a, cidr="217.61.249.0/28")

    response = auth_client.get("/")
    body = response.content.decode()

    assert "Anycast" in body
    assert "217.61.248.0/23" in body
    assert "3" in body  # rounded percent appears somewhere


@pytest.mark.django_db
def test_ipv4_pool_detail_shows_grid_with_blocks(auth_client):
    """Pool detail page renders a block grid for IPv4 pools."""
    p = Pool.objects.create(name="TestPool", cidr="10.0.0.0/28", block_prefix=30)
    a = Application.objects.create(name="Acme")
    Assignment.objects.create(pool=p, application=a, cidr="10.0.0.0/30")

    response = auth_client.get(f"/pool/{p.id}/")
    assert response.status_code == 200
    body = response.content.decode()

    # Pool name appears in the page
    assert "TestPool" in body
    # Application name appears for the assigned block
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
    a1 = Application.objects.create(name="AlphaNet")
    a2 = Application.objects.create(name="BetaCorp")
    Assignment.objects.create(pool=p, application=a1, cidr="2001:db8:1::/48")
    Assignment.objects.create(pool=p, application=a2, cidr="2001:db8:2::/48")

    response = auth_client.get(f"/pool/{p.id}/")
    assert response.status_code == 200
    body = response.content.decode()

    # Pool name and CIDR appear
    assert "v6Pool" in body
    assert "2001:db8::/32" in body
    # Both applications listed
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
    a1 = Application.objects.create(name="A")
    Application.objects.create(name="B")
    Assignment.objects.create(pool=p, application=a1, cidr="217.61.249.0/30")

    response = auth_client.post(f"/pool/{p.id}/assign/new/", {
        "application": Application.objects.get(name="B").id,
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
    a = Application.objects.create(name="A")

    response = auth_client.post(f"/pool/{p.id}/assign/new/", {
        "application": a.id,
        "cidr": "217.61.249.0/30",
        "gateway": "217.61.249.1",
        "notes": "Router",
    })
    assert response.status_code == 302
    assert Assignment.objects.filter(pool=p, cidr="217.61.249.0/30").exists()


@pytest.mark.django_db
def test_assignment_edit_loads_and_saves(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    a = Application.objects.create(name="A")
    asgn = Assignment.objects.create(pool=p, application=a, cidr="217.61.249.0/30", notes="old")

    response = auth_client.get(f"/assignment/{asgn.id}/edit/")
    assert response.status_code == 200

    response = auth_client.post(f"/assignment/{asgn.id}/edit/", {
        "application": a.id,
        "cidr": "217.61.249.0/30",
        "gateway": "",
        "notes": "new",
    })
    assert response.status_code == 302
    asgn.refresh_from_db()
    assert asgn.notes == "new"


@pytest.mark.django_db
def test_application_list_shows_count(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    a = Application.objects.create(name="BINSS")
    Assignment.objects.create(pool=p, application=a, cidr="217.61.249.0/30")
    Assignment.objects.create(pool=p, application=a, cidr="217.61.249.4/30")

    response = auth_client.get("/anwendungen/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "2" in body  # count appears


@pytest.mark.django_db
def test_application_detail_lists_assignments(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    a = Application.objects.create(name="BINSS")
    Assignment.objects.create(pool=p, application=a, cidr="217.61.249.0/30")

    response = auth_client.get(f"/anwendung/{a.id}/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "217.61.249.0/30" in body


@pytest.mark.django_db
def test_application_new_creates_and_redirects(auth_client):
    response = auth_client.post("/anwendung/new/", {
        "name": "NeueApp",
        "notes": "Hallo",
    })
    assert response.status_code == 302
    assert Application.objects.filter(name="NeueApp").exists()


@pytest.mark.django_db
def test_application_new_rejects_duplicate_name(auth_client):
    Application.objects.create(name="Dup")
    response = auth_client.post("/anwendung/new/", {
        "name": "Dup",
        "notes": "",
    })
    body = response.content.decode()
    assert response.status_code == 200  # form re-rendered
    assert "bereits" in body.lower() or "already" in body.lower()


@pytest.mark.django_db
def test_application_edit_loads_and_saves(auth_client):
    a = Application.objects.create(name="OldName", notes="old")
    response = auth_client.get(f"/anwendung/{a.id}/edit/")
    assert response.status_code == 200

    response = auth_client.post(f"/anwendung/{a.id}/edit/", {
        "name": "NewName",
        "notes": "new",
    })
    assert response.status_code == 302
    a.refresh_from_db()
    assert a.name == "NewName"
    assert a.notes == "new"
