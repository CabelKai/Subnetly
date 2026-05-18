# Delete-Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UI delete endpoints for `Pool`, `Application` and `Assignment` with a native `<dialog>` confirmation modal that pre-shows the cascade/block consequence.

**Architecture:** Three small POST-only views (one per entity), one shared template partial (`_delete_dialog.html`), per-detail-view context augmentation that computes `delete_blockers` + `delete_cascade_message`. Defense-in-depth: views re-check blocker conditions before delete. No JS framework — native `<dialog>` element only.

**Tech Stack:** Django 5.2, Tailwind via CDN (current setup), pytest-django. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-17-delete-views-design.md`

---

## File Structure

**Modify:**
- `web/ipam/urls.py` — three new URL patterns
- `web/ipam/views.py` — three new delete views + context augmentation in `pool_detail`, `application_detail`, `assignment_edit`
- `web/ipam/templates/pool_detail.html` — delete button + `{% include "_delete_dialog.html" %}` in header
- `web/ipam/templates/application_detail.html` — same
- `web/ipam/templates/assignment_form.html` — same (only in `{% if assignment %}` block)
- `web/ipam/tests/test_views.py` — 12 new tests

**Create:**
- `web/ipam/templates/_delete_dialog.html` — shared modal partial

---

### Task 1: Add URLs for the three delete endpoints

**Files:**
- Modify: `web/ipam/urls.py`

- [ ] **Step 1: Edit urls.py**

In `web/ipam/urls.py`, add three new patterns inside `urlpatterns`, after the existing `pool_edit` / `application_edit` lines:

```python
    path("pool/<int:pool_id>/delete/", views.pool_delete, name="pool_delete"),
    path("anwendung/<int:application_id>/delete/", views.application_delete, name="application_delete"),
    path("assignment/<int:assignment_id>/delete/", views.assignment_delete, name="assignment_delete"),
```

Final `urlpatterns` will look like (only showing relevant context):

```python
    path("pool/new/", views.pool_new, name="pool_new"),
    path("pool/<int:pool_id>/edit/", views.pool_edit, name="pool_edit"),
    path("pool/<int:pool_id>/delete/", views.pool_delete, name="pool_delete"),
    # … existing IP routes …
    path("anwendung/<int:application_id>/edit/", views.application_edit, name="application_edit"),
    path("anwendung/<int:application_id>/delete/", views.application_delete, name="application_delete"),
    path("assignment/<int:assignment_id>/edit/", views.assignment_edit, name="assignment_edit"),
    path("assignment/<int:assignment_id>/delete/", views.assignment_delete, name="assignment_delete"),
```

- [ ] **Step 2: Verify Django reverse() resolves**

Run:
```bash
docker compose exec -T web python -c "from django.urls import reverse; print(reverse('ipam:pool_delete', args=[1])); print(reverse('ipam:application_delete', args=[1])); print(reverse('ipam:assignment_delete', args=[1]))"
```

Expected output:
```
/pool/1/delete/
/anwendung/1/delete/
/assignment/1/delete/
```

(Will fail right now because the view functions don't exist yet — that's caught in the next task.)

---

### Task 2: TDD — write failing tests for the three delete views

**Files:**
- Modify: `web/ipam/tests/test_views.py` (append at end)

- [ ] **Step 1: Add nine new tests to `test_views.py`**

Append to the end of `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run all new tests, verify they fail**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "_delete_" -v 2>&1 | tail -25
```

Expected: 9 tests collected, all FAIL (currently get NoReverseMatch or AttributeError because views don't exist).

---

### Task 3: Implement the three delete views

**Files:**
- Modify: `web/ipam/views.py` (add imports and three views at the end)

- [ ] **Step 1: Add `require_POST` import**

In `web/ipam/views.py`, find the existing import block at the top. Add this line near the other `django.*` imports:

```python
from django.views.decorators.http import require_POST
```

- [ ] **Step 2: Append the three delete views at the end of views.py**

Append to `web/ipam/views.py`:

```python
@login_required
@require_POST
def pool_delete(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    if pool.assignments.exists():
        # Pre-check should have hidden the button — defense in depth.
        return redirect("ipam:pool_detail", pool_id=pool.pk)
    pool.delete()
    return redirect("ipam:index")


@login_required
@require_POST
def application_delete(request, application_id):
    app = get_object_or_404(Application, pk=application_id)
    if app.ip_assignments.exists():
        return redirect("ipam:application_detail", application_id=app.pk)
    app.delete()
    return redirect("ipam:application_list")


@login_required
@require_POST
def assignment_delete(request, assignment_id):
    asgn = get_object_or_404(Assignment, pk=assignment_id)
    pool_id = asgn.pool_id
    asgn.delete()  # CASCADEs to IPAssignments; M2M to Application clears itself
    return redirect("ipam:pool_detail", pool_id=pool_id)
```

- [ ] **Step 3: Run the nine delete tests, verify they pass**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "_delete_" -v 2>&1 | tail -25
```

Expected: 9 passed.

- [ ] **Step 4: Run full suite to make sure nothing else broke**

Run:
```bash
docker compose exec -T web pytest 2>&1 | tail -5
```

Expected: all tests pass.

---

### Task 4: Create the shared `_delete_dialog.html` partial

**Files:**
- Create: `web/ipam/templates/_delete_dialog.html`

- [ ] **Step 1: Create the partial**

Create `web/ipam/templates/_delete_dialog.html` with this exact content:

```django
<dialog id="delete-dialog"
        class="rounded-lg p-0 backdrop:bg-black/40 max-w-md w-[90vw]">
  <form method="post" action="{{ delete_action }}" class="p-6">
    {% csrf_token %}
    <h2 class="text-lg font-semibold mb-2">{{ delete_title }}</h2>

    {% if delete_blockers %}
      <p class="text-sm text-slate-700 mb-3">
        Kann nicht gelöscht werden — folgende Einträge referenzieren das hier:
      </p>
      <ul class="text-xs font-mono text-slate-600 mb-4 max-h-40 overflow-y-auto
                 border border-slate-200 rounded p-2 bg-slate-50">
        {% for b in delete_blockers %}<li>{{ b }}</li>{% endfor %}
      </ul>
    {% else %}
      <p class="text-sm text-slate-700 mb-4">{{ delete_cascade_message }}</p>
    {% endif %}

    <div class="flex justify-end gap-2">
      <button type="button"
              onclick="this.closest('dialog').close()"
              class="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">
        Abbrechen
      </button>
      {% if not delete_blockers %}
      <button type="submit"
              class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded text-sm">
        Endgültig löschen
      </button>
      {% endif %}
    </div>
  </form>
</dialog>

<button type="button"
        onclick="document.getElementById('delete-dialog').showModal()"
        class="bg-red-50 border border-red-300 text-red-700 hover:bg-red-100
               px-3 py-2 rounded text-sm">
  Löschen
</button>
```

- [ ] **Step 2: Sanity-check it loads (no test yet — covered in Task 5-7 tests)**

Run:
```bash
docker compose exec -T web python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

---

### Task 5: Wire Pool detail — context + include + tests

**Files:**
- Modify: `web/ipam/views.py` (the `pool_detail` view)
- Modify: `web/ipam/templates/pool_detail.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: TDD — write the Pool-detail delete-dialog test**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run the new tests, verify they fail**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "pool_detail_shows_delete" -v 2>&1 | tail -15
```

Expected: 2 tests FAIL (the dialog markup is not in the response yet).

- [ ] **Step 3: Add delete context in `pool_detail` view**

In `web/ipam/views.py`, find the `pool_detail` view. Locate the line at the end:

```python
    return render(request, "pool_detail.html", context)
```

Just BEFORE that line, add:

```python
    # Delete-dialog data: Pool is PROTECTed by any Assignment.
    context["delete_title"] = "Pool löschen?"
    context["delete_action"] = f"/pool/{pool.pk}/delete/"
    context["delete_blockers"] = [
        f"{a.cidr} ({', '.join(sorted(app.name for app in a.applications.all())) or '—'})"
        for a in db_assignments
    ]
    context["delete_cascade_message"] = ""
```

Note: `db_assignments` is already in scope for both the IPv4 and IPv6 branches of `pool_detail` (both branches assign it from `pool.assignments...`).

- [ ] **Step 4: Wire the include in `pool_detail.html`**

In `web/ipam/templates/pool_detail.html`, find the header block:

```html
<div class="mb-4 flex items-center justify-between">
    <div>
        <h1 class="text-2xl font-bold">{{ pool.name }}</h1>
        <p class="text-slate-500 font-mono text-sm">{% cidr_tooltip pool.cidr %}</p>
    </div>
    <div class="flex gap-2">
        <a href="{% url 'ipam:pool_edit' pool.id %}"
           class="bg-slate-200 hover:bg-slate-300 text-slate-900 px-3 py-2 rounded text-sm">
            Bearbeiten
        </a>
        <a href="{% url 'ipam:assignment_new' pool.id %}"
           class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium">
            + Zuweisung
        </a>
    </div>
</div>
```

Add `{% include "_delete_dialog.html" %}` inside the buttons `<div class="flex gap-2">`, after the `+ Zuweisung` link:

```html
<div class="mb-4 flex items-center justify-between">
    <div>
        <h1 class="text-2xl font-bold">{{ pool.name }}</h1>
        <p class="text-slate-500 font-mono text-sm">{% cidr_tooltip pool.cidr %}</p>
    </div>
    <div class="flex gap-2">
        <a href="{% url 'ipam:pool_edit' pool.id %}"
           class="bg-slate-200 hover:bg-slate-300 text-slate-900 px-3 py-2 rounded text-sm">
            Bearbeiten
        </a>
        <a href="{% url 'ipam:assignment_new' pool.id %}"
           class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium">
            + Zuweisung
        </a>
        {% include "_delete_dialog.html" %}
    </div>
</div>
```

- [ ] **Step 5: Run the two new tests, verify they pass**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "pool_detail_shows_delete" -v 2>&1 | tail -15
```

Expected: 2 passed.

- [ ] **Step 6: Run full suite**

Run:
```bash
docker compose exec -T web pytest 2>&1 | tail -5
```

Expected: all tests pass.

---

### Task 6: Wire Application detail — context + include + tests

**Files:**
- Modify: `web/ipam/views.py` (the `application_detail` view)
- Modify: `web/ipam/templates/application_detail.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: TDD — write the application-detail tests**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run new tests, verify they fail**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "application_detail_shows" -v 2>&1 | tail -15
```

Expected: 2 FAIL.

- [ ] **Step 3: Add delete context in `application_detail` view**

In `web/ipam/views.py`, find `application_detail`. Replace the existing function body with:

```python
@login_required
def application_detail(request, application_id):
    application = get_object_or_404(Application, pk=application_id)
    assignments = application.assignments.select_related("pool").order_by("pool__cidr", "cidr")

    blocking_ips = application.ip_assignments.select_related("assignment").all()
    delete_blockers = [
        f"{ip.address} (Subnetz {ip.assignment.cidr})"
        for ip in blocking_ips
    ]
    m2m_count = application.assignments.count()
    if delete_blockers:
        delete_cascade_message = ""
    elif m2m_count:
        delete_cascade_message = f"Wird aus {m2m_count} Subnetz(en) entfernt."
    else:
        delete_cascade_message = "Keine Referenzen — wird komplett entfernt."

    return render(request, "application_detail.html", {
        "application": application,
        "assignments": assignments,
        "delete_title": "Anwendung löschen?",
        "delete_action": f"/anwendung/{application.pk}/delete/",
        "delete_blockers": delete_blockers,
        "delete_cascade_message": delete_cascade_message,
    })
```

- [ ] **Step 4: Wire the include in `application_detail.html`**

In `web/ipam/templates/application_detail.html`, replace the header block:

```html
<div class="flex items-center justify-between mb-1 gap-2">
    <h1 class="text-2xl font-semibold truncate">{{ application.name }}</h1>
    <a href="{% url 'ipam:application_edit' application.id %}"
       class="bg-slate-200 hover:bg-slate-300 text-slate-900 px-3 py-1 rounded text-sm whitespace-nowrap">
        Bearbeiten
    </a>
</div>
```

with:

```html
<div class="flex items-center justify-between mb-1 gap-2">
    <h1 class="text-2xl font-semibold truncate">{{ application.name }}</h1>
    <div class="flex gap-2">
        <a href="{% url 'ipam:application_edit' application.id %}"
           class="bg-slate-200 hover:bg-slate-300 text-slate-900 px-3 py-1 rounded text-sm whitespace-nowrap">
            Bearbeiten
        </a>
        {% include "_delete_dialog.html" %}
    </div>
</div>
```

- [ ] **Step 5: Run the two new tests, verify they pass**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "application_detail_shows" -v 2>&1 | tail -15
```

Expected: 2 passed.

- [ ] **Step 6: Run full suite**

Run:
```bash
docker compose exec -T web pytest 2>&1 | tail -5
```

Expected: all tests pass.

---

### Task 7: Wire Assignment edit — context + include + test

**Files:**
- Modify: `web/ipam/views.py` (the `assignment_edit` view)
- Modify: `web/ipam/templates/assignment_form.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: TDD — write the assignment-edit dialog test**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run the new test, verify it fails**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "assignment_edit_shows_cascade" -v 2>&1 | tail -15
```

Expected: 1 FAIL.

- [ ] **Step 3: Add delete context in `assignment_edit` view**

In `web/ipam/views.py`, find the `assignment_edit` view. The render call at the end currently looks like:

```python
    return render(request, "assignment_form.html", {
        "form": form,
        "pool": pool,
        "pool_first_ip": pool_first,
        "pool_last_ip": pool_last,
        "assignment": assignment,
        "ip_rows": rows,
        "is_sparse_mode": is_sparse_mode,
    })
```

Just before that `return`, add:

```python
    ip_count = assignment.ip_assignments.count()
    delete_cascade_message = (
        f"Wird mit {ip_count} IP-Zuordnung(en) gelöscht."
        if ip_count else "Wird gelöscht."
    )
```

Then extend the render context dict with three new keys:

```python
    return render(request, "assignment_form.html", {
        "form": form,
        "pool": pool,
        "pool_first_ip": pool_first,
        "pool_last_ip": pool_last,
        "assignment": assignment,
        "ip_rows": rows,
        "is_sparse_mode": is_sparse_mode,
        "delete_title": "Subnetz löschen?",
        "delete_action": f"/assignment/{assignment.pk}/delete/",
        "delete_blockers": [],
        "delete_cascade_message": delete_cascade_message,
    })
```

- [ ] **Step 4: Wire the include in `assignment_form.html`**

In `web/ipam/templates/assignment_form.html`, find this block (inside `{% if assignment %}` is implicit because that's how the template branches between new/edit; the dialog should only appear in edit mode):

```html
<div class="flex items-center gap-4 mt-2">
    <button type="submit" class="bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium px-5 py-2 rounded">
        Subnetz speichern
    </button>
    <a href="{% url 'ipam:pool_detail' pool.pk %}" class="text-sm text-slate-500 hover:text-slate-700 underline">
        Zurück zum Pool
    </a>
</div>
```

Replace it with:

```html
<div class="flex items-center gap-4 mt-2">
    <button type="submit" class="bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium px-5 py-2 rounded">
        Subnetz speichern
    </button>
    <a href="{% url 'ipam:pool_detail' pool.pk %}" class="text-sm text-slate-500 hover:text-slate-700 underline">
        Zurück zum Pool
    </a>
    {% if assignment %}<span class="ml-auto">{% include "_delete_dialog.html" %}</span>{% endif %}
</div>
```

The wrapping `</form>` tag right after this block must be preserved — the include lives BEFORE the form closes, but since the `_delete_dialog.html` itself contains its own `<form>` (with its own `action` POST), this would nest forms. To avoid that, the include must be placed OUTSIDE the surrounding subnet-form.

Looking at `assignment_form.html` layout: the structure is:

```html
<form method="post" novalidate class="mb-8 ...">  <!-- subnet form -->
    {% csrf_token %}
    {% for field in form %} ... {% endfor %}
    <div class="flex items-center gap-4 mt-2"> ... buttons ... </div>
</form>

{% if assignment %}
<h2 ...>IP-Zuordnungen</h2>
...
```

The include MUST go between `</form>` and `{% if assignment %}`. Concretely, change the block to:

```html
<div class="flex items-center gap-4 mt-2">
    <button type="submit" class="bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium px-5 py-2 rounded">
        Subnetz speichern
    </button>
    <a href="{% url 'ipam:pool_detail' pool.pk %}" class="text-sm text-slate-500 hover:text-slate-700 underline">
        Zurück zum Pool
    </a>
</div>
</form>

{% if assignment %}
<div class="mb-6 flex justify-end">
    {% include "_delete_dialog.html" %}
</div>
{% endif %}
```

(Move only the inclusion site — leave the rest of the IP-Zuordnungen block below unchanged. The next existing line in the template is `{% if assignment %}` followed by `<h2>IP-Zuordnungen</h2>`. Merge: keep ONE `{% if assignment %}` block that now contains the delete-button div AND the existing IP-Zuordnungen content. Concretely, replace the two lines `</form>` followed by `{% if assignment %}` and the next `<h2 class="text-lg font-semibold text-slate-800 mb-2">IP-Zuordnungen</h2>` with:

```html
</form>

{% if assignment %}
<div class="mb-6 flex justify-end">
    {% include "_delete_dialog.html" %}
</div>

<h2 class="text-lg font-semibold text-slate-800 mb-2">IP-Zuordnungen</h2>
```

(All the rest of the existing IP-Zuordnungen block — `{% if not assignment.applications.exists %}…{% endif %}{% endif %}` — stays unchanged.)

- [ ] **Step 5: Run the new test, verify it passes**

Run:
```bash
docker compose exec -T web pytest ipam/tests/test_views.py -k "assignment_edit_shows_cascade" -v 2>&1 | tail -15
```

Expected: 1 passed.

- [ ] **Step 6: Run full suite**

Run:
```bash
docker compose exec -T web pytest 2>&1 | tail -5
```

Expected: all tests pass (89 existing + 12 new = 101 total, all green).

---

### Task 8: Manual smoke test in the browser

**Files:** none

- [ ] **Step 1: Start the stack if not running**

Run:
```bash
docker compose up -d
```

- [ ] **Step 2: Smoke-test each delete flow**

In a browser at `http://<host>:8080`:

1. **Pool delete (empty pool):**
   - Create a new Pool with `10.99.0.0/24`, no assignments.
   - Go to pool-detail. Click `Löschen`. Modal opens.
   - Confirm. Land on `/` index. Pool is gone.

2. **Pool delete (blocked):**
   - Create Pool `10.99.0.0/24`, add Assignment `10.99.0.0/28` with App "X".
   - Open pool-detail. Click `Löschen`. Modal shows the assignment as blocker.
   - No `Endgültig löschen` button. Press Esc → closed.

3. **Application delete (cascade-message):**
   - App "X" exists, attached to 1 Subnetz via M2M, but no IPs.
   - Open application-detail. Click `Löschen`. Modal: "Wird aus 1 Subnetz(en) entfernt."
   - Confirm → land on `/anwendungen/`. App gone. The Subnetz still exists, just without that App.

4. **Application delete (blocked):**
   - App "Y" has an IPAssignment.
   - Open application-detail. Click `Löschen`. Blocker list shows the IP.
   - No submit button.

5. **Assignment delete (cascade):**
   - Subnetz with 2 IPs.
   - Open Subnetz-edit. Click `Löschen`. Modal: "Wird mit 2 IP-Zuordnung(en) gelöscht."
   - Confirm → land on pool-detail. Subnetz weg, IPs weg.

- [ ] **Step 3: Note any UI glitches**

Document any rendering issues (modal positioning, button colors, Tailwind classes that didn't render). No commit at this step — just verification.

---

### Task 9: Final commit

**Files:** all of the above

- [ ] **Step 1: Review diff**

Run:
```bash
git diff web/ipam/urls.py web/ipam/views.py web/ipam/templates/ web/ipam/tests/test_views.py
git status --short
```

Expected: changes to `urls.py`, `views.py`, three templates (`pool_detail.html`, `application_detail.html`, `assignment_form.html`), one new template (`_delete_dialog.html`), and `test_views.py`.

- [ ] **Step 2: Stage and commit**

Run:
```bash
git add web/ipam/urls.py web/ipam/views.py \
  web/ipam/templates/_delete_dialog.html \
  web/ipam/templates/pool_detail.html \
  web/ipam/templates/application_detail.html \
  web/ipam/templates/assignment_form.html \
  web/ipam/tests/test_views.py \
  docs/superpowers/specs/2026-05-17-delete-views-design.md \
  docs/superpowers/plans/2026-05-17-delete-views-plan.md

git commit -m "feat(ipam): delete views for Pool, Application, Assignment

Adds POST-only delete endpoints with native <dialog> confirmation modal.
Per-detail-view pre-check shows cascade message (Assignment → N IPs) or
blocker list (Pool blocked by Assignments, Application blocked by
IPAssignments). Defense-in-depth: views re-check blockers before delete."
```

NOTE: this commit assumes the user wants delete-views shipped on their own. If the user is batching this with prior uncommitted work (Wiki-Cleanup, Security-Quick-Wins, etc.), skip the commit step here and let them assemble their own combined commit.

---

## Self-Review

**Spec coverage:**

| Spec section | Tasks |
|---|---|
| URLs | Task 1 |
| Views (3 endpoints, `@require_POST`, redirects, blocker re-check) | Task 3 + tests in Task 2 |
| Pre-Check-Daten (Pool, Application, Assignment) | Tasks 5, 6, 7 |
| Modal-Markup (partial) | Task 4 |
| Detail-Seiten — Integration (3 templates) | Tasks 5, 6, 7 |
| Tests (12 tests) | Tasks 2 (9) + 5 (2) + 6 (2) + 7 (1) = 14 — slight overcount, intentional: I split Pool-detail into "with blockers" and "empty pool" for clearer coverage. |
| Risiken (CSRF, 405 vs 302, dialog browser support, focus trap, blocker overflow) | CSRF and 405 are tested; dialog support and focus trap are inherent to native `<dialog>`; blocker overflow handled in partial CSS (`max-h-40 overflow-y-auto`). |

All spec sections covered.

**Placeholder scan:** no TBD/TODO. Code blocks present in every code step. Commands have expected output.

**Type consistency:** Context-key names match across tasks (`delete_title`, `delete_action`, `delete_blockers`, `delete_cascade_message`). URL names match (`pool_delete`, `application_delete`, `assignment_delete`).

**Scope:** one feature, one entity-family, focused. Suitable for a single execution session.
