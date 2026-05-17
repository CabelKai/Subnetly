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
    p = Pool.objects.create(name="P", cidr="217.61.248.0/23", )
    a1 = Application.objects.create(name="BINSS")
    a2 = Application.objects.create(name="Falcon")
    s1 = Assignment.objects.create(pool=p, cidr="217.61.249.0/28")
    s1.applications.add(a1)
    s2 = Assignment.objects.create(pool=p, cidr="217.61.249.16/28")
    s2.applications.add(a1)
    s3 = Assignment.objects.create(pool=p, cidr="217.61.249.32/29")
    s3.applications.add(a2)

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
    p = Pool.objects.create(name="Anycast", cidr="217.61.248.0/23", )
    a = Application.objects.create(name="X")
    # 16 of 512 IPs = 3.125% utilization
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/28")
    s.applications.add(a)

    response = auth_client.get("/")
    body = response.content.decode()

    assert "Anycast" in body
    assert "217.61.248.0/23" in body
    assert "3" in body  # rounded percent appears somewhere


@pytest.mark.django_db
def test_ipv4_pool_detail_shows_grid_with_blocks(auth_client):
    """Pool detail page renders a block grid for IPv4 pools."""
    p = Pool.objects.create(name="TestPool", cidr="10.0.0.0/28", )
    a = Application.objects.create(name="Acme")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/30")
    s.applications.add(a)

    response = auth_client.get(f"/pool/{p.id}/")
    assert response.status_code == 200
    body = response.content.decode()

    # Pool name appears in the page
    assert "TestPool" in body
    # Application name appears for the assigned block
    assert "Acme" in body
    # The assigned CIDR appears
    assert "10.0.0.0/30" in body
    # Flex-wrap layout is present
    assert "flex flex-wrap" in body or "flex-wrap" in body
    # Free block indicator (German UI uses "frei")
    assert "frei" in body.lower()


@pytest.mark.django_db
def test_ipv6_pool_detail_lists_assignments(auth_client):
    """Pool detail page renders a table of assignments for IPv6 pools."""
    p = Pool.objects.create(name="v6Pool", cidr="2001:db8::/32")
    a1 = Application.objects.create(name="AlphaNet")
    a2 = Application.objects.create(name="BetaCorp")
    s1 = Assignment.objects.create(pool=p, cidr="2001:db8:1::/48")
    s1.applications.add(a1)
    s2 = Assignment.objects.create(pool=p, cidr="2001:db8:2::/48")
    s2.applications.add(a2)

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
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", )
    a1 = Application.objects.create(name="A")
    b = Application.objects.create(name="B")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a1)

    response = auth_client.post(f"/pool/{p.id}/assign/new/", {
        "applications": [b.id],
        "cidr": "217.61.249.0/29",
        "notes": "",
    })
    body = response.content.decode()
    assert response.status_code == 200  # form re-rendered, not 302
    assert "Überschnei" in body  # German error text


@pytest.mark.django_db
def test_assignment_new_happy_path_redirects(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", )
    a = Application.objects.create(name="A")

    response = auth_client.post(f"/pool/{p.id}/assign/new/", {
        "applications": [a.id],
        "cidr": "217.61.249.0/30",
        "notes": "Router",
    })
    assert response.status_code == 302
    assert Assignment.objects.filter(pool=p, cidr="217.61.249.0/30").exists()


@pytest.mark.django_db
def test_assignment_edit_loads_and_saves(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", )
    a = Application.objects.create(name="A")
    asgn = Assignment.objects.create(pool=p, cidr="217.61.249.0/30", notes="old")
    asgn.applications.add(a)

    response = auth_client.get(f"/assignment/{asgn.id}/edit/")
    assert response.status_code == 200

    response = auth_client.post(f"/assignment/{asgn.id}/edit/", {
        "applications": [a.id],
        "cidr": "217.61.249.0/30",
        "notes": "new",
    })
    assert response.status_code == 302
    asgn.refresh_from_db()
    assert asgn.notes == "new"


@pytest.mark.django_db
def test_application_list_shows_count(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", )
    a = Application.objects.create(name="BINSS")
    s1 = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s1.applications.add(a)
    s2 = Assignment.objects.create(pool=p, cidr="217.61.249.4/30")
    s2.applications.add(a)

    response = auth_client.get("/anwendungen/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "2" in body  # count appears


@pytest.mark.django_db
def test_application_detail_lists_assignments(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", )
    a = Application.objects.create(name="BINSS")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)

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


@pytest.mark.django_db
def test_pool_new_ipv4_happy_path(auth_client):
    response = auth_client.post("/pool/new/", {
        "name": "P",
        "cidr": "10.0.0.0/24",
        "notes": "",
    })
    assert response.status_code == 302
    assert Pool.objects.filter(cidr="10.0.0.0/24").exists()


@pytest.mark.django_db
def test_pool_new_ipv6_happy_path(auth_client):
    response = auth_client.post("/pool/new/", {
        "name": "P6",
        "cidr": "2001:db8::/32",
        "notes": "",
    })
    assert response.status_code == 302
    p = Pool.objects.get(cidr="2001:db8::/32")
    assert p.ip_version == 6


@pytest.mark.django_db
def test_pool_edit_loads_and_saves(auth_client):
    p = Pool.objects.create(name="Old", cidr="10.1.0.0/24")
    response = auth_client.get(f"/pool/{p.id}/edit/")
    assert response.status_code == 200

    response = auth_client.post(f"/pool/{p.id}/edit/", {
        "name": "NewName",
        "cidr": "10.1.0.0/24",
        "notes": "edited",
    })
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.name == "NewName"
    assert p.notes == "edited"
