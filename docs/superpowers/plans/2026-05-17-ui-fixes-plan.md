# UI-Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Behebt 14 UI-/UX-Probleme aus dem Code-Review in drei thematischen Batches (Accessibility, Visual Consistency, User Feedback).

**Architecture:** Hauptsächlich Template- und Form-Class-Änderungen. Backend-Touch nur in `views.py` (Toast-Messages) und `services/colors.py` (Palette). Drei kleine Inline-`<script>`-Blöcke in `base.html` und `assignment_form.html`. Tests als Regression-Guards in `test_views.py`.

**Tech Stack:** Django 5.2, Tailwind via CDN (JIT-mode), pytest-django. Browser-native `<dialog>` und `beforeunload` (keine neuen JS-Libraries).

**Spec:** `docs/superpowers/specs/2026-05-17-ui-fixes-design.md`

---

## File Structure

**Modify:**
- `web/ipam/templates/base.html` — Skip-Link, Toast-Container, Drawer-A11y-Script, `id="main"`, `overflow-x` raus, Hamburger Touch-Target
- `web/ipam/templates/_sidebar.html` — `h3 → h2`, Close-Button Touch-Target
- `web/ipam/templates/index.html` — Empty-State-Link, Primary-CTA
- `web/ipam/templates/application_list.html` — Primary-CTA
- `web/ipam/templates/pool_detail.html` — Primary-CTA, Grid `overflow-x-auto`
- `web/ipam/templates/application_detail.html` — (nichts; bleibt)
- `web/ipam/templates/assignment_form.html` — Mobile `<label for>`, Reserved-Row Styling, IP-Delete Touch-Target, Primary-CTAs, Sparse-Add `inputmode/pattern`, beforeunload-Script
- `web/ipam/templates/pool_form.html` — `<style>` raus
- `web/ipam/templates/application_form.html` — `<style>` raus
- `web/ipam/forms.py` — `PoolForm`/`ApplicationForm` Widget-Class-Setup, `IPAssignmentForm` Adress-`inputmode/pattern`
- `web/ipam/services/colors.py` — `_PALETTE` 200er-Töne
- `web/ipam/views.py` — `messages.success/warning` in 13 Stellen
- `web/ipam/tests/test_views.py` — Regression-Guards

**Create:** keine neuen Files.

---

### Task 1: A1 — Heading-Hierarchie

**Files:**
- Modify: `web/ipam/templates/_sidebar.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run test, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_sidebar_uses_h2_not_h3 -v 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Fix sidebar template**

In `web/ipam/templates/_sidebar.html`:

Line 7: change `<h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">IP-Pools</h3>` → replace `<h3` with `<h2` and `</h3>` with `</h2>`.

Line 23: same — `<h3>Anwendungen</h3>` → `<h2>Anwendungen</h2>` (keeping all classes).

- [ ] **Step 4: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_sidebar_uses_h2_not_h3 -v 2>&1 | tail -5
```

Expected: PASS.

---

### Task 2: A2 — Skip-to-Content-Link

**Files:**
- Modify: `web/ipam/templates/base.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_skip_to_content_link_present(auth_client):
    """A2: Skip-link must be the first focusable element, target main content."""
    response = auth_client.get("/")
    body = response.content.decode()
    assert "Zum Inhalt springen" in body
    assert 'href="#main"' in body
    assert 'id="main"' in body
```

- [ ] **Step 2: Run test, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_skip_to_content_link_present -v 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Add skip-link and id**

In `web/ipam/templates/base.html`:

Find:
```html
<body class="bg-slate-50 text-slate-900 min-h-screen">

<input type="checkbox" id="nav-toggle" class="peer/drawer hidden">
```

Replace with:
```html
<body class="bg-slate-50 text-slate-900 min-h-screen">

<a href="#main"
   class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2
          focus:z-[100] focus:bg-slate-900 focus:text-white
          focus:px-4 focus:py-2 focus:rounded">
  Zum Inhalt springen
</a>

<input type="checkbox" id="nav-toggle" class="peer/drawer hidden">
```

Find the `<main>` tag (currently line 52 of base.html):
```html
<main class="pt-14 px-4 pb-4 md:px-6 md:pb-6 {% if user.is_authenticated %}md:pl-[calc(18rem+1.5rem)]{% endif %} overflow-x-auto">
```

Change to (also removes `overflow-x-auto` per Task 14):
```html
<main id="main" class="pt-14 px-4 pb-4 md:px-6 md:pb-6 {% if user.is_authenticated %}md:pl-[calc(18rem+1.5rem)]{% endif %}">
```

- [ ] **Step 4: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_skip_to_content_link_present -v 2>&1 | tail -5
```

Expected: PASS.

---

### Task 3: A3 — Mobile-Labels semantisch

**Files:**
- Modify: `web/ipam/templates/assignment_form.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_assignment_edit_mobile_uses_real_label_elements(auth_client):
    """A3: Mobile mini-labels must be <label for=...>, not <span>."""
    p = Pool.objects.create(name="P", cidr="10.0.0.0/24")
    a = Application.objects.create(name="A")
    s = Assignment.objects.create(pool=p, cidr="10.0.0.0/29")
    s.applications.add(a)
    response = auth_client.get(f"/assignment/{s.id}/edit/")
    body = response.content.decode()
    # At least 5 mobile-only labels per IP row (Anwendung, Gateway, Label, Notes, Adresse-when-input)
    label_count = body.count('<label class="md:hidden text-xs font-semibold')
    assert label_count >= 5, f"expected ≥5 mobile <label> elements, got {label_count}"
```

- [ ] **Step 2: Run test, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_assignment_edit_mobile_uses_real_label_elements -v 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Replace mobile spans with labels in assignment_form.html**

In `web/ipam/templates/assignment_form.html`, in the non-reserved IP-row block (5 fields), change each `<span class="md:hidden text-xs font-semibold text-slate-500">FIELDLABEL</span>` to `<label class="md:hidden text-xs font-semibold text-slate-500" for="{{ row.form.FIELDNAME.id_for_label }}">FIELDLABEL</label>`.

Concrete changes (5 spans to replace):

| Block | Field | Replace |
|---|---|---|
| Adresse (only when `is_full_mode` false; full-mode has no input) | `address` | `<span class="md:hidden text-xs font-semibold text-slate-500">Adresse</span>` → `{% if row.is_full_mode %}<span class="md:hidden text-xs font-semibold text-slate-500">Adresse</span>{% else %}<label class="md:hidden text-xs font-semibold text-slate-500" for="{{ row.form.address.id_for_label }}">Adresse</label>{% endif %}` |
| Anwendung | `application` | `<span ...>Anwendung</span>` → `<label class="md:hidden text-xs font-semibold text-slate-500" for="{{ row.form.application.id_for_label }}">Anwendung</label>` |
| Gateway | `is_gateway` | `<span ...>Gateway</span>` → `<label class="md:hidden text-xs font-semibold text-slate-500" for="{{ row.form.is_gateway.id_for_label }}">Gateway</label>` |
| Label | `label` | `<span ...>Label</span>` → `<label class="md:hidden text-xs font-semibold text-slate-500" for="{{ row.form.label.id_for_label }}">Label</label>` |
| Notes | `notes` | `<span ...>Notes</span>` → `<label class="md:hidden text-xs font-semibold text-slate-500" for="{{ row.form.notes.id_for_label }}">Notes</label>` |

Reserved-row's `<span ...>Adresse</span>` stays as `<span>` (no input behind it).

For the sparse-mode "Neue IP hinzufügen" form, give each input an explicit `id`:
- `<input type="text" name="address" ...>` → `<input type="text" id="addnew-address" name="address" ...>`
- `<select name="application" ...>` → `<select id="addnew-application" name="application" ...>`
- `<input type="checkbox" name="is_gateway">` → `<input type="checkbox" id="addnew-is_gateway" name="is_gateway">`
- `<input type="text" name="label" ...>` → `<input type="text" id="addnew-label" name="label" ...>`
- `<input type="text" name="notes" ...>` → `<input type="text" id="addnew-notes" name="notes" ...>`

Then replace each sparse-mode `<span class="md:hidden ...">FIELDLABEL</span>` with `<label class="md:hidden text-xs font-semibold text-slate-500" for="addnew-FIELDNAME">FIELDLABEL</label>`.

- [ ] **Step 4: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_assignment_edit_mobile_uses_real_label_elements -v 2>&1 | tail -5
```

Expected: PASS.

- [ ] **Step 5: Run full suite to ensure no regressions**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green.

---

### Task 4: A4 — Touch-Targets ≥44×44

**Files:**
- Modify: `web/ipam/templates/base.html` (Hamburger)
- Modify: `web/ipam/templates/_sidebar.html` (Close button)
- Modify: `web/ipam/templates/assignment_form.html` (IP-Delete `×`)

- [ ] **Step 1: Bump Hamburger size in base.html**

Find:
```html
<label for="nav-toggle" class="md:hidden p-2 -ml-2 cursor-pointer" aria-label="Menü öffnen">
```

Replace with:
```html
<label for="nav-toggle" class="md:hidden p-3 -ml-1 cursor-pointer min-w-[44px] min-h-[44px] flex items-center" aria-label="Menü öffnen">
```

- [ ] **Step 2: Bump Sidebar-Close size in `_sidebar.html`**

Find:
```html
<label for="nav-toggle"
       class="cursor-pointer text-slate-400 hover:text-slate-700 text-2xl leading-none px-2 -mr-2"
       aria-label="Menü schließen">×</label>
```

Replace with:
```html
<label for="nav-toggle"
       class="cursor-pointer text-slate-400 hover:text-slate-700 text-2xl leading-none
              min-w-[44px] min-h-[44px] flex items-center justify-center -mr-2"
       aria-label="Menü schließen">×</label>
```

- [ ] **Step 3: Bump IP-Delete `×` in `assignment_form.html`**

Find:
```html
<button type="submit" formnovalidate
        formaction="{% url 'ipam:ip_assignment_delete' assignment.id row.ip_assignment.id %}"
        class="text-red-600 hover:underline bg-transparent border-0 cursor-pointer p-2 md:p-0"
        title="IP-Zuordnung löschen">×</button>
```

Replace with:
```html
<button type="submit" formnovalidate
        formaction="{% url 'ipam:ip_assignment_delete' assignment.id row.ip_assignment.id %}"
        class="text-red-600 hover:underline bg-transparent border-0 cursor-pointer
               min-w-[44px] min-h-[44px] flex items-center justify-center
               md:min-w-0 md:min-h-0 md:block md:p-0"
        title="IP-Zuordnung löschen">×</button>
```

- [ ] **Step 4: Run full suite**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green.

---

### Task 5: A5 — Mobile-Drawer A11y

**Files:**
- Modify: `web/ipam/templates/base.html`

- [ ] **Step 1: Mark up Hamburger as button-like**

In `base.html`, the Hamburger label (already touched in Task 4) needs role/aria/tabindex/aria-controls. Update to:

```html
<label for="nav-toggle"
       role="button" tabindex="0"
       aria-controls="sidebar-drawer" aria-expanded="false"
       class="md:hidden p-3 -ml-1 cursor-pointer min-w-[44px] min-h-[44px] flex items-center"
       aria-label="Menü öffnen">
    <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
    </svg>
</label>
```

- [ ] **Step 2: Add `id="sidebar-drawer"` to `<aside>`**

In `base.html`, find the `<aside>` opening tag and add `id="sidebar-drawer"`:

```html
<aside id="sidebar-drawer" class="
    fixed top-14 bottom-0 left-0 z-40 w-72 -translate-x-full
    peer-checked/drawer:translate-x-0 transition-transform duration-200
    bg-white border-r border-slate-200 p-3 overflow-y-auto text-sm
    md:translate-x-0 md:transition-none
">
```

- [ ] **Step 3: Add inline JS for drawer A11y at end of base.html**

In `base.html`, just before `</body>` (and only when authenticated):

```html
{% if user.is_authenticated %}
<script>
(function () {
  const toggle = document.getElementById('nav-toggle');
  const btn = document.querySelector('label[for="nav-toggle"][role="button"]');
  if (!toggle || !btn) return;

  function sync() { btn.setAttribute('aria-expanded', toggle.checked); }
  toggle.addEventListener('change', sync);
  sync();

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && toggle.checked) {
      toggle.checked = false;
      sync();
    }
  });

  btn.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      toggle.checked = !toggle.checked;
      sync();
    }
  });
})();
</script>
{% endif %}
```

- [ ] **Step 4: Write smoke test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_mobile_drawer_has_aria_attributes(auth_client):
    """A5: Mobile drawer has accessible attributes — aria-controls + aria-expanded."""
    response = auth_client.get("/")
    body = response.content.decode()
    assert 'aria-controls="sidebar-drawer"' in body
    assert 'aria-expanded="false"' in body
    assert 'id="sidebar-drawer"' in body
```

- [ ] **Step 5: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_mobile_drawer_has_aria_attributes -v 2>&1 | tail -5
```

Expected: PASS.

---

### Task 6: B1 — 200er-Palette

**Files:**
- Modify: `web/ipam/services/colors.py`

- [ ] **Step 1: Write a unit test for the palette**

Append to `web/ipam/tests/test_blocks.py` (since there's no `test_colors.py`):

```python
def test_palette_uses_tailwind_200_tones():
    """B1: Color palette uses 200-tone Tailwind colors for WCAG AAA contrast vs slate-900."""
    from ipam.services.colors import _PALETTE
    # Spot-check three known 200-tone hex values
    assert "#FECACA" in _PALETTE  # red-200
    assert "#BBF7D0" in _PALETTE  # green-200
    assert "#BFDBFE" in _PALETTE  # blue-200
    # Make sure none of the old 300-tone hex values remain
    assert "#FCA5A5" not in _PALETTE  # red-300 (old)
    assert "#86EFAC" not in _PALETTE  # green-300 (old)
    assert "#7DD3FC" not in _PALETTE  # sky-300 (old)
```

- [ ] **Step 2: Run test, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_blocks.py::test_palette_uses_tailwind_200_tones -v 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Replace palette in colors.py**

In `web/ipam/services/colors.py`, replace the `_PALETTE` constant:

```python
_PALETTE = [
    "#FECACA",  # red-200
    "#FED7AA",  # orange-200
    "#FEF08A",  # yellow-200
    "#D9F99D",  # lime-200
    "#BBF7D0",  # green-200
    "#A7F3D0",  # emerald-200
    "#99F6E4",  # teal-200
    "#BAE6FD",  # sky-200
    "#BFDBFE",  # blue-200
    "#C7D2FE",  # indigo-200
    "#DDD6FE",  # violet-200
    "#E9D5FF",  # purple-200
    "#F5D0FE",  # fuchsia-200
    "#FBCFE8",  # pink-200
    "#FECDD3",  # rose-200
    "#E4D88A",  # warm khaki (kept for variety)
]
```

- [ ] **Step 4: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_blocks.py::test_palette_uses_tailwind_200_tones -v 2>&1 | tail -5
```

Expected: PASS.

- [ ] **Step 5: Run full suite**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green.

---

### Task 7: B2 — Primär-CTA vereinheitlichen

**Files:**
- Modify: `web/ipam/templates/index.html`
- Modify: `web/ipam/templates/application_list.html`
- Modify: `web/ipam/templates/pool_detail.html`
- Modify: `web/ipam/templates/assignment_form.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py -k "no_blue_primary_cta" -v 2>&1 | tail -10
```

Expected: 3 FAIL.

- [ ] **Step 3: Bulk replace via sed**

```bash
cd /srv/docker/IP-Planer && \
sed -i 's/bg-blue-600 hover:bg-blue-700 text-white/bg-slate-800 hover:bg-slate-700 text-white/g' \
  web/ipam/templates/index.html \
  web/ipam/templates/application_list.html \
  web/ipam/templates/pool_detail.html \
  web/ipam/templates/assignment_form.html && \
sed -i 's/bg-slate-700 hover:bg-slate-600 text-white/bg-slate-800 hover:bg-slate-700 text-white/g' \
  web/ipam/templates/assignment_form.html
```

- [ ] **Step 4: Verify Logout button unchanged**

The Logout button in `base.html` should remain `bg-slate-700`:

```bash
grep "bg-slate-700" /srv/docker/IP-Planer/web/ipam/templates/base.html
```

Expected: shows the Logout button line. If empty, the sed accidentally hit base.html (it shouldn't have — base.html wasn't in the list).

- [ ] **Step 5: Run tests, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py -k "no_blue_primary_cta" -v 2>&1 | tail -10
```

Expected: 3 PASS.

- [ ] **Step 6: Run full suite**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green.

---

### Task 8: B3 — Reserved-Rows deutlicher

**Files:**
- Modify: `web/ipam/templates/assignment_form.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run test, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_reserved_row_uses_distinctive_styling -v 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Update reserved-row styling**

In `web/ipam/templates/assignment_form.html`, find the reserved-row container:

```html
{% if row.reserved_kind %}
<div class="block md:contents bg-slate-50 border md:border-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0">
```

Replace with:

```html
{% if row.reserved_kind %}
<div class="block md:contents bg-slate-100 border-l-4 border-l-slate-300 md:border-l-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0">
```

Also bump the "Netzwerk-Adresse / Broadcast-Adresse" text from `text-slate-500 italic` to `text-slate-600 italic font-medium`. Find:

```html
<div class="md:px-2 md:py-2 md:border-t md:col-span-5 text-slate-500 italic">
    {% if row.reserved_kind == "network" %}Netzwerk-Adresse — reserviert{% else %}Broadcast-Adresse — reserviert{% endif %}
</div>
```

Replace with:

```html
<div class="md:px-2 md:py-2 md:border-t md:col-span-5 text-slate-600 italic font-medium">
    {% if row.reserved_kind == "network" %}Netzwerk-Adresse — reserviert{% else %}Broadcast-Adresse — reserviert{% endif %}
</div>
```

- [ ] **Step 4: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_reserved_row_uses_distinctive_styling -v 2>&1 | tail -5
```

Expected: PASS.

---

### Task 9: B4 — Inline `<style>` raus

**Files:**
- Modify: `web/ipam/forms.py`
- Modify: `web/ipam/templates/pool_form.html`
- Modify: `web/ipam/templates/application_form.html`

- [ ] **Step 1: Add `__init__` to `PoolForm` in forms.py**

Find:
```python
class PoolForm(forms.ModelForm):
    class Meta:
        model = Pool
        fields = ["name", "cidr", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_cidr(self):
```

Insert a new `__init__` method between `Meta` and `clean_cidr`:

```python
class PoolForm(forms.ModelForm):
    class Meta:
        model = Pool
        fields = ["name", "cidr", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-slate-300 rounded px-3 py-2 text-sm "
                "focus:outline-none focus:ring-2 focus:ring-slate-400",
            )

    def clean_cidr(self):
```

- [ ] **Step 2: Add `__init__` to `ApplicationForm` in forms.py**

Find:
```python
class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
```

Replace with:

```python
class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-slate-300 rounded px-3 py-2 text-sm "
                "focus:outline-none focus:ring-2 focus:ring-slate-400",
            )
```

- [ ] **Step 3: Remove `<style>` block from pool_form.html**

In `web/ipam/templates/pool_form.html`, delete the entire trailing `<style>` block (after the form `</div>` and before `{% endblock %}`):

```html
<style>
    input[type=text], input[type=number], select, textarea {
        border: 1px solid rgb(203 213 225);
        border-radius: 0.25rem;
        width: 100%;
        padding: 0.25rem 0.5rem;
    }
</style>
```

- [ ] **Step 4: Remove `<style>` block from application_form.html**

Same as Step 3, in `web/ipam/templates/application_form.html`.

- [ ] **Step 5: Run full suite**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green (Pool/Application form tests already exist and still pass).

---

### Task 10: C1 — Toast-Messages

**Files:**
- Modify: `web/ipam/views.py`
- Modify: `web/ipam/templates/base.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py -k "shows_success_toast or shows_warning_toast" -v 2>&1 | tail -10
```

Expected: 4 FAIL.

- [ ] **Step 3: Add `messages` import + calls to views.py**

In `web/ipam/views.py` near the top imports add:

```python
from django.contrib import messages
```

Then add `messages.success(request, "...")` / `messages.warning(request, "...")` calls just before each `redirect(...)` in POST-redirecting views. Concrete edits:

**`pool_new`** — find `return redirect("ipam:pool_detail", pool_id=pool.id)` and insert before it:
```python
            messages.success(request, "Pool angelegt.")
```

**`pool_edit`** — find `return redirect("ipam:pool_detail", pool_id=pool.id)` (in the form-valid branch) and insert before:
```python
            messages.success(request, "Pool gespeichert.")
```

**`pool_delete`** — find the function. In the blocked branch (assignments exist):
```python
    if pool.assignments.exists():
        messages.warning(request, "Pool nicht gelöscht — Zuweisungen vorhanden.")
        return redirect("ipam:pool_detail", pool_id=pool.pk)
    pool.delete()
    messages.success(request, "Pool gelöscht.")
    return redirect("ipam:index")
```

**`application_new`** — before redirect:
```python
            messages.success(request, "Anwendung angelegt.")
```

**`application_edit`** — before redirect:
```python
            messages.success(request, "Anwendung gespeichert.")
```

**`application_delete`** — both branches:
```python
    if app.ip_assignments.exists():
        messages.warning(request, "Anwendung nicht gelöscht — IP-Zuordnungen vorhanden.")
        return redirect("ipam:application_detail", application_id=app.pk)
    app.delete()
    messages.success(request, "Anwendung gelöscht.")
    return redirect("ipam:application_list")
```

**`assignment_new`** — before redirect:
```python
            messages.success(request, "Subnetz angelegt.")
```

**`assignment_edit`** — before redirect (form-valid branch):
```python
            messages.success(request, "Subnetz gespeichert.")
```

**`assignment_delete`** — before redirect:
```python
    messages.success(request, "Subnetz gelöscht.")
    return redirect("ipam:pool_detail", pool_id=pool_id)
```

**`ip_assignment_save`** — two redirect paths:
- Delete action branch (`if request.POST.get("action") == "delete":`):
  ```python
        if ip_id:
            IPAssignment.objects.filter(pk=ip_id, assignment_id=assignment_id).delete()
            messages.success(request, "IP-Zuordnung gelöscht.")
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)
  ```
- Form-valid branch (after `obj.save()`):
  ```python
            obj.save()
        messages.success(request, "IP-Zuordnung gespeichert.")
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)
  ```

**`ip_assignment_save_bulk`** — after the atomic block, before the redirect:
```python
                obj.save()
        if any_change:
            messages.success(request, "IP-Zuordnungen gespeichert.")
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)
```

**`ip_assignment_delete`** — before redirect:
```python
    obj.delete()
    messages.success(request, "IP-Zuordnung gelöscht.")
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)
```

- [ ] **Step 4: Add toast container to base.html**

In `web/ipam/templates/base.html`, immediately after the `<main ...>` opening tag, insert:

```html
{% if messages %}
<div role="status" aria-live="polite"
     class="fixed top-16 right-4 z-50 flex flex-col gap-2 max-w-sm">
  {% for m in messages %}
  <div class="bg-white border-l-4 px-4 py-3 rounded shadow-lg text-sm
              {% if m.level_tag == 'success' %}border-green-500{% endif %}
              {% if m.level_tag == 'warning' %}border-amber-500{% endif %}
              {% if m.level_tag == 'error' %}border-red-500{% endif %}
              {% if m.level_tag == 'info' %}border-slate-500{% endif %}"
       data-toast>
    {{ m }}
  </div>
  {% endfor %}
</div>
<script>
setTimeout(() => document.querySelectorAll('[data-toast]').forEach(t => t.remove()), 4000);
</script>
{% endif %}
```

- [ ] **Step 5: Run new toast tests**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py -k "shows_success_toast or shows_warning_toast" -v 2>&1 | tail -10
```

Expected: 4 PASS.

- [ ] **Step 6: Run full suite**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green.

---

### Task 11: C2 — Bulk-Save beforeunload

**Files:**
- Modify: `web/ipam/templates/assignment_form.html`

- [ ] **Step 1: Add inline script at end of `assignment_form.html`**

In `web/ipam/templates/assignment_form.html`, find the existing `{% if assignment %}<script>` block at the bottom. Just before the closing `})();` of the IIFE for pill checkbox handling, no — that's a different concern. Add a NEW IIFE inside the same `{% if assignment %}<script>...</script>{% endif %}` block, after the existing one:

```html
{% if assignment %}
<script>
(function () {
    /* … existing pill-picker code … */
})();

(function () {
    const form = document.querySelector('form[action$="/save_bulk/"]');
    if (!form) return;
    let dirty = false;
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('submit', () => { dirty = false; });
    window.addEventListener('beforeunload', (e) => {
        if (dirty) { e.preventDefault(); e.returnValue = ''; }
    });
})();
</script>
{% endif %}
```

The exact insertion is just before `</script>`, after the existing IIFE.

- [ ] **Step 2: Run full suite (smoke)**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green. (No new test — beforeunload behavior is browser-only; manual smoke test in Step 3.)

- [ ] **Step 3: Manual smoke test**

In a browser at the deployed dev URL: edit a Subnet, change one IP-application field, click "Zurück zum Pool". Browser should show the native "Changes you made may not be saved" prompt.

---

### Task 12: C3 — Adress-Input-Hints

**Files:**
- Modify: `web/ipam/forms.py`
- Modify: `web/ipam/templates/assignment_form.html`

- [ ] **Step 1: Add `inputmode/pattern/placeholder` in `IPAssignmentForm.__init__`**

In `web/ipam/forms.py`, find `IPAssignmentForm.__init__`. After the class-setup loop, before `self.assignment = assignment`... wait, the current order is:

```python
def __init__(self, *args, assignment=None, **kwargs):
    super().__init__(*args, **kwargs)
    self.assignment = assignment
    if assignment is not None:
        self.fields["application"].queryset = assignment.applications.all()
    for name, field in self.fields.items():
        if name == "is_gateway":
            continue
        extra = " js-ip-app-select" if name == "application" else ""
        field.widget.attrs.setdefault(...)
```

Just after the `for` loop ends, add:

```python
        self.fields["address"].widget.attrs.update({
            "inputmode": "numeric",
            "pattern": r"[0-9a-fA-F:.]+",
            "placeholder": "z.B. 10.0.0.1",
        })
```

(Note 8-space indent: this is inside `__init__` but outside the `for` loop.)

- [ ] **Step 2: Add same attrs to sparse-mode add-form input**

In `web/ipam/templates/assignment_form.html`, find:

```html
<input type="text" name="address" placeholder="z.B. 10.0.0.1"
       class="border border-slate-300 rounded px-2 py-1 text-xs w-40">
```

Replace with:

```html
<input type="text" id="addnew-address" name="address" placeholder="z.B. 10.0.0.1"
       inputmode="numeric" pattern="[0-9a-fA-F:.]+"
       class="border border-slate-300 rounded px-2 py-1 text-xs w-40">
```

(The `id="addnew-address"` was already required by Task 3 — keep both attrs consistent.)

- [ ] **Step 3: Write test**

Append to `web/ipam/tests/test_views.py`:

```python
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_assignment_edit_address_inputs_have_inputmode_and_pattern -v 2>&1 | tail -5
```

Expected: PASS.

---

### Task 13: C4 — Index-Empty-State auf `pool_new`

**Files:**
- Modify: `web/ipam/templates/index.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_index_empty_state_links_to_pool_new(auth_client):
    """C4: When no pools exist, empty state links to /pool/new/, not /admin/."""
    # No pools — auth_client fixture creates user, no Pool objects
    response = auth_client.get("/")
    body = response.content.decode()
    assert 'href="/pool/new/"' in body
    # Admin link must NOT be the empty-state target
    assert 'Pool anlegen' in body
    # Old admin link gone from empty-state copy
    assert '<a href="/admin/" class="underline">Admin</a>' not in body
```

- [ ] **Step 2: Run test, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_index_empty_state_links_to_pool_new -v 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Update empty-state in `index.html`**

In `web/ipam/templates/index.html`, find:

```html
<p class="text-slate-500">Noch keine Pools. Im <a href="/admin/" class="underline">Admin</a> anlegen.</p>
```

Replace with:

```html
<p class="text-slate-500">Noch keine Pools. <a href="{% url 'ipam:pool_new' %}" class="underline">Pool anlegen</a>.</p>
```

- [ ] **Step 4: Run test, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py::test_index_empty_state_links_to_pool_new -v 2>&1 | tail -5
```

Expected: PASS.

---

### Task 14: C5 — `overflow-x` aus `<main>` raus, scoped auf Grid

**Files:**
- Modify: `web/ipam/templates/base.html` (already touched in Task 2 — remove `overflow-x-auto` there)
- Modify: `web/ipam/templates/pool_detail.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_main_has_no_overflow_x_auto(auth_client):
    """C5: <main> no longer has overflow-x-auto (was Punkt 25 — moved to grid container)."""
    response = auth_client.get("/")
    body = response.content.decode()
    # Find the <main ...> opening tag and verify no overflow-x-auto on it
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
```

- [ ] **Step 2: Run tests, verify fail**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py -k "has_no_overflow_x_auto or grid_container_has_overflow" -v 2>&1 | tail -10
```

Expected:
- `test_main_has_no_overflow_x_auto`: PASS already (Task 2 removed `overflow-x-auto`)
- `test_ipv4_grid_container_has_overflow_x_auto`: FAIL.

- [ ] **Step 3: Add `overflow-x-auto` to grid container in pool_detail.html**

In `web/ipam/templates/pool_detail.html`, find:

```html
<div class="flex flex-wrap gap-1 items-stretch">
```

Replace with:

```html
<div class="flex flex-wrap gap-1 items-stretch overflow-x-auto">
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest ipam/tests/test_views.py -k "has_no_overflow_x_auto or grid_container_has_overflow" -v 2>&1 | tail -10
```

Expected: 2 PASS.

- [ ] **Step 5: Run full suite**

```bash
cd /srv/docker/IP-Planer && docker compose exec -T web pytest 2>&1 | tail -3
```

Expected: all green.

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| A1 Heading-Hierarchie | Task 1 |
| A2 Skip-to-Content-Link | Task 2 |
| A3 Mobile-Labels semantisch | Task 3 |
| A4 Touch-Targets ≥44×44 | Task 4 |
| A5 Mobile-Drawer A11y | Task 5 |
| B1 200er-Palette | Task 6 |
| B2 Primär-CTA vereinheitlichen | Task 7 |
| B3 Reserved-Rows deutlicher | Task 8 |
| B4 Inline `<style>` raus | Task 9 |
| C1 Toast-Messages | Task 10 |
| C2 Bulk-Save beforeunload | Task 11 |
| C3 Adress-Input-Hints | Task 12 |
| C4 Index-Empty-State | Task 13 |
| C5 `overflow-x` Scope | Task 14 |

All 14 spec items mapped to tasks. No gaps.

**Placeholder scan:** no TBD/TODO. All code blocks complete.

**Type/name consistency:** context-key names match across tasks. Spec strings ("Pool gelöscht.", "border-l-4 border-l-slate-300", "addnew-address" prefix) are reused consistently.

**Task interactions:** Task 2 removes `overflow-x-auto` from `<main>` (as part of skip-link work, since both touch the `<main>` tag), Task 14 then adds it to the grid container. The test `test_main_has_no_overflow_x_auto` thus passes after Task 2, not Task 14 — noted explicitly in Task 14 Step 2.

Tasks 3 and 12 both touch the sparse-mode address input. Task 3 adds `id="addnew-address"`; Task 12 adds `inputmode/pattern`. Both must end up on the same `<input>`. The plan instructs both in their respective steps with full final markup.

Task 7's sed-based bulk replace is safe: the pattern `bg-blue-600 hover:bg-blue-700 text-white` is specific enough not to false-positive on other classes. Verified by Step 4 sanity check that `base.html`'s Logout button still has `bg-slate-700`.
