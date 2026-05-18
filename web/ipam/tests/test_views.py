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
    # Block-grid layout is present (flex with grow-to-fill rows)
    assert "flex flex-wrap" in body
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
    assert "Bearbeiten" in body  # responsive card layout, not table


@pytest.mark.django_db
def test_pool_color_uses_first_app_alphabetically(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/28")
    z = Application.objects.create(name="Zulu")
    a = Application.objects.create(name="Alpha")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/30")
    s.applications.add(z, a)

    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()
    assert "Alpha" in body and "Zulu" in body


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
    asgn = Assignment.objects.get(pool=p, cidr="217.61.249.0/30")
    assert list(asgn.applications.all()) == [a]


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


@pytest.mark.django_db
def test_pool_edit_rejects_cidr_that_excludes_existing_assignment(auth_client):
    """Changing a pool's CIDR must not orphan its existing assignments."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.128/25")
    s.applications.add(a)

    response = auth_client.post(f"/pool/{p.id}/edit/", {
        "name": "P",
        "cidr": "10.0.0.0/26",  # 10.0.0.128/25 lies outside this
        "notes": "",
    })
    assert response.status_code == 200  # re-rendered with error
    body = response.content.decode()
    assert "10.0.0.128/25" in body
    p.refresh_from_db()
    assert str(p.cidr) == "10.0.0.0/24"  # unchanged


@pytest.mark.django_db
def test_pool_edit_rejects_changing_ip_version_with_existing_assignments(auth_client):
    """Pool with IPv4 assignments must not be flipped to IPv6 (or vice versa)."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)

    response = auth_client.post(f"/pool/{p.id}/edit/", {
        "name": "P",
        "cidr": "2001:db8::/32",
        "notes": "",
    })
    assert response.status_code == 200
    p.refresh_from_db()
    assert p.ip_version == 4
    assert str(p.cidr) == "10.0.0.0/24"


@pytest.mark.django_db
def test_pool_edit_allows_cidr_widening(auth_client):
    """Widening a pool's CIDR (still covering all assignments) is allowed."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)

    response = auth_client.post(f"/pool/{p.id}/edit/", {
        "name": "P",
        "cidr": "10.0.0.0/23",
        "notes": "",
    })
    assert response.status_code == 302
    p.refresh_from_db()
    assert str(p.cidr) == "10.0.0.0/23"


@pytest.mark.django_db
def test_assignment_form_rejects_removal_of_app_with_ip_assignments(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
    a1 = Application.objects.create(name="A1")
    a2 = Application.objects.create(name="A2")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a1, a2)
    IPAssignment.objects.create(assignment=s, address="217.61.249.1", application=a1)

    response = auth_client.post(f"/assignment/{s.id}/edit/", {
        "applications": [a2.id],
        "cidr": "217.61.249.0/30",
        "notes": "",
    })
    assert response.status_code == 200
    body = response.content.decode()
    assert "A1" in body
    assert "IP-Zuordnungen" in body or "IP-Zuordnung" in body
    s.refresh_from_db()
    assert set(s.applications.values_list("name", flat=True)) == {"A1", "A2"}


@pytest.mark.django_db
def test_assignment_edit_renders_full_iplist_for_small_subnet(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)

    response = auth_client.get(f"/assignment/{s.id}/edit/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "217.61.249.0" in body
    assert "217.61.249.1" in body
    assert "217.61.249.2" in body
    assert "217.61.249.3" in body
    assert "IP-Zuordnung" in body


@pytest.mark.django_db
def test_assignment_edit_renders_sparse_iplist_for_large_subnet(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.248.0/22")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/24")
    s.applications.add(a)
    IPAssignment.objects.create(assignment=s, address="217.61.249.10", application=a)

    response = auth_client.get(f"/assignment/{s.id}/edit/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "217.61.249.10" in body
    assert body.count("217.61.249.") < 30
    assert "hinzufügen" in body.lower() or "anlegen" in body.lower()


@pytest.mark.django_db
def test_ip_assignment_save_creates_new_row(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)

    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "address": "217.61.249.1",
        "application": a.id,
        "label": "Router-A",
        "notes": "",
    })
    assert response.status_code == 302
    ip = IPAssignment.objects.get(assignment=s, address="217.61.249.1")
    assert ip.application == a
    assert ip.label == "Router-A"
    assert ip.is_gateway is False


@pytest.mark.django_db
def test_ip_assignment_save_updates_existing_row(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)
    IPAssignment.objects.create(assignment=s, address="217.61.249.1", application=a, label="old")

    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "address": "217.61.249.1",
        "application": a.id,
        "label": "new",
        "notes": "",
    })
    assert response.status_code == 302
    ip = IPAssignment.objects.get(assignment=s, address="217.61.249.1")
    assert ip.label == "new"


@pytest.mark.django_db
def test_ip_assignment_save_setting_gateway_clears_others(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)
    old_gw = IPAssignment.objects.create(
        assignment=s, address="217.61.249.1", application=a, is_gateway=True,
    )

    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "address": "217.61.249.2",
        "application": a.id,
        "is_gateway": "on",
        "label": "",
        "notes": "",
    })
    assert response.status_code == 302
    old_gw.refresh_from_db()
    assert old_gw.is_gateway is False
    new_gw = IPAssignment.objects.get(assignment=s, address="217.61.249.2")
    assert new_gw.is_gateway is True


@pytest.mark.django_db
def test_ip_assignment_save_rejects_app_outside_subnet(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a1 = Application.objects.create(name="A1")
    a2 = Application.objects.create(name="A2")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a1)

    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "address": "217.61.249.1",
        "application": a2.id,
        "label": "",
        "notes": "",
    })
    assert response.status_code == 200
    body = response.content.decode()
    assert "gültige" in body.lower() or "valid" in body.lower()


@pytest.mark.django_db
def test_ip_assignment_save_renders_errors_inline_on_validation_failure(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)

    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "address": "10.0.0.1",
        "application": a.id,
        "label": "",
        "notes": "",
    })
    assert response.status_code == 200
    body = response.content.decode()
    assert "Subnetz" in body


@pytest.mark.django_db
def test_assignment_edit_renders_add_row_for_empty_large_subnet(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.248.0/22")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/24")
    s.applications.add(a)
    # no IPAssignments yet

    response = auth_client.get(f"/assignment/{s.id}/edit/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "hinzufügen" in body.lower()


@pytest.mark.django_db
def test_ip_assignment_delete_rejects_get(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)
    ip = IPAssignment.objects.create(assignment=s, address="217.61.249.1", application=a)

    # GET must be redirected, NOT delete the row
    response = auth_client.get(f"/subnet/{s.id}/ip/{ip.id}/delete/")
    assert response.status_code == 302
    assert IPAssignment.objects.filter(pk=ip.pk).exists()

    # POST does delete
    response = auth_client.post(f"/subnet/{s.id}/ip/{ip.id}/delete/")
    assert response.status_code == 302
    assert not IPAssignment.objects.filter(pk=ip.pk).exists()


@pytest.mark.django_db
def test_ip_assignment_save_with_action_delete_removes_row(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)
    ip = IPAssignment.objects.create(assignment=s, address="217.61.249.1", application=a)

    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "action": "delete",
        "ip_id": ip.id,
        "address": "217.61.249.1",
        "application": a.id,
    })
    assert response.status_code == 302
    assert not IPAssignment.objects.filter(pk=ip.pk).exists()


@pytest.mark.django_db
def test_assignment_edit_header_shows_pool_range(auth_client):
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/29")
    s.applications.add(a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    assert "Subnetz aus dem Pool" in body
    assert "10.20.30.0/24" in body
    assert "10.20.30.0" in body
    assert "10.20.30.255" in body


@pytest.mark.django_db
def test_assignment_edit_marks_network_and_broadcast_rows(auth_client):
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/30")
    s.applications.add(a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    assert "Netzwerk-Adresse" in body
    assert "Broadcast-Adresse" in body


@pytest.mark.django_db
def test_ip_assignment_save_bulk_creates_multiple_rows(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/29")  # 8 IPs
    s.applications.add(a)
    # /29 rows in order: .0 (net), .1, .2, .3, .4, .5, .6, .7 (bcast)
    # Reserved indices: 0 (net) and 7 (bcast) — skipped.
    # Editable indices: r1, r2, r3, r4, r5, r6
    response = auth_client.post(f"/subnet/{s.id}/ip/save_bulk/", {
        "r1-address": "10.20.30.1",
        "r1-application": a.id,
        "r1-label": "first",
        "r1-notes": "",
        "r2-address": "10.20.30.2",
        "r2-application": a.id,
        "r2-label": "second",
        "r2-notes": "",
    })
    assert response.status_code == 302
    assert IPAssignment.objects.filter(assignment=s).count() == 2
    assert IPAssignment.objects.get(assignment=s, address="10.20.30.1").label == "first"
    assert IPAssignment.objects.get(assignment=s, address="10.20.30.2").label == "second"


@pytest.mark.django_db
def test_ip_assignment_save_bulk_rolls_back_on_error(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a1 = Application.objects.create(name="A1")
    a2 = Application.objects.create(name="A2")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/29")
    s.applications.add(a1)  # only a1, NOT a2
    response = auth_client.post(f"/subnet/{s.id}/ip/save_bulk/", {
        "r1-address": "10.20.30.1",
        "r1-application": a1.id,
        "r1-label": "ok",
        "r1-notes": "",
        "r2-address": "10.20.30.2",
        "r2-application": a2.id,  # invalid — app not in subnet
        "r2-label": "bad",
        "r2-notes": "",
    })
    assert response.status_code == 200  # re-renders with errors
    assert IPAssignment.objects.filter(assignment=s).count() == 0  # nothing saved


@pytest.mark.django_db
def test_ip_assignment_save_bulk_rejects_multiple_gateways(auth_client):
    """User checks two `is_gateway` boxes in one POST → must error, not silently
    keep only the last. Constraint allows max one gateway per subnet."""
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/29")
    s.applications.add(a)
    response = auth_client.post(f"/subnet/{s.id}/ip/save_bulk/", {
        "r1-address": "10.20.30.1",
        "r1-application": a.id,
        "r1-is_gateway": "on",
        "r1-label": "first",
        "r1-notes": "",
        "r2-address": "10.20.30.2",
        "r2-application": a.id,
        "r2-is_gateway": "on",
        "r2-label": "second",
        "r2-notes": "",
    })
    assert response.status_code == 200  # re-rendered with error
    assert IPAssignment.objects.filter(assignment=s).count() == 0  # nothing saved
    body = response.content.decode()
    assert "Gateway" in body  # error mentions gateway


@pytest.mark.django_db
def test_ip_assignment_save_bulk_skips_untouched_full_mode_rows(auth_client):
    """In full-mode the template emits a hidden address input for every row.

    A POST that only fills the application on ONE row must still succeed —
    the other rows have addresses (from the hidden inputs) but no application
    and must be skipped, not validated as failures.
    """
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/29")  # 8 IPs, full-mode
    s.applications.add(a)
    # Simulate what the template POSTs: addresses for ALL non-reserved rows
    # (r0 = .0 network, r7 = .7 broadcast → skipped by the view).
    # Only r3 has an application filled in by the user.
    response = auth_client.post(f"/subnet/{s.id}/ip/save_bulk/", {
        "r1-address": "10.20.30.1", "r1-application": "", "r1-label": "", "r1-notes": "",
        "r2-address": "10.20.30.2", "r2-application": "", "r2-label": "", "r2-notes": "",
        "r3-address": "10.20.30.3", "r3-application": a.id, "r3-label": "router", "r3-notes": "",
        "r4-address": "10.20.30.4", "r4-application": "", "r4-label": "", "r4-notes": "",
        "r5-address": "10.20.30.5", "r5-application": "", "r5-label": "", "r5-notes": "",
        "r6-address": "10.20.30.6", "r6-application": "", "r6-label": "", "r6-notes": "",
    })
    assert response.status_code == 302
    assert IPAssignment.objects.filter(assignment=s).count() == 1
    assert IPAssignment.objects.get(assignment=s, address="10.20.30.3").label == "router"


@pytest.mark.django_db
def test_ip_assignment_clean_rejects_network_address(auth_client):
    from ipam.models import IPAssignment
    from django.core.exceptions import ValidationError
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/30")
    s.applications.add(a)
    ip = IPAssignment(assignment=s, address="10.20.30.0", application=a)
    with pytest.raises(ValidationError) as exc:
        ip.full_clean()
    assert "address" in exc.value.error_dict


@pytest.mark.django_db
def test_ip_assignment_clean_rejects_broadcast_address(auth_client):
    from ipam.models import IPAssignment
    from django.core.exceptions import ValidationError
    p = Pool.objects.create(name="P", cidr="10.20.30.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.20.30.0/30")
    s.applications.add(a)
    ip = IPAssignment(assignment=s, address="10.20.30.3", application=a)
    with pytest.raises(ValidationError) as exc:
        ip.full_clean()
    assert "address" in exc.value.error_dict


@pytest.mark.django_db
def test_mobile_navigation_markup_present(auth_client):
    response = auth_client.get("/")
    body = response.content.decode()
    assert 'id="nav-toggle"' in body
    assert 'for="nav-toggle"' in body
    assert "peer-checked/drawer:translate-x-0" in body


@pytest.mark.django_db
def test_assignment_edit_renders_pill_picker(auth_client):
    """Applications field renders as pill-toggle labels, not <ul>/<li> checkboxes."""
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
    a1 = Application.objects.create(name="Mail-Server")
    a2 = Application.objects.create(name="DNS")
    asgn = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    asgn.applications.add(a1)  # one selected, one not

    response = auth_client.get(f"/assignment/{asgn.id}/edit/")
    assert response.status_code == 200
    body = response.content.decode()

    # Pill container present
    assert 'class="flex flex-wrap gap-2"' in body
    # Each application rendered as a <label> with pill classes
    assert body.count("has-[:checked]:bg-slate-900") == 2
    assert "Mail-Server" in body
    assert "DNS" in body
    # Real checkbox inputs still in the DOM (existing JS depends on them)
    assert 'name="applications"' in body
    assert 'type="checkbox"' in body
    # sr-only hides the native checkbox visually
    assert 'class="sr-only"' in body
    # No <ul>/<li> markup from the default CheckboxSelectMultiple template
    assert '<ul id="id_applications"' not in body
    # Selected application's input carries the `checked` attribute.
    # Leading space disambiguates from Tailwind's `has-[:checked]:` class strings.
    assert " checked" in body


# ---------- Delete views ----------

@pytest.mark.django_db
def test_pool_delete_happy_path(auth_client):
    p = Pool.objects.create(name="Empty", cidr="10.0.0.0/24")
    response = auth_client.post(f"/pool/{p.id}/delete/")
    assert response.status_code == 302
    assert response.url == "/"
    assert not Pool.objects.filter(pk=p.pk).exists()


@pytest.mark.django_db
def test_pool_delete_blocked_by_assignments_does_not_delete(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    response = auth_client.post(f"/pool/{p.id}/delete/")
    assert response.status_code == 302  # redirect back to detail, not delete
    assert Pool.objects.filter(pk=p.pk).exists()


@pytest.mark.django_db
def test_pool_delete_get_returns_405(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    response = auth_client.get(f"/pool/{p.id}/delete/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_application_delete_happy_path(auth_client):
    a = Application.objects.create(name="Unused")
    response = auth_client.post(f"/anwendung/{a.id}/delete/")
    assert response.status_code == 302
    assert response.url == "/anwendungen/"
    assert not Application.objects.filter(pk=a.pk).exists()


@pytest.mark.django_db
def test_application_delete_blocked_by_ip_assignments_does_not_delete(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    IPAssignment.objects.create(assignment=s, address="10.0.0.1", application=a)
    response = auth_client.post(f"/anwendung/{a.id}/delete/")
    assert response.status_code == 302
    assert Application.objects.filter(pk=a.pk).exists()


@pytest.mark.django_db
def test_application_delete_get_returns_405(auth_client):
    a = Application.objects.create(name="A")
    response = auth_client.get(f"/anwendung/{a.id}/delete/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_assignment_delete_happy_path(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    response = auth_client.post(f"/assignment/{s.id}/delete/")
    assert response.status_code == 302
    assert response.url == f"/pool/{p.id}/"
    assert not Assignment.objects.filter(pk=s.pk).exists()


@pytest.mark.django_db
def test_assignment_delete_cascades_ip_assignments(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    IPAssignment.objects.create(assignment=s, address="10.0.0.1", application=a)
    IPAssignment.objects.create(assignment=s, address="10.0.0.2", application=a)
    assert IPAssignment.objects.count() == 2
    response = auth_client.post(f"/assignment/{s.id}/delete/")
    assert response.status_code == 302
    assert IPAssignment.objects.count() == 0


@pytest.mark.django_db
def test_assignment_delete_get_returns_405(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    response = auth_client.get(f"/assignment/{s.id}/delete/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_pool_detail_shows_delete_dialog_with_blockers_when_assignments_exist(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="MyApp")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()
    # Dialog markup present
    assert 'id="delete-dialog"' in body
    # Title is fixed
    assert "Pool löschen?" in body
    # Blocker shown (CIDR + app)
    assert "10.0.0.0/28" in body
    assert "MyApp" in body
    # Submit button hidden when blockers exist
    assert "Endgültig löschen" not in body


@pytest.mark.django_db
def test_pool_detail_shows_delete_button_on_empty_pool(auth_client):
    p = Pool.objects.create(name="Empty", cidr="10.0.0.0/24")
    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()
    assert 'id="delete-dialog"' in body
    assert "Endgültig löschen" in body  # submit button present


@pytest.mark.django_db
def test_application_detail_shows_cascade_message_when_no_blockers(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="NoIPsYet")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)  # M2M ref but no IPAssignment
    response = auth_client.get(f"/anwendung/{a.id}/")
    body = response.content.decode()
    assert 'id="delete-dialog"' in body
    assert "Anwendung löschen?" in body
    # Cascade message mentions the 1 subnet
    assert "1" in body and "Subnetz" in body
    # Submit button present (no blockers)
    assert "Endgültig löschen" in body


@pytest.mark.django_db
def test_application_detail_shows_blockers_when_ip_assignments_exist(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    IPAssignment.objects.create(assignment=s, address="10.0.0.1", application=a)
    response = auth_client.get(f"/anwendung/{a.id}/")
    body = response.content.decode()
    assert 'id="delete-dialog"' in body
    assert "10.0.0.1" in body
    assert "10.0.0.0/28" in body
    # Submit button hidden when blockers exist
    assert "Endgültig löschen" not in body


@pytest.mark.django_db
def test_assignment_edit_mobile_rows_have_gap_between_label_and_input(auth_client):
    """Regression guard: mobile-view mini-labels and form inputs in IP rows
    must have a `gap-3` on their flex container, otherwise `w-full` on the
    input pushes it flush against the label with zero visible spacing."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/29")
    s.applications.add(a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    # The 5 field rows per IP each have `flex justify-between items-center md:block`.
    # After the fix, each such row also has `gap-3` to keep label and input apart.
    # Count the full mobile-row signature with gap-3.
    assert body.count("justify-between items-center gap-3 md:block") >= 5


@pytest.mark.django_db
def test_assignment_edit_shows_cascade_message_with_ip_count(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    IPAssignment.objects.create(assignment=s, address="10.0.0.1", application=a)
    IPAssignment.objects.create(assignment=s, address="10.0.0.2", application=a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    assert 'id="delete-dialog"' in body
    assert "Subnetz löschen?" in body
    # Cascade message mentions count
    assert "2" in body and "IP-Zuordnung" in body
    # Submit button present (Assignment never has blockers, only cascades)
    assert "Endgültig löschen" in body


@pytest.mark.django_db
def test_sidebar_uses_h2_not_h3(auth_client):
    """A1: Sidebar section headings must be <h2> (after page <h1>), not <h3>."""
    Pool.objects.create(name="P", cidr="10.0.0.0/24")
    response = auth_client.get("/")
    body = response.content.decode()
    assert ">IP-Pools</h2>" in body
    assert ">Anwendungen</h2>" in body
    assert ">IP-Pools</h3>" not in body
    assert ">Anwendungen</h3>" not in body


@pytest.mark.django_db
def test_skip_to_content_link_present(auth_client):
    """A2: Skip-link must be the first focusable element, target main content."""
    response = auth_client.get("/")
    body = response.content.decode()
    assert "Zum Inhalt springen" in body
    assert 'href="#main"' in body
    assert 'id="main"' in body


# ---------- C1: Toast messages ----------

@pytest.mark.django_db
def test_pool_create_shows_success_toast(auth_client):
    """C1: After POST→Redirect, a success toast appears in the rendered page."""
    response = auth_client.post("/pool/new/", {
        "name": "T", "cidr": "10.0.0.0/24", "notes": "",
    }, follow=True)
    body = response.content.decode()
    assert "Pool angelegt." in body


@pytest.mark.django_db
def test_pool_delete_shows_success_toast(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    response = auth_client.post(f"/pool/{p.id}/delete/", follow=True)
    body = response.content.decode()
    assert "Pool gelöscht." in body


@pytest.mark.django_db
def test_pool_delete_blocked_shows_warning_toast(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    response = auth_client.post(f"/pool/{p.id}/delete/", follow=True)
    body = response.content.decode()
    assert "Pool nicht gelöscht" in body
    assert "border-amber-500" in body  # warning border color


@pytest.mark.django_db
def test_assignment_delete_shows_success_toast(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/28")
    s.applications.add(a)
    response = auth_client.post(f"/assignment/{s.id}/delete/", follow=True)
    body = response.content.decode()
    assert "Subnetz gelöscht." in body


@pytest.mark.django_db
def test_assignment_edit_mobile_uses_real_label_elements(auth_client):
    """A3: Mobile mini-labels must be <label for=...>, not <span>."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/29")
    s.applications.add(a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    label_count = body.count('<label class="md:hidden text-xs font-semibold')
    assert label_count >= 5, f"expected >=5 mobile <label> elements, got {label_count}"


@pytest.mark.django_db
def test_mobile_drawer_has_aria_attributes(auth_client):
    """A5: Mobile drawer has accessible attributes — aria-controls + aria-expanded."""
    response = auth_client.get("/")
    body = response.content.decode()
    assert 'aria-controls="sidebar-drawer"' in body
    assert 'aria-expanded="false"' in body
    assert 'id="sidebar-drawer"' in body


@pytest.mark.django_db
def test_no_blue_primary_cta_on_index(auth_client):
    """B2: Primary CTAs are slate-800, never blue-600."""
    response = auth_client.get("/")
    body = response.content.decode()
    assert "bg-blue-600" not in body


@pytest.mark.django_db
def test_no_blue_primary_cta_on_application_list(auth_client):
    response = auth_client.get("/anwendungen/")
    body = response.content.decode()
    assert "bg-blue-600" not in body


@pytest.mark.django_db
def test_no_blue_primary_cta_on_pool_detail(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()
    assert "bg-blue-600" not in body


@pytest.mark.django_db
def test_reserved_row_uses_distinctive_styling(auth_client):
    """B3: Network/Broadcast rows have a left-border indicator (slate-300)."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/30")  # /30 has net + bcast
    s.applications.add(a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    assert "border-l-4 border-l-slate-300" in body
    assert "Netzwerk-Adresse" in body
    assert "Broadcast-Adresse" in body


@pytest.mark.django_db
def test_assignment_edit_address_inputs_have_inputmode_and_pattern(auth_client):
    """C3: Address inputs include inputmode=numeric and pattern for mobile keyboard hint."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/22")  # /22 = sparse
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/24")
    s.applications.add(a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    # Sparse-mode "Neue IP hinzufügen" input has the attrs
    assert 'inputmode="numeric"' in body
    assert 'pattern="[0-9a-fA-F:.]+"' in body


@pytest.mark.django_db
def test_index_empty_state_links_to_pool_new(auth_client):
    """C4: When no pools exist, empty state links to /pool/new/, not /admin/."""
    response = auth_client.get("/")
    body = response.content.decode()
    assert 'href="/pool/new/"' in body
    assert 'Pool anlegen' in body
    assert '<a href="/admin/" class="underline">Admin</a>' not in body


@pytest.mark.django_db
def test_main_has_no_overflow_x_auto(auth_client):
    """C5: <main> no longer has overflow-x-auto (moved to grid container)."""
    response = auth_client.get("/")
    body = response.content.decode()
    import re
    m = re.search(r"<main[^>]*>", body)
    assert m, "main tag not found"
    assert "overflow-x-auto" not in m.group(0)


@pytest.mark.django_db
def test_ipv4_grid_container_has_overflow_x_auto(auth_client):
    """C5: The IPv4 grid container itself owns overflow-x-auto (scoped)."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()
    assert "flex flex-wrap gap-1 items-stretch overflow-x-auto" in body
