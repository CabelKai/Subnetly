# UI-Fixes — 14 Punkte aus Code-Review

Behebt die UI-/UX-Problem aus dem Code-Review vom 2026-05-17. Drei
thematische Batches in einem Spec, weil alle Änderungen denselben
Template-/Form-Surface anfassen.

## Design-Entscheidungen (vorab geklärt)

- **Farb-Palette**: Tailwind 200er-Töne mit `text-slate-900`. Garantiert
  WCAG AAA für alle Block-Farben.
- **Primär-CTA**: durchgängig `bg-slate-800 hover:bg-slate-700 text-white`.
  Blau verschwindet als Aktions-Farbe. Sekundär bleibt `bg-slate-200`.
- **Unsaved-Changes-Schutz**: browser-native `beforeunload` (kein Custom-Modal).

---

## Batch A — Accessibility-Fundament

### A1 — Heading-Hierarchie (Review-Punkt 18)

`web/ipam/templates/_sidebar.html` Z.7 und Z.23: `<h3>` → `<h2>`. Die
Page-Title in `index.html`, `pool_detail.html`, `application_detail.html`
ist bereits `<h1>`. Sidebar-Sections sind eine Ebene drunter → `<h2>`.

### A2 — Skip-to-Content-Link (Review-Punkt 19)

In `web/ipam/templates/base.html` direkt nach `<body>`:

```html
<a href="#main"
   class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2
          focus:z-[100] focus:bg-slate-900 focus:text-white
          focus:px-4 focus:py-2 focus:rounded">
  Zum Inhalt springen
</a>
```

`<main>`-Tag bekommt `id="main"`.

### A3 — Mobile-Labels semantisch (Review-Punkt 22)

In `web/ipam/templates/assignment_form.html` IP-Rows: alle Mobile-Mini-
Labels von `<span class="md:hidden ...">Label</span>` auf
`<label class="md:hidden ..." for="{{ row.form.X.id_for_label }}">Label</label>`.

Betroffene Stellen (nicht-reservierte Row, 5 Felder):
- Adresse → `for="{{ row.form.address.id_for_label }}"` (nur wenn
  `is_full_mode` false, weil sonst gibt es kein Input-Element)
- Anwendung → `for="{{ row.form.application.id_for_label }}"`
- Gateway → `for="{{ row.form.is_gateway.id_for_label }}"`
- Label → `for="{{ row.form.label.id_for_label }}"`
- Notes → `for="{{ row.form.notes.id_for_label }}"`

Reservierte Row: Adresse-Label bleibt `<span>` (kein Input dahinter).
Sparse-Mode Add-Form: die fünf Felder haben `name=` Attribute aber keine
`id=`. Lösung: jedem Input `id="addnew-address"` etc. geben und entspreche
`<label for="addnew-address">` benutzen.

### A4 — Touch-Targets ≥ 44 × 44 (Review-Punkt 15)

Drei Buttons unter dem 44×44-Mindestmaß:

| Element | Datei:Zeile | Aktuell | Neu |
|---|---|---|---|
| Hamburger | `base.html:15` | `p-2 -ml-2` (~40×40) | `p-3 -ml-1` (≥44×44) |
| Sidebar-Close-`×` | `_sidebar.html:3` | `text-2xl px-2` | `text-2xl min-w-[44px] min-h-[44px] flex items-center justify-center` |
| IP-Delete-`×` | `assignment_form.html:117` | `p-2 md:p-0` (~32×32 mobile) | `min-w-[44px] min-h-[44px] flex items-center justify-center md:min-w-0 md:min-h-0 md:block` |

### A5 — Mobile-Drawer A11y (Review-Punkt 17)

Aktuelles Markup ist Checkbox-Hack: kein `aria-expanded`, kein Esc-Close,
kein Focus-Trap.

Lösung — minimal-invasiv, behält den CSS-only-Layout-Ansatz:

1. Hamburger bleibt `<label for="nav-toggle">`, bekommt zusätzlich
   `role="button"`, `tabindex="0"`, `aria-controls="sidebar-drawer"`,
   `aria-expanded="false"`.
2. `<aside>` bekommt `id="sidebar-drawer"`.
3. Inline-`<script>` in `base.html` (gated mit `{% if user.is_authenticated %}`):

```javascript
(function () {
  const toggle = document.getElementById('nav-toggle');
  const btn = document.querySelector('label[for="nav-toggle"][role="button"]');
  if (!toggle || !btn) return;

  function sync() { btn.setAttribute('aria-expanded', toggle.checked); }
  toggle.addEventListener('change', sync);
  sync();

  // Esc closes drawer
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && toggle.checked) toggle.checked = false, sync();
  });

  // Space/Enter on <label role="button">
  btn.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      toggle.checked = !toggle.checked;
      sync();
    }
  });
})();
```

Kein Focus-Trap (außer Scope) — der pragmatische Schutz reicht für die
interne Anwendung.

---

## Batch B — Visual Consistency

### B1 — 200er-Palette (Review-Punkt 16)

`web/ipam/services/colors.py` `_PALETTE` ersetzen:

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

16 Einträge, alle 200er-Tailwind-Töne plus den existierenden Khaki-
Akzent. Block-Text in `pool_detail.html` ist schon `text-slate-900` —
keine Template-Änderung nötig.

### B2 — Primär-CTA vereinheitlichen (Review-Punkt 23)

**Suchen/Ersetzen:**
- `bg-blue-600 hover:bg-blue-700 text-white` → `bg-slate-800 hover:bg-slate-700 text-white`
  - Vorkommen: `index.html:8`, `application_list.html:7`,
    `pool_detail.html:16`, `assignment_form.html:184`,
    `assignment_form.html` Sparse-Mode `+ IP hinzufügen` Button
- `bg-slate-700 hover:bg-slate-600 text-white` → `bg-slate-800 hover:bg-slate-700 text-white`
  - Vorkommen: `assignment_form.html:38` (Subnetz speichern),
    `assignment_form.html:142` (Alle IP-Zuordnungen speichern)
- Login-Button `bg-slate-800` (`registration/login.html`): bleibt
- Logout-Button (`base.html:31`): bleibt `bg-slate-700` — als Element in
  der dunklen Header-Bar ist Slate-700 visuell stimmig

Tertiär bleibt: `text-slate-500 hover:text-slate-700 underline` für
"Abbrechen"-Links.

### B3 — Reserved-Rows deutlicher (Review-Punkt 28)

In `web/ipam/templates/assignment_form.html` reservierte Row aktuell:

```html
<div class="block md:contents bg-slate-50 border md:border-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0">
```

Neu:

```html
<div class="block md:contents bg-slate-100 border-l-4 border-l-slate-300 md:border-l-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0">
```

Mobile: dicker Slate-300-Balken links, `bg-slate-100` Hintergrund.
Desktop: bleibt der `md:border-t`-Grid-Look der Tabelle erhalten.

Zusätzlich der italic Status-Text bekommt `font-medium text-slate-600`
(vorher `text-slate-500 italic` — italic bleibt, aber dunkler/medium).

### B4 — Inline `<style>` raus (Review-Punkt 24)

`web/ipam/templates/pool_form.html` und `application_form.html` enthalten
am Ende je einen `<style>`-Block:

```css
input[type=text], input[type=number], select, textarea {
    border: 1px solid rgb(203 213 225);
    border-radius: 0.25rem;
    width: 100%;
    padding: 0.25rem 0.5rem;
}
```

Ersatz: In `web/ipam/forms.py` jeweils `PoolForm.__init__` und
`ApplicationForm.__init__` mit Widget-Class-Setup (analog
`AssignmentForm.__init__` Z.30–36):

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    for name, field in self.fields.items():
        field.widget.attrs.setdefault(
            "class",
            "w-full border border-slate-300 rounded px-3 py-2 text-sm "
            "focus:outline-none focus:ring-2 focus:ring-slate-400",
        )
```

`<style>`-Blöcke aus beiden Templates entfernen.

---

## Batch C — User Feedback

### C1 — Toast-Messages via Django Messages (Review-Punkt 21)

**Backend:** in jeden POST-redirecting View Erfolgs-/Warn-Messages
ergänzen (Django `messages`-Framework ist bereits installiert, siehe
`settings.py` MIDDLEWARE + TEMPLATES context_processors):

| View | Trigger | Message |
|---|---|---|
| `pool_new` | success | "Pool angelegt." |
| `pool_edit` | success | "Pool gespeichert." |
| `pool_delete` | success | "Pool gelöscht." |
| `pool_delete` | blocked branch | warning "Pool nicht gelöscht — Zuweisungen vorhanden." |
| `application_new` | success | "Anwendung angelegt." |
| `application_edit` | success | "Anwendung gespeichert." |
| `application_delete` | success | "Anwendung gelöscht." |
| `application_delete` | blocked branch | warning "Anwendung nicht gelöscht — IP-Zuordnungen vorhanden." |
| `assignment_new` | success | "Subnetz angelegt." |
| `assignment_edit` | success | "Subnetz gespeichert." |
| `assignment_delete` | success | "Subnetz gelöscht." |
| `ip_assignment_save` | success (incl. `action=delete`) | "IP-Zuordnung gespeichert." / "IP-Zuordnung gelöscht." |
| `ip_assignment_save_bulk` | success | "IP-Zuordnungen gespeichert." |
| `ip_assignment_delete` | success | "IP-Zuordnung gelöscht." |

**Frontend:** in `base.html` direkt nach `<main>`-Tag-Beginn:

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

Auto-dismiss nach 4s; `aria-live="polite"` für Screenreader; kein
Focus-Stealing.

**Tests:** assert nach POST mit `follow=True`:
- `assert "Pool gespeichert." in response.content.decode()`
- Pro CRUD-Operation einer.

### C2 — Bulk-Save beforeunload (Review-Punkt 26)

In `assignment_form.html` JS-Block am Ende (bei `{% if assignment %}`),
nach dem existierenden IIFE für `js-ip-app-select`:

```javascript
(function(){
  const form = document.querySelector('form[action$="/save_bulk/"]');
  if (!form) return;
  let dirty = false;
  form.addEventListener('input', () => { dirty = true; });
  form.addEventListener('submit', () => { dirty = false; });
  window.addEventListener('beforeunload', (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });
})();
```

Browser zeigt native "Changes you made may not be saved"-Prompt bei
Navigation/Tab-Close.

### C3 — Adress-Input-Hints (Review-Punkt 27)

**Pro IP-Row** (`IPAssignmentForm`, kommt aus `forms.py`):

In `IPAssignmentForm.__init__` zwischen den existierenden Class-Setup-
Loop und `self.assignment = assignment` ergänzen:

```python
self.fields["address"].widget.attrs.update({
    "inputmode": "numeric",
    "pattern": r"[0-9a-fA-F:.]+",
    "placeholder": "z.B. 10.0.0.1",
})
```

**Sparse-Mode Add-Form** (`assignment_form.html:159`):

```html
<input type="text" name="address" placeholder="z.B. 10.0.0.1"
       inputmode="numeric" pattern="[0-9a-fA-F:.]+"
       class="border border-slate-300 rounded px-2 py-1 text-xs w-40">
```

### C4 — Index-Empty-State auf `pool_new` (Review-Punkt 20)

`index.html:26`:

```html
<p class="text-slate-500">
  Noch keine Pools. <a href="{% url 'ipam:pool_new' %}" class="underline">Pool anlegen</a>.
</p>
```

Statt aktuell `/admin/`.

### C5 — `overflow-x` aus `<main>` raus (Review-Punkt 25)

`web/ipam/templates/base.html` Z.52:

```html
<main id="main" class="pt-14 px-4 pb-4 md:px-6 md:pb-6 {% if user.is_authenticated %}md:pl-[calc(18rem+1.5rem)]{% endif %}">
```

`overflow-x-auto` entfernt. Scope auf das IPv4-Grid in
`pool_detail.html:23`:

```html
<div class="flex flex-wrap gap-1 items-stretch overflow-x-auto">
```

---

## Testabdeckung

Pro Batch ein bis drei Regression-Guards in `test_views.py`:

**Batch A:**
- `test_sidebar_uses_h2_not_h3` — assert `<h2` in body, no `<h3 class="text-xs font-semibold text-slate-500"` (Sidebar-h3-Marker)
- `test_skip_link_present` — assert `Zum Inhalt springen` and `id="main"` in body
- `test_assignment_edit_mobile_uses_real_labels` — assert `<label class="md:hidden"` count ≥ 5

**Batch B:**
- `test_color_palette_uses_200_tones` — import `_PALETTE`, assert specific hex values present
- `test_no_blue_primary_cta_in_templates` — render index/application_list/pool_detail, assert `bg-blue-600` not in body
- `test_reserved_row_uses_distinctive_styling` — assert `border-l-4 border-l-slate-300` in assignment_edit body for a /30
- (Inline-`<style>` removal: indirekt durch Pool/Application-Form-Tests, da diese das Rendering schon prüfen)

**Batch C:**
- `test_pool_create_shows_success_toast` — POST + follow=True, assert `Pool angelegt.` in body
- `test_assignment_delete_shows_success_toast` — analog
- `test_pool_delete_blocked_shows_warning_toast` — assert warning text + warning border class
- `test_index_empty_state_links_to_pool_new` — assert `/pool/new/` in empty body
- `test_main_has_no_overflow_x_auto` — assert `<main` line in body does not contain `overflow-x-auto`

Plus pro Stelle die existierenden Tests grün halten (z.B. existierende
`test_assignment_edit_*` müssen weiterhin laufen).

---

## Risiken / Edge Cases

1. **Tailwind CDN und Arbitrary Values**: `min-w-[44px]`, `focus:z-[100]`
   etc. funktionieren bei der CDN-JIT-Variante. Verifiziert anhand der
   bestehenden Klassen (`md:pl-[calc(18rem+1.5rem)]` ist schon im
   Einsatz).
2. **Inline-Script-CSP**: Bei späterer CSP-Hardening würden die inline
   `<script>`-Blöcke (Drawer A11y, Toast-Dismiss, Bulk-Save-Dirty) eine
   `script-src 'unsafe-inline'`-Whitelist brauchen. Out of scope für
   diesen Spec.
3. **Toast in Modals**: Wenn ein Toast erscheint während das Delete-Modal
   offen ist, überlagert er den Modal-Inhalt (z-index Modal=auto in
   `<dialog>`, Toast=`z-50`). Akzeptabel — Modals schließen sich nach
   dem POST-Submit ohnehin.
4. **`<label>`-`for=` auf Mobile**: Auf Desktop wird das `<label>` durch
   `md:hidden` versteckt. Der Form-Label für Desktop ist separat im
   Tabellen-Header `<div class="hidden md:block">Anwendung</div>`. Das
   ist kein `<label for=>`, aber als Header-Cell ist es semantisch
   weniger kritisch — keep as-is.
5. **`inputmode="numeric"` für IPv6**: erlaubt Buchstaben a–f und `:`
   nicht — `pattern="[0-9a-fA-F:.]+"` ja, aber Soft-Keyboard zeigt
   numerische Tastatur. Trade-off: IPv4 ist 95% der Anwendungsfälle;
   für IPv6 müssen User auf alphanumerische Tastatur schalten. OK.
6. **`beforeunload`-Prompt**: Browser unterdrücken die Custom-Message
   seit Chrome 51 — User sieht generisches "Changes you made may not be
   saved" oder browser-übersetzte Variante. Konsistente UX, nicht
   anpassbar.
