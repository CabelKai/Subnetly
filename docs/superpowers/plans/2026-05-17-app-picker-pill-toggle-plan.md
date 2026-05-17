# Anwendungs-Picker als Pill-Toggles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vertical checkbox list for the `applications` field on the subnet edit page with horizontal pill-shaped toggles. Selected pills use a dark Slate-900 background; unselected are light/neutral.

**Architecture:** New Django widget `PillCheckboxSelectMultiple` (subclass of `forms.CheckboxSelectMultiple`) with custom container/option templates. CSS-only toggle via Tailwind's `has-[:checked]:` modifier. Real checkbox inputs stay in the DOM (visually hidden via `sr-only`), so the existing JS in `assignment_form.html` that reads `input[name="applications"]:checked` keeps working unchanged.

**Tech Stack:** Django 5.x, Tailwind 3.4+ (CDN, already in `base.html:7`), pytest-django, Docker Compose for execution.

**Spec:** `docs/superpowers/specs/2026-05-17-app-picker-pill-toggle-design.md`

---

## File Structure

- **Create:** `web/ipam/widgets.py` — new module, holds `PillCheckboxSelectMultiple` (single responsibility: custom widget classes for the ipam app)
- **Create:** `web/ipam/templates/ipam/widgets/pill_checkbox_select.html` — container template
- **Create:** `web/ipam/templates/ipam/widgets/pill_checkbox_option.html` — single-pill template
- **Modify:** `web/ipam/forms.py:5-24` — import the new widget, swap it into `AssignmentForm.Meta.widgets`
- **Modify:** `web/ipam/tests/test_views.py` — add one smoke test that asserts the pill markup is present on the edit page

No changes to:
- `assignment_form.html` (renders `{{ field }}` already — the widget template takes over automatically)
- The JS block at `assignment_form.html:196-242` (still reads `input[type="checkbox"][name="applications"]:checked`)
- `AssignmentForm.clean_applications` (forms.py:65)
- URL routing, views, models, migrations

---

## How to Run Tests

The Django app runs in a Docker Compose service called `web` (see `docker-compose.yml`). Run pytest from the repo root:

```bash
docker compose exec web pytest -x
```

For a single test:

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_assignment_edit_renders_pill_picker -x -v
```

If the `web` container is not running:

```bash
docker compose up -d
```

---

## Task 1: Pill-Toggle Widget

**Files:**
- Create: `web/ipam/widgets.py`
- Create: `web/ipam/templates/ipam/widgets/pill_checkbox_select.html`
- Create: `web/ipam/templates/ipam/widgets/pill_checkbox_option.html`
- Modify: `web/ipam/forms.py`
- Test: `web/ipam/tests/test_views.py` (append one test)

### - [ ] Step 1: Write the failing integration test

Append to `web/ipam/tests/test_views.py`:

```python
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
```

### - [ ] Step 2: Run the test, confirm it fails

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_assignment_edit_renders_pill_picker -x -v
```

Expected: FAIL. The body will contain Django's default `<ul>` checkbox markup, so the assertion on `<ul id="id_applications"` will fail (or one of the pill-class assertions before it).

### - [ ] Step 3: Create the widget class

Create `web/ipam/widgets.py`:

```python
from django import forms


class PillCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """Renders M2M selection as Tailwind pill-toggles.

    Real checkbox inputs are kept in the DOM (visually hidden via sr-only)
    so existing JS that reads `input[name=...]:checked` continues to work.
    """

    template_name = "ipam/widgets/pill_checkbox_select.html"
    option_template_name = "ipam/widgets/pill_checkbox_option.html"
```

### - [ ] Step 4: Create the container template

Create `web/ipam/templates/ipam/widgets/pill_checkbox_select.html`:

```django
<div class="flex flex-wrap gap-2">
  {% for group, options, index in widget.optgroups %}
    {% for option in options %}
      {% include option.template_name with widget=option %}
    {% endfor %}
  {% endfor %}
</div>
```

### - [ ] Step 5: Create the option (single pill) template

Create `web/ipam/templates/ipam/widgets/pill_checkbox_option.html`:

```django
<label class="px-3 py-1.5 rounded-full border border-slate-300 bg-slate-50
              text-sm text-slate-600 cursor-pointer select-none transition
              hover:border-slate-400 hover:bg-slate-100
              focus-within:ring-2 focus-within:ring-slate-400
              has-[:checked]:bg-slate-900 has-[:checked]:text-white
              has-[:checked]:border-slate-900">
  <input type="{{ widget.type }}"
         name="{{ widget.name }}"
         {% if widget.value != None %}value="{{ widget.value|stringformat:'s' }}"{% endif %}
         class="sr-only"
         {% include "django/forms/widgets/attrs.html" %}>
  {{ widget.label }}
</label>
```

Note: `django/forms/widgets/attrs.html` is part of Django itself; it renders the remaining attributes including `checked` (set automatically by `CheckboxSelectMultiple` for selected options) and `id`. This is the same partial Django's stock checkbox option template uses.

### - [ ] Step 6: Wire the new widget into AssignmentForm

Edit `web/ipam/forms.py` — change lines 1-24 area:

Replace:
```python
from .models import Application, Assignment, IPAssignment, Pool
```
with:
```python
from .models import Application, Assignment, IPAssignment, Pool
from .widgets import PillCheckboxSelectMultiple
```

And replace:
```python
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "applications": forms.CheckboxSelectMultiple(),
        }
```
with:
```python
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "applications": PillCheckboxSelectMultiple(),
        }
```

### - [ ] Step 7: Run the new test, confirm it passes

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_assignment_edit_renders_pill_picker -x -v
```

Expected: PASS.

If it fails with a `TemplateDoesNotExist` error for `django/forms/widgets/attrs.html`, set in `web/subnetly/settings.py`:

```python
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"
```

and add `"django.forms"` to `INSTALLED_APPS`. Then re-run.

If the assertion on `'class="sr-only"' in body` fails because `attrs.html` overwrote the `class` attribute, the option template needs to put `class="sr-only"` into `widget.attrs` instead of as a literal attribute. Quick fix: replace `class="sr-only"` in the input tag with nothing, and override `build_attrs` in the widget:

```python
class PillCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = "ipam/widgets/pill_checkbox_select.html"
    option_template_name = "ipam/widgets/pill_checkbox_option.html"

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        option["attrs"]["class"] = "sr-only"
        return option
```

If applied: simplify the option template by removing `class="sr-only"` from the literal `<input>` markup, since `attrs.html` will emit it.

### - [ ] Step 8: Run the full test suite

```bash
docker compose exec web pytest -x
```

Expected: All tests pass. The existing test `test_assignment_edit_loads_and_saves` (test_views.py:157) is the most relevant safety net — it POSTs `applications: [a.id]` to the edit endpoint; this must still result in a 302 and persist the application link.

### - [ ] Step 9: Commit

```bash
git add web/ipam/widgets.py \
        web/ipam/templates/ipam/widgets/pill_checkbox_select.html \
        web/ipam/templates/ipam/widgets/pill_checkbox_option.html \
        web/ipam/forms.py \
        web/ipam/tests/test_views.py
git commit -m "feat(ui): pill-toggle picker for applications on subnet edit"
```

If `settings.py` was changed in Step 7's troubleshooting branch, also add `web/subnetly/settings.py` to the commit.

---

## Task 2: Manual Browser Verification

**No code changes. This is a visual sanity check.**

### - [ ] Step 1: Restart the web container so it picks up the new templates

```bash
docker compose restart web
```

(Django auto-reloads Python, but template-path discovery from a fresh app config is safest with a restart.)

### - [ ] Step 2: Navigate to an existing subnet edit page

Open `http://<host>/assignment/<id>/edit/` for any subnet that has at least 2 applications in the system. Find an ID via the sidebar or the pool detail page.

### - [ ] Step 3: Verify visual + interactive behavior

Confirm:
- Applications render as horizontal pills, not a vertical list.
- Unselected pills: light slate-50 background, slate-600 text, slate-300 border.
- Selected pills: dark slate-900 background, white text.
- Clicking a pill toggles its state (and you see the styling flip).
- Tab focus moves through pills, Space toggles, and a focus ring is visible.
- Below the pill row, the IP-rows' "Anwendung" dropdown contains exactly the currently-selected applications (the existing live-sync JS still works).

### - [ ] Step 4: Save the form and verify persistence

Toggle one application, click "Subnetz speichern", reload the edit page, confirm the selection persisted.

### - [ ] Step 5: Empty-state sanity check (optional)

Open the edit page for a subnet/pool combination where no `Application` objects exist in the system at all. The pill row should render empty (the existing amber "Erst Anwendungen am Subnetz hinterlegen" warning below is unrelated and still shows). No JS errors in the browser console.

---

## Done When

- New test `test_assignment_edit_renders_pill_picker` passes.
- All pre-existing tests still pass.
- A subnet edit page in a real browser shows pills, toggles them, and saves.
- One commit on `main` containing the widget code + templates + form change + new test.
