# Multi-App-Subnets + Per-IP-Assignments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subnetz (`Assignment`) hält mehrere Anwendungen über M2M; jede IP im Subnetz kann einer dieser Anwendungen über ein neues `IPAssignment`-Modell zugeordnet werden. Die Subnetz-Edit-Seite zeigt eine IP-Liste (vollständig bis 32 IPs, sparse darüber) mit Inline-CRUD pro Zeile.

**Architecture:** Datenmodell-Erweiterung in einer Migration (0005) mit Schema + RunPython-Datenmigration + Schema-Drop in einer Datei. UI bleibt klassisch Django + Tailwind: zwei getrennte Form-Bereiche auf der Edit-Seite (Subnetz-Metadaten oben, IP-Liste unten mit jeweils einem Mini-Form pro Zeile). Service-Funktion `build_ip_rows` zentralisiert die Vollständig-vs-Sparse-Entscheidung.

**Tech Stack:** Django 5.0+, PostgreSQL 16 (partielle Unique-Indexe), pytest-django, Tailwind. Docker-Compose-Setup mit Service `web`.

**Test-Befehl:** `docker compose exec web pytest ipam/tests/ -v` (immer aus dem Repo-Root `/srv/docker/IP-Planer/`). Einzeltest: `docker compose exec web pytest ipam/tests/test_models.py::test_name -v`.

**Spec:** `docs/superpowers/specs/2026-05-17-multi-app-subnets-design.md`.

---

## Task 1: Datenbank-Backup (Pre-Migration-Checkpoint)

**Files:** keine — Operator-Schritt.

- [ ] **Step 1: Backup der relevanten Tabellen**

```bash
docker compose exec db pg_dump -U "$DB_USER" -d "$DB_NAME" \
    -t ipam_assignment -t ipam_application \
    --data-only --column-inserts \
    > /srv/docker/IP-Planer/backups/pre-0005-$(date +%Y%m%d-%H%M%S).sql
```

`$DB_USER` und `$DB_NAME` aus `.env`. Falls `backups/`-Verzeichnis fehlt: `mkdir -p /srv/docker/IP-Planer/backups`.

- [ ] **Step 2: Backup-Größe prüfen**

```bash
ls -lh /srv/docker/IP-Planer/backups/pre-0005-*.sql
```

Erwartet: Datei vorhanden, > 0 Bytes, enthält `INSERT INTO ipam_assignment` und `INSERT INTO ipam_application`.

- [ ] **Step 3: Restore-Probe (read-only Verifikation)**

```bash
head -50 /srv/docker/IP-Planer/backups/pre-0005-*.sql
```

Erwartet: SQL-Statements lesbar, kein offensichtlicher Corruption.

---

## Task 2: `IPAssignment`-Modell schreiben (Tests-First)

**Files:**
- Modify: `web/ipam/models.py`
- Test: `web/ipam/tests/test_models.py`

- [ ] **Step 1: Failing Test — IPAssignment basic create**

In `web/ipam/tests/test_models.py` ergänzen (am Ende):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec web pytest ipam/tests/test_models.py::test_ip_assignment_basic_create -v
```

Erwartet: `ImportError: cannot import name 'IPAssignment'` oder ein ähnlicher Fehler über das fehlende Modell.

- [ ] **Step 3: Implementiere `IPAssignment` + M2M in `models.py`**

Ersetze in `web/ipam/models.py` die `Assignment`-Klasse durch:

```python
class Assignment(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.PROTECT, related_name="assignments")
    applications = models.ManyToManyField(Application, related_name="assignments")
    cidr = CidrAddressField()
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]

    def clean(self):
        super().clean()
        if not self.pool_id or self.cidr is None:
            return
        from netaddr import IPNetwork
        pool_net = IPNetwork(str(self.pool.cidr))
        ass_net = IPNetwork(str(self.cidr))
        if pool_net.version != ass_net.version:
            raise ValidationError(
                {"cidr": f"IP-Familie passt nicht zum Pool (Pool ist IPv{pool_net.version})."}
            )
        if ass_net not in pool_net:
            raise ValidationError(
                {"cidr": f"{self.cidr} liegt nicht innerhalb des Pools {self.pool.cidr}."}
            )

    def __str__(self):
        names = ", ".join(sorted(a.name for a in self.applications.all())) or "—"
        return f"{self.cidr} → {names}"
```

Und am Dateiende ergänzen:

```python
class IPAssignment(models.Model):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="ip_assignments"
    )
    address = models.GenericIPAddressField()
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="ip_assignments"
    )
    is_gateway = models.BooleanField(default=False)
    label = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["address"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "address"],
                name="ip_unique_per_assignment",
            ),
            models.UniqueConstraint(
                fields=["assignment"],
                condition=models.Q(is_gateway=True),
                name="ip_one_gateway_per_assignment",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.assignment_id or self.address is None:
            return
        import ipaddress
        try:
            net = ipaddress.ip_network(str(self.assignment.cidr), strict=False)
            addr = ipaddress.ip_address(str(self.address))
        except ValueError as exc:
            raise ValidationError({"address": str(exc)})
        if addr.version != net.version:
            raise ValidationError({"address": f"IP-Familie passt nicht zum Subnetz (IPv{net.version})."})
        if addr not in net:
            raise ValidationError(
                {"address": f"{addr} liegt nicht im Subnetz {self.assignment.cidr}."}
            )
        if self.application_id and not self.assignment.applications.filter(pk=self.application_id).exists():
            raise ValidationError(
                {"application": "Anwendung ist nicht in der Subnetz-Liste."}
            )

    def __str__(self):
        return f"{self.address} → {self.application.name}"
```

(Die `Assignment.clean()`-Logik bleibt unverändert von früher — das `application`/`gateway`-FK fällt weg, der Rest bleibt.)

- [ ] **Step 4: Migration ist jetzt erforderlich — wird in Task 3 erzeugt**

Tests laufen noch nicht — die Migration fehlt. Weiter mit Task 3, hier kein Test-Run.

- [ ] **Step 5: Commit (nur Modell, ohne Migration noch nicht run-fähig — kein commit)**

Wir committen erst, wenn Modell **und** Migration zusammen passen (Ende Task 3).

---

## Task 3: Migration `0005_multi_app_subnets`

**Files:**
- Create: `web/ipam/migrations/0005_multi_app_subnets.py`

- [ ] **Step 1: Migration generieren (auto, dann handisch nachbessern)**

```bash
docker compose exec web python manage.py makemigrations ipam --name multi_app_subnets
```

Erwartet: Datei `web/ipam/migrations/0005_multi_app_subnets.py` wird angelegt — sie enthält das M2M-Field, das neue Modell, das Drop von `application` und `gateway`. Inspiziere die Datei.

- [ ] **Step 2: Datenmigration einfügen**

Öffne `web/ipam/migrations/0005_multi_app_subnets.py`. Die generierten Operationen sind voraussichtlich (in dieser Reihenfolge):
1. `AddField(model_name='assignment', name='applications', field=ManyToManyField(...))`
2. `CreateModel(name='IPAssignment', ...)`
3. `RemoveField(model_name='assignment', name='application')`
4. `RemoveField(model_name='assignment', name='gateway')`

Füge **zwischen Operation 2 und 3** eine `RunPython`-Operation ein:

```python
def migrate_data(apps, schema_editor):
    Assignment = apps.get_model("ipam", "Assignment")
    IPAssignment = apps.get_model("ipam", "IPAssignment")
    for a in Assignment.objects.all():
        if a.application_id:
            a.applications.add(a.application_id)
        if a.gateway:
            IPAssignment.objects.create(
                assignment=a,
                address=str(a.gateway),
                application_id=a.application_id,
                is_gateway=True,
            )


def reverse_data(apps, schema_editor):
    Assignment = apps.get_model("ipam", "Assignment")
    IPAssignment = apps.get_model("ipam", "IPAssignment")
    for a in Assignment.objects.all():
        first_app = a.applications.order_by("name").first()
        if first_app is not None:
            a.application_id = first_app.id
        gw = IPAssignment.objects.filter(assignment=a, is_gateway=True).first()
        if gw is not None:
            a.gateway = gw.address
        a.save()
```

Trage diese Funktionen am Anfang der Datei (nach den Imports) ein, dann ergänze in `operations` an der passenden Stelle:

```python
    migrations.RunPython(migrate_data, reverse_code=reverse_data),
```

- [ ] **Step 3: Migrationen ausführen**

```bash
docker compose exec web python manage.py migrate ipam
```

Erwartet: `Applying ipam.0005_multi_app_subnets... OK`.

- [ ] **Step 4: Manuelle DB-Verifikation**

```bash
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME" -c "\d ipam_assignment"
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME" -c "\d ipam_ipassignment"
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME" -c "\d ipam_assignment_applications"
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT count(*) FROM ipam_assignment_applications;"
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT count(*) FROM ipam_ipassignment WHERE is_gateway = true;"
```

Erwartet:
- `ipam_assignment` hat keine `application`- und keine `gateway`-Spalte mehr.
- `ipam_ipassignment` existiert.
- `ipam_assignment_applications` hat genau so viele Zeilen wie es vorher Assignments gab.
- `ipam_ipassignment WHERE is_gateway = true` hat so viele Zeilen wie es vorher Assignments mit gesetztem Gateway gab.

- [ ] **Step 5: `test_ip_assignment_basic_create` jetzt grün**

```bash
docker compose exec web pytest ipam/tests/test_models.py::test_ip_assignment_basic_create -v
```

Erwartet: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/models.py web/ipam/migrations/0005_multi_app_subnets.py web/ipam/tests/test_models.py
git commit -m "feat(ipam): IPAssignment model + M2M Subnet↔Application

Modell und Migration 0005 in einem Schritt — Migration enthält
RunPython-Datenüberführung des bisherigen FK + Gateway in die
neue M2M-Beziehung bzw. IPAssignment-Zeile mit is_gateway=True.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Bestehende Tests an M2M anpassen

Die bestehenden Tests setzen `assignment.application=<obj>` und `gateway=...`. Nach der Migration laufen sie nicht mehr.

**Files:**
- Modify: `web/ipam/tests/test_models.py`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Vor-Check — sehen wie viele Tests jetzt brechen**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -40
```

Erwartet: viele FAILs, alle mit Bezug zu `application=` oder `gateway=`.

- [ ] **Step 2: `test_models.py` anpassen**

Im File `web/ipam/tests/test_models.py`:

**`test_assignment_basic_create`** ersetzen durch:

```python
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
```

**`test_assignment_orders_by_cidr`** ersetzen:

```python
@pytest.mark.django_db
def test_assignment_orders_by_cidr(pool_v4):
    a_obj = Application.objects.create(name="X")
    a1 = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.16/28")
    a1.applications.add(a_obj)
    a2 = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/28")
    a2.applications.add(a_obj)
    cidrs = [str(a.cidr) for a in pool_v4.assignments.all()]
    assert cidrs == ["217.61.249.0/28", "217.61.249.16/28"]
```

**`test_assignment_must_be_inside_pool`** ersetzen:

```python
@pytest.mark.django_db
def test_assignment_must_be_inside_pool(pool_v4):
    a = Assignment(pool=pool_v4, cidr="10.0.0.0/24")
    with pytest.raises(ValidationError) as exc:
        a.full_clean()
    assert "innerhalb" in str(exc.value).lower() or "inside" in str(exc.value).lower()
```

**`test_assignment_ip_family_must_match_pool`** ersetzen:

```python
@pytest.mark.django_db
def test_assignment_ip_family_must_match_pool(pool_v4):
    a = Assignment(pool=pool_v4, cidr="2a05:ed80:100:1::/64")
    with pytest.raises(ValidationError):
        a.full_clean()
```

**`test_assignments_in_same_pool_cannot_overlap`** ersetzen:

```python
@pytest.mark.django_db
def test_assignments_in_same_pool_cannot_overlap(pool_v4):
    Application.objects.create(name="A")
    Application.objects.create(name="B")
    Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/28")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(pool=pool_v4, cidr="217.61.249.8/29")
```

**`test_assignments_in_different_pools_can_overlap_logically`** ersetzen:

```python
@pytest.mark.django_db
def test_assignments_in_different_pools_can_overlap_logically(pool_v4, pool_v6):
    Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/28")
    Assignment.objects.create(pool=pool_v6, cidr="2a05:ed80:100:1::/64")
```

- [ ] **Step 3: `test_views.py` anpassen**

In allen Tests die `application=<id>` oder `gateway=...` im POST-Body verwenden, ersetzen durch `applications=<id>` (Django MultipleChoiceField akzeptiert eine Liste von IDs oder eine einzelne ID — beim direkten POST über `client.post` als Mehrfachwert).

Konkret:

**`test_sidebar_groups_assignments_by_pool_then_application`** ersetzen:

```python
@pytest.mark.django_db
def test_sidebar_groups_assignments_by_pool_then_application(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.248.0/23")
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
    assert body.count("217.61.248.0/23") == 2
    assert body.count(">BINSS<") == 1
    assert body.count(">Falcon<") == 1
    assert "217.61.249.0/28" in body
    assert "217.61.249.16/28" in body
    assert "217.61.249.32/29" in body
```

**`test_index_shows_pool_card_with_utilization`** ersetzen:

```python
@pytest.mark.django_db
def test_index_shows_pool_card_with_utilization(auth_client):
    p = Pool.objects.create(name="Anycast", cidr="217.61.248.0/23")
    a = Application.objects.create(name="X")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/28")
    s.applications.add(a)
    response = auth_client.get("/")
    body = response.content.decode()
    assert "Anycast" in body
    assert "217.61.248.0/23" in body
    assert "3" in body
```

**`test_ipv4_pool_detail_shows_grid_with_blocks`** ersetzen:

```python
@pytest.mark.django_db
def test_ipv4_pool_detail_shows_grid_with_blocks(auth_client):
    p = Pool.objects.create(name="TestPool", cidr="10.0.0.0/28")
    a = Application.objects.create(name="Acme")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/30")
    s.applications.add(a)
    response = auth_client.get(f"/pool/{p.id}/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "TestPool" in body
    assert "Acme" in body
    assert "10.0.0.0/30" in body
    assert "flex flex-wrap" in body or "flex-wrap" in body
    assert "frei" in body.lower()
```

**`test_ipv6_pool_detail_lists_assignments`** ersetzen:

```python
@pytest.mark.django_db
def test_ipv6_pool_detail_lists_assignments(auth_client):
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
    assert "v6Pool" in body
    assert "2001:db8::/32" in body
    assert "AlphaNet" in body
    assert "BetaCorp" in body
    assert "2001:db8:1::/48" in body
    assert "2001:db8:2::/48" in body
    assert "IPv6-Ansicht folgt" not in body
    assert "<table" in body
```

**`test_assignment_new_rejects_overlap`** ersetzen (gateway-Feld entfällt im POST, application→applications):

```python
@pytest.mark.django_db
def test_assignment_new_rejects_overlap(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
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
    assert response.status_code == 200
    assert "Überschnei" in body
```

**`test_assignment_new_happy_path_redirects`** ersetzen:

```python
@pytest.mark.django_db
def test_assignment_new_happy_path_redirects(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
    a = Application.objects.create(name="A")

    response = auth_client.post(f"/pool/{p.id}/assign/new/", {
        "applications": [a.id],
        "cidr": "217.61.249.0/30",
        "notes": "Router",
    })
    assert response.status_code == 302
    assert Assignment.objects.filter(pool=p, cidr="217.61.249.0/30").exists()
```

**`test_assignment_edit_loads_and_saves`** ersetzen:

```python
@pytest.mark.django_db
def test_assignment_edit_loads_and_saves(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
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
```

**`test_application_list_shows_count`** ersetzen:

```python
@pytest.mark.django_db
def test_application_list_shows_count(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
    a = Application.objects.create(name="BINSS")
    s1 = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s1.applications.add(a)
    s2 = Assignment.objects.create(pool=p, cidr="217.61.249.4/30")
    s2.applications.add(a)
    response = auth_client.get("/anwendungen/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "2" in body
```

**`test_application_detail_lists_assignments`** ersetzen:

```python
@pytest.mark.django_db
def test_application_detail_lists_assignments(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
    a = Application.objects.create(name="BINSS")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)
    response = auth_client.get(f"/anwendung/{a.id}/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "217.61.249.0/30" in body
```

- [ ] **Step 4: `application_list`-View Count anpassen**

In `web/ipam/views.py`, Funktion `application_list`: der aktuelle Count zählt die M2M-related-name korrekt — `annotate(n_assignments=Count("assignments"))` funktioniert auch für M2M. **Keine Änderung nötig**, dieser Schritt ist Verifikation per Test-Run.

- [ ] **Step 5: Run all tests, sehen welche jetzt grün sind**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -50
```

Erwartet: Verbleibende FAILs nur noch in `forms.py`-bezogenen Tests (`AssignmentForm` hat noch Feld `application` / `gateway`), Wiki-Import-Tests, und Tests die auf `application_id`-Verhalten im Sidebar / Pool-Detail / Context-Processor zielen. Diese werden in den folgenden Tasks behoben.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/tests/test_models.py web/ipam/tests/test_views.py
git commit -m "test(ipam): adapt model+view tests to M2M applications"
```

---

## Task 5: `AssignmentForm` an M2M anpassen

**Files:**
- Modify: `web/ipam/forms.py`
- Test: `web/ipam/tests/test_views.py` (neuer Test)

- [ ] **Step 1: Failing Test — Removal of app with IP assignments is blocked**

In `web/ipam/tests/test_views.py` ergänzen:

```python
@pytest.mark.django_db
def test_assignment_form_rejects_removal_of_app_with_ip_assignments(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28")
    a1 = Application.objects.create(name="A1")
    a2 = Application.objects.create(name="A2")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a1, a2)
    IPAssignment.objects.create(assignment=s, address="217.61.249.1", application=a1)

    # Versuche A1 (Anwendung mit IP) aus der M2M-Liste zu entfernen
    response = auth_client.post(f"/assignment/{s.id}/edit/", {
        "applications": [a2.id],   # A1 ausgelassen
        "cidr": "217.61.249.0/30",
        "notes": "",
    })
    assert response.status_code == 200  # form re-rendered
    body = response.content.decode()
    assert "A1" in body
    assert "IP-Zuordnungen" in body or "IP-Zuordnung" in body  # Fehlermeldung
    # M2M-Liste unverändert
    s.refresh_from_db()
    assert set(s.applications.values_list("name", flat=True)) == {"A1", "A2"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_assignment_form_rejects_removal_of_app_with_ip_assignments -v
```

Erwartet: FAIL — vermutlich entweder weil `applications` als Feld nicht akzeptiert wird (Form hat noch `application`), oder weil die Validierung noch fehlt.

- [ ] **Step 3: `AssignmentForm` ersetzen**

Ersetze in `web/ipam/forms.py` die `AssignmentForm`-Klasse durch:

```python
class AssignmentForm(forms.ModelForm):
    """ModelForm for Assignment, excluding `pool` (injected from URL)."""

    class Meta:
        model = Assignment
        fields = ["applications", "cidr", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "applications": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, pool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = pool
        for name, field in self.fields.items():
            if name == "applications":
                # CheckboxSelectMultiple uses its own markup; no tw class wrapper.
                continue
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400",
            )

    def clean(self):
        cleaned = super().clean()
        cidr_val = cleaned.get("cidr")
        if cidr_val is None or self.pool is None:
            return cleaned

        instance = self.instance or Assignment()
        instance.pool = self.pool
        instance.cidr = cidr_val
        try:
            instance.clean()
        except ValidationError as exc:
            self.add_error(None, exc)
            return cleaned

        new_net = IPNetwork(str(cidr_val))
        qs = Assignment.objects.filter(pool=self.pool)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        for other in qs:
            other_net = IPNetwork(str(other.cidr))
            if new_net in other_net or other_net in new_net:
                names = ", ".join(sorted(a.name for a in other.applications.all())) or "—"
                raise ValidationError(
                    {"cidr": f"Überschneidung mit {other.cidr} ({names})."}
                )
        return cleaned

    def clean_applications(self):
        apps = self.cleaned_data["applications"]
        if self.instance.pk:
            used = set(
                self.instance.ip_assignments.values_list("application_id", flat=True)
            )
            missing = used - {a.id for a in apps}
            if missing:
                names = list(
                    Application.objects.filter(pk__in=missing).values_list("name", flat=True)
                )
                raise ValidationError(
                    "Diese Anwendungen haben noch IP-Zuordnungen und können nicht "
                    f"entfernt werden: {', '.join(names)}. Erst die IPs löschen."
                )
        return apps
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_assignment_form_rejects_removal_of_app_with_ip_assignments -v
```

Erwartet: PASS.

- [ ] **Step 5: Alle Tests laufen**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -30
```

Erwartet: Form-Tests grün; verbleibende FAILs nur noch in import_wiki, context_processors, pool_detail (Farbe).

- [ ] **Step 6: Commit**

```bash
git add web/ipam/forms.py web/ipam/tests/test_views.py
git commit -m "feat(ipam): AssignmentForm uses applications M2M + blocks unsafe removal"
```

---

## Task 6: `context_processors.sidebar_tree` auf M2M umstellen

**Files:**
- Modify: `web/ipam/context_processors.py`

- [ ] **Step 1: Tests laufen → identifiziert fail**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_sidebar_groups_assignments_by_pool_then_application -v
```

Erwartet: FAIL — der context_processor greift auf `a.application.name` zu, das gibt es nicht mehr.

- [ ] **Step 2: Implementiere M2M-fähige sidebar_tree**

Ersetze `web/ipam/context_processors.py` durch:

```python
from collections import OrderedDict

from .models import Application, Assignment, Pool


def sidebar_tree(request):
    """Two flat lists for the left sidebar:
    - sidebar_pools: flat list of pools.
    - sidebar_apps:  each application with its assignments (expandable). With
                     M2M, one assignment may appear under multiple applications.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"sidebar_pools": [], "sidebar_apps": []}

    pools = [
        {"id": p.id, "name": p.name, "cidr": str(p.cidr), "ip_version": p.ip_version}
        for p in Pool.objects.order_by("cidr")
    ]

    assignments = (
        Assignment.objects
        .select_related("pool")
        .prefetch_related("applications")
        .order_by("cidr")
    )

    by_app = OrderedDict()
    for a in assignments:
        for app in a.applications.all():
            node = by_app.setdefault(app.id, {
                "id": app.id,
                "name": app.name,
                "assignments": [],
            })
            node["assignments"].append({
                "cidr": str(a.cidr),
                "pool_id": a.pool_id,
            })

    # Apps without assignments come at the end, sorted alphabetically among themselves.
    apps_with_assignments = set(by_app.keys())
    for app in Application.objects.exclude(id__in=apps_with_assignments).order_by("name"):
        by_app[app.id] = {"id": app.id, "name": app.name, "assignments": []}

    # Sort the main list by application name (case-insensitive) for stable UI.
    sorted_nodes = sorted(by_app.values(), key=lambda n: n["name"].casefold())
    return {"sidebar_pools": pools, "sidebar_apps": sorted_nodes}
```

- [ ] **Step 3: Run test to verify it passes**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_sidebar_groups_assignments_by_pool_then_application -v
```

Erwartet: PASS.

- [ ] **Step 4: Commit**

```bash
git add web/ipam/context_processors.py
git commit -m "feat(ipam): sidebar iterates assignments via M2M applications"
```

---

## Task 7: Pool-Detail-Farbe via erste Anwendung alphabetisch

**Files:**
- Modify: `web/ipam/views.py`
- Modify: `web/ipam/templates/pool_detail.html`
- Test: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Failing Test — Block-Farbe und Tooltip**

In `web/ipam/tests/test_views.py` ergänzen:

```python
@pytest.mark.django_db
def test_pool_color_uses_first_app_alphabetically(auth_client):
    p = Pool.objects.create(name="P", cidr="10.0.0.0/28")
    z = Application.objects.create(name="Zulu")
    a = Application.objects.create(name="Alpha")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/30")
    s.applications.add(z, a)

    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()
    # Beide Apps sichtbar (Tooltip / kommagetrennt)
    assert "Alpha" in body and "Zulu" in body
```

- [ ] **Step 2: Run test → noch grün oder rot je nach view-state**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_pool_color_uses_first_app_alphabetically -v
```

Erwartet: FAIL — `pool_detail`-View greift noch auf `a.application.name` zu.

- [ ] **Step 3: `pool_detail`-View umbauen**

Ersetze in `web/ipam/views.py` die Funktion `pool_detail`:

```python
def _first_app_name(assignment):
    apps = sorted((a.name for a in assignment.applications.all()), key=str.casefold)
    return apps[0] if apps else "—"


def _all_app_names(assignment):
    return ", ".join(sorted((a.name for a in assignment.applications.all()), key=str.casefold)) or "—"


@login_required
def pool_detail(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)

    if pool.ip_version == 4:
        pool_net = IPNetwork(str(pool.cidr))
        db_assignments = list(
            pool.assignments.prefetch_related("applications").all()
        )
        assignments = [
            {"cidr": IPNetwork(str(a.cidr)), "label": _first_app_name(a)}
            for a in db_assignments
        ]
        blocks = compute_blocks(pool_net, assignments)

        color_map = colors_for_set(_first_app_name(a) for a in db_assignments)

        for b in blocks:
            if b["kind"] == "assigned":
                src = next(a for a in db_assignments if IPNetwork(str(a.cidr)) == b["cidr"])
                first_name = _first_app_name(src)
                b["color"] = color_map.get(first_name, "#E5E7EB")
                b["app_names"] = _all_app_names(src)
                b["obj"] = src
            b["width_rem"] = f"{b['size'] * 0.3:.2f}"

        context = {"pool": pool, "blocks": blocks}
    else:
        db_assignments = list(
            pool.assignments.prefetch_related("applications").order_by("cidr")
        )
        rows = []
        for a in db_assignments:
            rows.append({
                "id": a.id,
                "cidr": a.cidr,
                "app_names": _all_app_names(a),
            })
        context = {"pool": pool, "blocks": None, "v6_rows": rows}

    return render(request, "pool_detail.html", context)
```

- [ ] **Step 4: `pool_detail.html` Template anpassen**

In `web/ipam/templates/pool_detail.html` den IPv4-Block-Eintrag ersetzen (Zeilen 26–34, das `<div>...<a>...<span class="font-semibold">...`-Konstrukt):

```html
                <div class="group relative rounded p-2 text-xs cursor-pointer hover:opacity-80 transition-opacity"
                     style="width: {{ b.width_rem }}rem; min-width: max-content; max-width: 100%; flex: 0 0 auto; background-color: {{ b.color }};"
                     title="{{ b.app_names }}">
                    <a href="{% url 'ipam:assignment_edit' b.obj.id %}"
                       class="block no-underline text-slate-900">
                        <span class="font-semibold block">{{ b.app_names }}</span>
                        <span class="font-mono block">{{ b.cidr }}</span>
                    </a>
                    {% cidr_tooltip_panel b.cidr %}
                </div>
```

Und in der IPv6-Tabelle (Zeilen 59–67) ersetzen:

```html
            {% for row in v6_rows %}
            <tr class="border-t border-slate-200 hover:bg-slate-50">
                <td class="px-3 py-2 font-mono">{% cidr_tooltip row.cidr %}</td>
                <td class="px-3 py-2">{{ row.app_names }}</td>
                <td class="px-3 py-2">
                    <a href="{% url 'ipam:assignment_edit' row.id %}"
                       class="text-blue-600 hover:underline text-xs">Bearbeiten</a>
                </td>
            </tr>
```

- [ ] **Step 5: Run test to verify it passes**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_pool_color_uses_first_app_alphabetically -v
docker compose exec web pytest ipam/tests/test_views.py::test_ipv4_pool_detail_shows_grid_with_blocks -v
docker compose exec web pytest ipam/tests/test_views.py::test_ipv6_pool_detail_lists_assignments -v
```

Erwartet: alle PASS.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/views.py web/ipam/templates/pool_detail.html web/ipam/tests/test_views.py
git commit -m "feat(ipam): pool detail uses first-app-alphabetically color + multi-app labels"
```

---

## Task 8: Wiki-Import auf M2M umstellen

**Files:**
- Modify: `web/ipam/management/commands/import_wiki.py`
- Modify: `web/ipam/tests/test_import_command.py`

- [ ] **Step 1: Bestehenden Wiki-Import-Test ansehen**

```bash
docker compose exec web pytest ipam/tests/test_import_command.py -v
```

Erwartet: FAIL — die Tests greifen auf `assignment.application` zu.

- [ ] **Step 2: `import_wiki.py` anpassen**

In `web/ipam/management/commands/import_wiki.py`, der Block ab Zeile 67 (`if Assignment.objects.filter(... ).exists():`) und der Block ab Zeile 71 (`a = Assignment(...)`) durch folgendes ersetzen:

```python
            if Assignment.objects.filter(pool=pool, cidr=str(ipnet.cidr)).exists():
                # Bereits vorhanden — sicherstellen, dass die importierte App in der M2M-Liste ist
                existing = Assignment.objects.get(pool=pool, cidr=str(ipnet.cidr))
                if not existing.applications.filter(pk=application.pk).exists():
                    existing.applications.add(application)
                assignments_existing += 1
                continue

            a = Assignment(pool=pool, cidr=str(ipnet.cidr), notes=notes)
            try:
                a.full_clean()
                with transaction.atomic():
                    a.save()
                    a.applications.add(application)
                assignments_new += 1
            except (ValidationError, IntegrityError) as e:
                logger.warning(f"SKIP {cidr_str} ({app_name}): {e}")
                skipped += 1
```

(Beachte: `applications.add(application)` muss nach `a.save()` kommen, da M2M eine PK auf der linken Seite braucht.)

- [ ] **Step 3: Test ergänzen — Idempotenz mit existierendem Subnet, neue App**

Die bestehenden Tests in `test_import_command.py` (count-basiert) bleiben unverändert. Ergänze am Ende einen neuen Test:

```python
@pytest.mark.django_db
def test_import_adds_new_app_to_existing_assignment(tmp_path):
    from ipam.models import IPAssignment
    Pool.objects.create(name="P", cidr="217.61.248.0/23")
    # Existierendes Subnet mit App "Bestand"
    bestand = Application.objects.create(name="Bestand")
    s = Assignment.objects.create(pool=Pool.objects.first(), cidr="217.61.249.0/28")
    s.applications.add(bestand)

    # Wiki-Dump fügt diesselbe CIDR mit anderer App "Neu" zu
    txt = tmp_path / "wiki.txt"
    txt.write_text("==== Neu ====\n217.61.249.0/28\n")
    call_command("import_wiki", str(txt))

    s.refresh_from_db()
    names = set(s.applications.values_list("name", flat=True))
    assert "Bestand" in names
    assert "Neu" in names
```

- [ ] **Step 4: Run test**

```bash
docker compose exec web pytest ipam/tests/test_import_command.py -v
```

Erwartet: alle PASS (bestehende 3 + 1 neuer).

- [ ] **Step 5: Commit**

```bash
git add web/ipam/management/commands/import_wiki.py web/ipam/tests/test_import_command.py
git commit -m "feat(ipam): wiki import adds applications via M2M, merges on existing CIDR"
```

---

## Task 9: Constraint- und Validation-Tests für `IPAssignment`

**Files:**
- Test: `web/ipam/tests/test_models.py`

- [ ] **Step 1: Failing Tests schreiben**

In `web/ipam/tests/test_models.py` am Ende ergänzen:

```python
@pytest.mark.django_db
def test_ip_assignment_address_must_be_in_cidr(pool_v4):
    from ipam.models import IPAssignment
    app = Application.objects.create(name="X")
    asgn = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/30")
    asgn.applications.add(app)
    ip = IPAssignment(assignment=asgn, address="10.0.0.1", application=app)
    with pytest.raises(ValidationError):
        ip.full_clean()


@pytest.mark.django_db
def test_ip_assignment_application_must_be_in_subnet_apps(pool_v4):
    from ipam.models import IPAssignment
    a1 = Application.objects.create(name="A1")
    a2 = Application.objects.create(name="A2")
    asgn = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/30")
    asgn.applications.add(a1)  # nur a1!
    ip = IPAssignment(assignment=asgn, address="217.61.249.1", application=a2)
    with pytest.raises(ValidationError) as exc:
        ip.full_clean()
    assert "Subnetz-Liste" in str(exc.value)


@pytest.mark.django_db
def test_ip_assignment_unique_per_assignment(pool_v4):
    from ipam.models import IPAssignment
    app = Application.objects.create(name="X")
    asgn = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/30")
    asgn.applications.add(app)
    IPAssignment.objects.create(assignment=asgn, address="217.61.249.1", application=app)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IPAssignment.objects.create(
                assignment=asgn, address="217.61.249.1", application=app,
            )


@pytest.mark.django_db
def test_only_one_gateway_per_assignment(pool_v4):
    from ipam.models import IPAssignment
    app = Application.objects.create(name="X")
    asgn = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/30")
    asgn.applications.add(app)
    IPAssignment.objects.create(
        assignment=asgn, address="217.61.249.1", application=app, is_gateway=True,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IPAssignment.objects.create(
                assignment=asgn, address="217.61.249.2", application=app, is_gateway=True,
            )


@pytest.mark.django_db
def test_deleting_assignment_cascades_to_ip_assignments(pool_v4):
    from ipam.models import IPAssignment
    app = Application.objects.create(name="X")
    asgn = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/30")
    asgn.applications.add(app)
    IPAssignment.objects.create(assignment=asgn, address="217.61.249.1", application=app)
    assert IPAssignment.objects.count() == 1
    asgn.delete()
    assert IPAssignment.objects.count() == 0


@pytest.mark.django_db
def test_application_delete_protected_when_ip_assigned(pool_v4):
    from django.db.models import ProtectedError
    from ipam.models import IPAssignment
    app = Application.objects.create(name="X")
    asgn = Assignment.objects.create(pool=pool_v4, cidr="217.61.249.0/30")
    asgn.applications.add(app)
    IPAssignment.objects.create(assignment=asgn, address="217.61.249.1", application=app)
    with pytest.raises(ProtectedError):
        app.delete()
```

- [ ] **Step 2: Run tests**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v -k "ip_assignment or gateway_per or cascades or protected" 2>&1 | tail -20
```

Erwartet: alle 6 PASS.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/tests/test_models.py
git commit -m "test(ipam): IPAssignment validation + constraint tests"
```

---

## Task 10: `services/ip_list.py` — `build_ip_rows` Helper

**Files:**
- Create: `web/ipam/services/ip_list.py`
- Test: `web/ipam/tests/test_ip_list.py`

- [ ] **Step 1: Failing Test — full mode**

Erstelle `web/ipam/tests/test_ip_list.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_ip_list.py -v
```

Erwartet: `ModuleNotFoundError: No module named 'ipam.services.ip_list'`.

- [ ] **Step 3: Implementation**

Erstelle `web/ipam/services/ip_list.py`:

```python
from netaddr import IPNetwork


FULL_LIST_MAX = 32  # /27 IPv4, /123 IPv6


def build_ip_rows(assignment):
    """Returns list of dicts describing IP rows for the subnet edit page.

    Each row dict has:
        address (str), ip_assignment (IPAssignment | None),
        is_full_mode (bool).

    The form per row is built by the view (needs `IPAssignmentForm` import,
    which would cycle through forms.py if done here).
    """
    net = IPNetwork(str(assignment.cidr))
    size = net.size
    existing = {
        str(ip.address): ip for ip in assignment.ip_assignments.all()
    }
    if size <= FULL_LIST_MAX:
        return [
            {
                "address": str(ip),
                "ip_assignment": existing.get(str(ip)),
                "is_full_mode": True,
            }
            for ip in net
        ]
    return [
        {
            "address": addr,
            "ip_assignment": ip,
            "is_full_mode": False,
        }
        for addr, ip in sorted(existing.items(), key=lambda kv: _ip_sort_key(kv[0]))
    ]


def _ip_sort_key(addr_str):
    """Sort key that works for both v4 and v6 addresses."""
    import ipaddress
    return int(ipaddress.ip_address(addr_str))
```

- [ ] **Step 4: Run tests to verify pass**

```bash
docker compose exec web pytest ipam/tests/test_ip_list.py -v
```

Erwartet: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add web/ipam/services/ip_list.py web/ipam/tests/test_ip_list.py
git commit -m "feat(ipam): services/ip_list.build_ip_rows helper"
```

---

## Task 11: `IPAssignmentForm`

**Files:**
- Modify: `web/ipam/forms.py`

- [ ] **Step 1: Form ergänzen**

In `web/ipam/forms.py` am Dateiende ergänzen (Imports oben anpassen — `IPAssignment` hinzufügen):

```python
from .models import Application, Assignment, IPAssignment, Pool
```

und am Ende:

```python
class IPAssignmentForm(forms.ModelForm):
    class Meta:
        model = IPAssignment
        fields = ["address", "application", "is_gateway", "label", "notes"]
        widgets = {
            "notes": forms.TextInput(),
        }

    def __init__(self, *args, assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        if assignment is not None:
            self.fields["application"].queryset = assignment.applications.all()
        for name, field in self.fields.items():
            if name == "is_gateway":
                continue
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-slate-400",
            )

    def clean(self):
        cleaned = super().clean()
        if self.assignment is None:
            return cleaned
        instance = self.instance or IPAssignment()
        instance.assignment = self.assignment
        instance.address = cleaned.get("address")
        instance.application = cleaned.get("application")
        try:
            instance.clean()
        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                for field, errors in exc.error_dict.items():
                    self.add_error(None if field == "__all__" else field, errors)
            else:
                self.add_error(None, exc.messages)
        return cleaned
```

- [ ] **Step 2: Smoke-Import-Test**

```bash
docker compose exec web python -c "from ipam.forms import IPAssignmentForm; print('ok')"
```

Erwartet: `ok`.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/forms.py
git commit -m "feat(ipam): IPAssignmentForm with subnet-scoped application queryset"
```

---

## Task 12: `assignment_edit`-View erweitert + Template-Section IP-Liste

**Files:**
- Modify: `web/ipam/views.py`
- Modify: `web/ipam/templates/assignment_form.html`
- Test: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Failing Tests — IP-Liste rendert**

In `web/ipam/tests/test_views.py` ergänzen:

```python
@pytest.mark.django_db
def test_assignment_edit_renders_full_iplist_for_small_subnet(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)

    response = auth_client.get(f"/assignment/{s.id}/edit/")
    assert response.status_code == 200
    body = response.content.decode()
    # alle 4 Adressen werden gerendert
    assert "217.61.249.0" in body
    assert "217.61.249.1" in body
    assert "217.61.249.2" in body
    assert "217.61.249.3" in body
    # Sektion-Header vorhanden
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
    # nur die existierende IP, nicht alle 256
    assert "217.61.249.10" in body
    assert body.count("217.61.249.") < 30  # nicht alle 256 gerendert
    # "Hinzufügen"-Knopf erwartet
    assert "hinzufügen" in body.lower() or "anlegen" in body.lower()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v -k "renders_full_iplist or renders_sparse_iplist"
```

Erwartet: FAIL — Template kennt die Sektion noch nicht.

- [ ] **Step 3: URL-Stubs + View-Stubs für ip_assignment_save/delete einfügen**

Damit das Template `{% url 'ipam:ip_assignment_save' ... %}` und `..._delete ...` rendern kann, brauchen wir die URLs jetzt schon. Die echten Implementierungen folgen in Task 13/14.

In `web/ipam/urls.py` ergänzen:

```python
    path("subnet/<int:assignment_id>/ip/save/",
         views.ip_assignment_save, name="ip_assignment_save"),
    path("subnet/<int:assignment_id>/ip/<int:ip_id>/delete/",
         views.ip_assignment_delete, name="ip_assignment_delete"),
```

In `web/ipam/views.py` am Dateiende stub-Funktionen:

```python
@login_required
def ip_assignment_save(request, assignment_id):
    # vollständige Implementierung in Task 13
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)


@login_required
def ip_assignment_delete(request, assignment_id, ip_id):
    # vollständige Implementierung in Task 14
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)
```

- [ ] **Step 4: `assignment_edit`-View erweitern**

In `web/ipam/views.py`, Funktion `assignment_edit`, vor dem `return render(...)`:

```python
@login_required
def assignment_edit(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    pool = assignment.pool
    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment, pool=pool)
        if form.is_valid():
            form.save()
            return redirect("ipam:pool_detail", pool_id=pool.pk)
    else:
        form = AssignmentForm(instance=assignment, pool=pool)

    from .forms import IPAssignmentForm
    from .services.ip_list import build_ip_rows
    rows = build_ip_rows(assignment)
    for row in rows:
        row["form"] = IPAssignmentForm(
            instance=row["ip_assignment"],
            assignment=assignment,
            initial=None if row["ip_assignment"] else {"address": row["address"]},
        )

    return render(request, "assignment_form.html", {
        "form": form,
        "pool": pool,
        "assignment": assignment,
        "ip_rows": rows,
    })
```

- [ ] **Step 5: Template erweitern**

Ersetze `web/ipam/templates/assignment_form.html` vollständig durch:

```html
{% extends "base.html" %}
{% block title %}{% if assignment %}Subnetz bearbeiten{% else %}Neue Zuweisung{% endif %}{% endblock %}
{% block content %}
<div class="max-w-4xl mx-auto">
    <h1 class="text-2xl font-bold text-slate-800 mb-1">
        {% if assignment %}Subnetz bearbeiten{% else %}Neue Zuweisung{% endif %}
    </h1>

    {# Pool info (read-only) #}
    <div class="mb-6 bg-slate-100 border border-slate-300 rounded px-4 py-3 text-sm text-slate-700">
        <span class="font-semibold">Pool:</span>
        {{ pool.name }} &mdash; <code class="font-mono">{{ pool.cidr }}</code>
    </div>

    {# Non-field errors of the subnet form #}
    {% if form.non_field_errors %}
    <div class="mb-4 bg-red-50 border border-red-300 rounded px-4 py-3 text-sm text-red-700">
        {% for error in form.non_field_errors %}
            <p>{{ error }}</p>
        {% endfor %}
    </div>
    {% endif %}

    {# === Subnet metadata form === #}
    <form method="post" novalidate class="mb-8 bg-white border border-slate-200 rounded p-4">
        {% csrf_token %}
        {% for field in form %}
        <div class="mb-4">
            <label for="{{ field.id_for_label }}"
                   class="block text-sm font-medium text-slate-700 mb-1">
                {{ field.label }}{% if field.field.required %} <span class="text-red-500">*</span>{% endif %}
            </label>
            {{ field }}
            {% if field.errors %}
            <ul class="mt-1 text-xs text-red-600">
                {% for error in field.errors %}<li>{{ error }}</li>{% endfor %}
            </ul>
            {% endif %}
            {% if field.help_text %}
            <p class="mt-1 text-xs text-slate-500">{{ field.help_text }}</p>
            {% endif %}
        </div>
        {% endfor %}
        <div class="flex items-center gap-4 mt-2">
            <button type="submit"
                    class="bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium px-5 py-2 rounded">
                Subnetz speichern
            </button>
            <a href="{% url 'ipam:pool_detail' pool.pk %}"
               class="text-sm text-slate-500 hover:text-slate-700 underline">
                Zurück zum Pool
            </a>
        </div>
    </form>

    {# === IP assignment section === #}
    {% if assignment %}
    <h2 class="text-lg font-semibold text-slate-800 mb-2">IP-Zuordnungen</h2>

    {% if not assignment.applications.exists %}
    <div class="mb-4 bg-amber-50 border border-amber-300 rounded px-4 py-3 text-sm text-amber-800">
        Erst Anwendungen am Subnetz hinterlegen, dann können IPs zugeordnet werden.
    </div>
    {% else %}

    <div class="overflow-x-auto bg-white border border-slate-200 rounded">
        <table class="w-full text-xs">
            <thead class="bg-slate-100 text-slate-600">
                <tr>
                    <th class="px-2 py-2 text-left font-semibold">Adresse</th>
                    <th class="px-2 py-2 text-left font-semibold">Anwendung</th>
                    <th class="px-2 py-2 text-left font-semibold">Gateway</th>
                    <th class="px-2 py-2 text-left font-semibold">Label</th>
                    <th class="px-2 py-2 text-left font-semibold">Notes</th>
                    <th class="px-2 py-2 text-left font-semibold">Aktion</th>
                </tr>
            </thead>
            <tbody>
                {% for row in ip_rows %}
                <tr class="border-t border-slate-100 align-top">
                    <form method="post" action="{% url 'ipam:ip_assignment_save' assignment.id %}">
                        {% csrf_token %}
                        <td class="px-2 py-1 font-mono whitespace-nowrap">
                            {% if row.is_full_mode %}
                                <input type="hidden" name="address" value="{{ row.address }}">
                                {{ row.address }}
                            {% else %}
                                <input type="text" name="address" value="{{ row.form.address.value|default:'' }}"
                                       class="border border-slate-300 rounded px-2 py-1 text-xs w-40">
                            {% endif %}
                        </td>
                        <td class="px-2 py-1">{{ row.form.application }}</td>
                        <td class="px-2 py-1">{{ row.form.is_gateway }}</td>
                        <td class="px-2 py-1">{{ row.form.label }}</td>
                        <td class="px-2 py-1">{{ row.form.notes }}</td>
                        <td class="px-2 py-1 whitespace-nowrap">
                            <button type="submit"
                                    class="bg-slate-700 hover:bg-slate-600 text-white px-2 py-1 rounded">
                                Speichern
                            </button>
                            {% if row.ip_assignment %}
                            <a href="{% url 'ipam:ip_assignment_delete' assignment.id row.ip_assignment.id %}"
                               class="text-red-600 hover:underline ml-2">×</a>
                            {% endif %}
                        </td>
                    </form>
                </tr>
                {% if row.form.errors %}
                <tr class="bg-red-50">
                    <td colspan="6" class="px-2 py-2 text-red-700 text-xs">
                        {% for field, errors in row.form.errors.items %}
                            <strong>{{ field }}:</strong>
                            {% for e in errors %}{{ e }}{% endfor %}
                        {% endfor %}
                    </td>
                </tr>
                {% endif %}
                {% empty %}
                <tr>
                    <td colspan="6" class="px-2 py-4 text-center text-slate-400 italic">
                        Keine IPs zugeordnet.
                    </td>
                </tr>
                {% endfor %}

                {% if ip_rows and not ip_rows.0.is_full_mode %}
                <tr class="border-t-2 border-slate-300 bg-slate-50">
                    <form method="post" action="{% url 'ipam:ip_assignment_save' assignment.id %}">
                        {% csrf_token %}
                        <td class="px-2 py-1">
                            <input type="text" name="address" placeholder="z.B. 10.0.0.1"
                                   class="border border-slate-300 rounded px-2 py-1 text-xs w-40">
                        </td>
                        <td class="px-2 py-1">
                            <select name="application"
                                    class="border border-slate-300 rounded px-2 py-1 text-xs">
                                <option value="">---</option>
                                {% for app in assignment.applications.all %}
                                <option value="{{ app.id }}">{{ app.name }}</option>
                                {% endfor %}
                            </select>
                        </td>
                        <td class="px-2 py-1"><input type="checkbox" name="is_gateway"></td>
                        <td class="px-2 py-1"><input type="text" name="label"
                                                       class="border border-slate-300 rounded px-2 py-1 text-xs w-32"></td>
                        <td class="px-2 py-1"><input type="text" name="notes"
                                                       class="border border-slate-300 rounded px-2 py-1 text-xs"></td>
                        <td class="px-2 py-1">
                            <button type="submit"
                                    class="bg-blue-600 hover:bg-blue-700 text-white px-2 py-1 rounded">
                                + IP hinzufügen
                            </button>
                        </td>
                    </form>
                </tr>
                {% endif %}
            </tbody>
        </table>
    </div>
    {% endif %}
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 6: Run tests**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v -k "renders_full_iplist or renders_sparse_iplist"
```

Erwartet: beide PASS.

- [ ] **Step 7: `assignment_new`-View muss noch funktionieren**

Test:

```bash
docker compose exec web pytest ipam/tests/test_views.py -v -k "assignment_new_happy_path or assignment_new_rejects"
```

Erwartet: beide PASS — `assignment_new` rendert das Template ohne `assignment`-Variable, daher zeigt der `{% if assignment %}`-Block nichts.

- [ ] **Step 8: Commit**

```bash
git add web/ipam/views.py web/ipam/templates/assignment_form.html web/ipam/tests/test_views.py
git commit -m "feat(ipam): assignment edit page renders per-IP CRUD table"
```

---

## Task 13: `ip_assignment_save`-View + URL

**Files:**
- Modify: `web/ipam/views.py`
- Modify: `web/ipam/urls.py`
- Test: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Failing Tests**

In `web/ipam/tests/test_views.py` ergänzen:

```python
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
    s.applications.add(a1)  # a2 ist nicht in der Subnetz-Liste

    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "address": "217.61.249.1",
        "application": a2.id,
        "label": "",
        "notes": "",
    })
    # Form rejected → re-render with 200, body enthält Fehler
    assert response.status_code == 200
    body = response.content.decode()
    # Django ModelForm: application aus queryset gefiltert, Fehler "Wählen Sie eine gültige Auswahl"
    assert "gültige" in body.lower() or "valid" in body.lower()


@pytest.mark.django_db
def test_ip_assignment_save_renders_errors_inline_on_validation_failure(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)

    # Adresse außerhalb des CIDR
    response = auth_client.post(f"/subnet/{s.id}/ip/save/", {
        "address": "10.0.0.1",
        "application": a.id,
        "label": "",
        "notes": "",
    })
    assert response.status_code == 200
    body = response.content.decode()
    assert "Subnetz" in body  # Fehlermeldung enthält "Subnetz"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v -k "ip_assignment_save"
```

Erwartet: alle FAIL — URL nicht definiert.

- [ ] **Step 3: Stub-View durch echte Implementierung ersetzen**

In `web/ipam/views.py`, am Anfang `transaction` importieren falls noch nicht:

```python
from django.db import transaction
```

Ersetze die Stub-Funktion `ip_assignment_save` (aus Task 12) durch:

```python
@login_required
def ip_assignment_save(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method != "POST":
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)

    from .forms import IPAssignmentForm
    from .models import IPAssignment
    from .services.ip_list import build_ip_rows

    address = request.POST.get("address", "")
    instance = IPAssignment.objects.filter(
        assignment=assignment, address=address,
    ).first()
    form = IPAssignmentForm(request.POST, instance=instance, assignment=assignment)

    if form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.assignment = assignment
            if obj.is_gateway:
                IPAssignment.objects.filter(
                    assignment=assignment, is_gateway=True,
                ).exclude(pk=obj.pk or 0).update(is_gateway=False)
            obj.save()
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)

    # Fehlerpfad: Edit-Seite direkt rendern, fehlerhaftes Form in die Zeile einsetzen
    rows = build_ip_rows(assignment)
    replaced = False
    for row in rows:
        if row["address"] == address:
            row["form"] = form
            replaced = True
        else:
            row["form"] = IPAssignmentForm(
                instance=row["ip_assignment"],
                assignment=assignment,
                initial=None if row["ip_assignment"] else {"address": row["address"]},
            )
    if not replaced:
        rows.append({
            "address": address,
            "ip_assignment": None,
            "form": form,
            "is_full_mode": False,
        })

    subnet_form = AssignmentForm(instance=assignment, pool=assignment.pool)
    return render(request, "assignment_form.html", {
        "form": subnet_form,
        "pool": assignment.pool,
        "assignment": assignment,
        "ip_rows": rows,
    })
```

(URL wurde bereits in Task 12 angelegt — Stub durch Implementierung ersetzen, sonst nichts.)

- [ ] **Step 4: Tests laufen**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v -k "ip_assignment_save"
```

Erwartet: alle 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add web/ipam/views.py web/ipam/tests/test_views.py
git commit -m "feat(ipam): ip_assignment_save with gateway-uniqueness enforcement"
```

---

## Task 14: `ip_assignment_delete`-View + URL

**Files:**
- Modify: `web/ipam/views.py`
- Modify: `web/ipam/urls.py`
- Test: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Failing Test**

In `web/ipam/tests/test_views.py` ergänzen:

```python
@pytest.mark.django_db
def test_ip_assignment_delete_removes_row(auth_client):
    from ipam.models import IPAssignment
    p = Pool.objects.create(name="P", cidr="217.61.249.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="217.61.249.0/30")
    s.applications.add(a)
    ip = IPAssignment.objects.create(assignment=s, address="217.61.249.1", application=a)

    response = auth_client.get(f"/subnet/{s.id}/ip/{ip.id}/delete/")
    assert response.status_code == 302
    assert not IPAssignment.objects.filter(pk=ip.pk).exists()
```

- [ ] **Step 2: Run to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_ip_assignment_delete_removes_row -v
```

Erwartet: FAIL — URL nicht definiert.

- [ ] **Step 3: Stub-View durch echte Implementierung ersetzen**

In `web/ipam/views.py` Stub-Funktion `ip_assignment_delete` (aus Task 12) durch echte Logik ersetzen:

```python
@login_required
def ip_assignment_delete(request, assignment_id, ip_id):
    from .models import IPAssignment
    obj = get_object_or_404(IPAssignment, pk=ip_id, assignment_id=assignment_id)
    obj.delete()
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)
```

(URL wurde bereits in Task 12 angelegt.)

- [ ] **Step 4: Run test**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_ip_assignment_delete_removes_row -v
```

Erwartet: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/ipam/views.py web/ipam/tests/test_views.py
git commit -m "feat(ipam): ip_assignment_delete view"
```

---

## Task 15: Admin-UI an M2M + Inline anpassen

**Files:**
- Modify: `web/ipam/admin.py`

- [ ] **Step 1: Aktuellen Admin lesen → Felder anpassen**

Ersetze `web/ipam/admin.py` durch:

```python
from django.contrib import admin

from .models import Application, Assignment, IPAssignment, Pool


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "ip_version")
    search_fields = ("name", "cidr")
    readonly_fields = ("ip_version",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class IPAssignmentInline(admin.TabularInline):
    model = IPAssignment
    extra = 0
    autocomplete_fields = ("application",)
    fields = ("address", "application", "is_gateway", "label", "notes")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("cidr", "pool", "applications_list")
    list_filter = ("pool",)
    search_fields = ("cidr", "notes")
    autocomplete_fields = ("pool",)
    filter_horizontal = ("applications",)
    inlines = [IPAssignmentInline]

    @admin.display(description="Anwendungen")
    def applications_list(self, obj):
        return ", ".join(sorted(a.name for a in obj.applications.all()))


@admin.register(IPAssignment)
class IPAssignmentAdmin(admin.ModelAdmin):
    list_display = ("address", "assignment", "application", "is_gateway")
    list_filter = ("is_gateway",)
    search_fields = ("address", "label")
    autocomplete_fields = ("application", "assignment")
```

- [ ] **Step 2: Smoke-Test — Admin lädt**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -10
```

Erwartet: keine Regressionen.

Und manueller Smoke-Check über den Browser an `https://subnetly.kntinternet.de/admin/` (vom Operator):
- Pool, Application, Assignment, IPAssignment alle erreichbar.
- Assignment-Detail: M2M-Widget für Anwendungen + Inline-Tabelle der IPs.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/admin.py
git commit -m "feat(ipam): admin shows IPAssignment inline + M2M filter_horizontal"
```

---

## Task 16: Volltest-Run + Doku-Anpassung

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Komplette Test-Suite läuft**

```bash
docker compose exec web pytest ipam/tests/ -v
```

Erwartet: ALL PASS. Test-Anzahl ungefähr 63 (43 + ~20 neue).

- [ ] **Step 2: CLAUDE.md-Notiz ergänzen**

Öffne `CLAUDE.md` im Repo-Root. Ergänze unter den bestehenden Bullets:

```markdown
- Subnet ↔ Application ist M2M (Migration 0005). Jede IP im Subnet kann
  über `IPAssignment` einer Anwendung zugeordnet werden; `is_gateway` ist
  ein partieller Unique-Constraint (max. ein Gateway pro Subnet).
- Subnet-Edit-Seite zeigt vollständige IP-Liste bis 32 IPs (Cut-off in
  `services/ip_list.FULL_LIST_MAX`), darüber sparse.
```

- [ ] **Step 3: Visual Smoke-Test im Browser**

(Operator-Schritt)
1. Existierendes /30-Subnet aufrufen → Edit-Seite zeigt 4 IP-Zeilen, 2 davon ggf. zugeordnet.
2. Eine zweite Anwendung an das Subnet hängen → speichern → Block in Pool-Detail zeigt beide Anwendungen kommagetrennt, Farbe folgt der alphabetisch ersten.
3. Eine IP der zweiten Anwendung zuordnen → Speichern → Tabelle aktualisiert.
4. Gateway umsetzen → vorherige Gateway-Markierung verschwindet.
5. Versuch, die erste Anwendung aus dem Subnet zu entfernen, obwohl noch IPs zugeordnet → Fehlermeldung.
6. IP löschen über das `×` → Zeile weg.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note multi-app subnets + IP assignment cutoff in CLAUDE.md"
```

---

## Task 17: Rollback-Verifikation (optional, aber empfohlen)

**Files:** keine — Operator-Verifikation.

- [ ] **Step 1: Rollback testen (in Dev/Staging, nicht Prod)**

```bash
docker compose exec web python manage.py migrate ipam 0004
```

Erwartet: `Unapplying ipam.0005_multi_app_subnets... OK`. Die alten Spalten kommen zurück, der `reverse_data` populiert `application` und `gateway` aus M2M und IPAssignment.

- [ ] **Step 2: Forward erneut anwenden**

```bash
docker compose exec web python manage.py migrate ipam
```

Erwartet: `Applying ipam.0005_multi_app_subnets... OK`. Daten wieder konsistent.

- [ ] **Step 3: Volltest**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -5
```

Erwartet: ALL PASS.

(Kein Commit — dies ist eine Verifikation.)

---

## Done.

**Erwartete Endzustände:**
- 17 Tasks abgeschlossen.
- ~63 Tests grün.
- Migration 0005 angewendet, alle Bestandsdaten erhalten.
- UI: Subnet-Edit zeigt IP-Liste, Pool-Übersicht zeigt mehrere Anwendungen pro Block.
- Wiki-Import läuft idempotent mit M2M-Logik.
- Admin zeigt IP-Inline-Tabelle.

**Bei Problemen:** Migration zurückrollen mit `python manage.py migrate ipam 0004`. Backup aus Task 1 zur Hand halten.
