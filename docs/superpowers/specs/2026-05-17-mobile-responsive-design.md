# Mobile-Responsive UI (Design)

**Datum:** 2026-05-17
**Status:** Spec, zur Plan-Erstellung
**Basis:** Subnetly v1.2 (Multi-App-Subnets, Commit `33467ec`)
**Repo:** `/srv/docker/IP-Planer/`

## 1. Zweck

Die UI ist aktuell nicht mobil bedienbar. Fixe 288-px-Sidebar drückt Content
auf <100 px Restbreite (Smartphone 375 px); die neue 6-Spalten-IP-Liste auf
der Subnetz-Edit-Seite ist auf Mobile unbedienbar; Tabellen schneiden
Spalten ab; Header läuft eng.

Ziel: pragmatischer Mobile-Layer ohne neue JS-Dependency. Tailwind +
CSS-only + Off-Canvas-Sidebar via Checkbox-Hack.

## 2. Scope (in/out)

**In Scope:**
- `base.html` mit Off-Canvas-Sidebar + responsivem Header
- `_sidebar.html` (Content unverändert, evtl. Close-Affordance)
- `assignment_form.html` IP-Liste als Stack-Card auf Mobile
- `application_list.html`, `application_detail.html` Tabellen → Cards
- `pool_detail.html` IPv6-Tabelle → Cards (IPv4-Block-Grid bleibt)
- Header-Anpassungen (Hamburger, Truncation)
- Form-Seiten: Body-Padding responsiv

**Out of Scope:**
- IPv4-Block-Grid-Layout (bleibt Desktop-Density mit horizontalem Scroll
  und Pinch-Zoom auf Mobile)
- Bottom-Tabs / native-App-Feeling
- Dark Mode, Theme-Switch
- Accessibility-Audit über das hinaus, was Off-Canvas automatisch bringt

## 3. Breakpoint-Strategie

Tailwind Standard-Breakpoints:

| Breakpoint | Pixel | Verwendung |
|---|---|---|
| Default (mobile) | <640 | Phone portrait. Hamburger sichtbar, Sidebar off-canvas, Tabellen als Cards. |
| `sm` | ≥640 | Phone landscape / kleines Tablet. Header zeigt zusätzlich Username + Anwendungs-Link. |
| `md` | ≥768 | Tablet portrait und größer. Sidebar permanent sichtbar, Tabellen als echte Spalten-Layouts, IP-Liste als 6-Spalten-Grid. |
| `lg`, `xl` | ≥1024, ≥1280 | wie bisher. |

Wesentlicher Wechsel ist **md** (768 px) — darunter ist alles Mobile-Layout,
darüber wie bisher.

## 4. Off-Canvas-Sidebar (CSS-only)

Pattern: unsichtbare Checkbox vor dem `<header>`; Hamburger-`<label>` togglt;
`peer-checked/drawer:` Tailwind-Modifier auf `<aside>` schiebt sie rein.

### 4.1 `base.html` Skelett

```html
<!doctype html>
<html lang="de">
<head>…viewport meta…</head>
<body class="bg-slate-50 text-slate-900">

<input type="checkbox" id="nav-toggle" class="peer/drawer hidden">

<header class="bg-slate-800 text-slate-100 h-14 px-4 flex items-center gap-3">
  <label for="nav-toggle" class="md:hidden p-2 -ml-2 cursor-pointer" aria-label="Menü öffnen">
    <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
    </svg>
  </label>
  <a href="{% url 'ipam:index' %}" class="font-semibold truncate">
    <span class="md:hidden text-base">Subnetly</span>
    <span class="hidden md:inline text-lg">Subnetly – KNT IP Planer</span>
  </a>
  <div class="ml-auto flex items-center gap-2 md:gap-4">
    {% if user.is_authenticated %}
      <a href="{% url 'ipam:application_list' %}" class="hidden sm:inline text-sm hover:underline">Anwendungen</a>
      <span class="hidden sm:inline text-sm">{{ user.username }}</span>
      <form action="{% url 'logout' %}" method="post" class="inline">{% csrf_token %}
        <button class="bg-slate-700 hover:bg-slate-600 px-3 py-1 rounded text-sm">Logout</button>
      </form>
    {% endif %}
  </div>
</header>

{# Backdrop, only on mobile when drawer open #}
<label for="nav-toggle"
       class="md:hidden hidden peer-checked/drawer:block fixed inset-0 z-30 bg-black/40"
       aria-hidden="true"></label>

<div class="flex" style="min-height: calc(100vh - 3.5rem);">
  {% if user.is_authenticated %}
  <aside class="
    fixed top-14 bottom-0 left-0 z-40 w-72 -translate-x-full
    peer-checked/drawer:translate-x-0 transition-transform duration-200
    bg-white border-r border-slate-200 p-3 overflow-y-auto text-sm
    md:static md:translate-x-0 md:transform-none md:top-0 md:h-auto md:transition-none
  ">
    {% include "_sidebar.html" %}
  </aside>
  {% endif %}
  <main class="flex-1 p-4 md:p-6 overflow-x-auto min-w-0">
    {% block content %}{% endblock %}
  </main>
</div>
</body>
</html>
```

Wichtige Details:
- `<input type="checkbox" id="nav-toggle" class="peer/drawer hidden">` muss
  Sibling zur `<aside>` sein, damit `peer-checked/drawer:` greift. In dieser
  Struktur sind `<input>` und `<aside>` in derselben Eltern-Ebene (body),
  daher OK.
- Sidebar-Höhe auf Mobile: `top-14 bottom-0` (unterhalb der 56 px Header).
  Auf md+: `md:static md:top-0 md:h-auto`.
- `md:transition-none` verhindert Transform-Animation beim Resize über die
  Breakpoint-Grenze.
- Backdrop ist ein zweites `<label for="nav-toggle">` — Click darauf togglt
  die Checkbox = Sidebar schließt.
- `<main class="min-w-0">` ist wichtig, damit lange Inhalte (z.B. das
  IPv4-Block-Grid) den Flex-Container nicht aufblasen.

### 4.2 `_sidebar.html`

Kein inhaltlicher Umbau. Optional: einen kleinen "×"-Close-Button oben rechts,
sichtbar nur auf `<md`, der ebenfalls `<label for="nav-toggle">` ist.

```html
<div class="flex md:hidden justify-end mb-2">
  <label for="nav-toggle" class="cursor-pointer text-slate-400 hover:text-slate-700 text-xl leading-none px-2 -mr-2"
         aria-label="Menü schließen">×</label>
</div>
{# bisheriger Inhalt unverändert #}
```

## 5. IP-Liste als Stack-Card auf Mobile

`assignment_form.html` Grid-Container:

### 5.1 Strategie

- **md+**: Container ist `display: grid` mit 6 Spalten, `<form>` ist
  `display: contents` (transparent für Grid). Wie bisher.
- **<md**: Container ist `display: block`. Jedes `<form>` ist eine
  Card (`block`, eigenes Border, Padding). Innen wieder Stack mit
  Mini-Labels.

Tailwind:
- Grid-Container: `md:grid md:items-center` (kein `grid` ohne `md:`).
- Per-row `<form>`: `block md:contents bg-white border md:border-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0`.
- Zellen: `md:px-2 md:py-1 md:border-t flex justify-between items-center md:block`.
- Mini-Label pro Zelle (Mobile only): `<span class="md:hidden text-xs font-semibold text-slate-500 mr-2">Adresse</span>`.

### 5.2 Vollständige Markup-Skizze

```html
<div class="md:grid md:items-center text-xs"
     style="grid-template-columns: auto auto auto auto auto auto;">

  {# Header row — nur md+ #}
  <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Adresse</div>
  <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Anwendung</div>
  <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Gateway</div>
  <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Label</div>
  <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Notes</div>
  <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Aktion</div>

  {% for row in ip_rows %}
  <form method="post" action="…"
        class="block md:contents bg-white border md:border-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0">
    {% csrf_token %}

    <div class="md:px-2 md:py-1 md:border-t flex justify-between items-center md:block font-mono">
      <span class="md:hidden text-xs font-semibold text-slate-500">Adresse</span>
      {% if row.is_full_mode %}
        <input type="hidden" name="address" value="{{ row.address }}">
        <span>{{ row.address }}</span>
      {% else %}
        <input type="text" name="address" value="{{ row.form.address.value|default:'' }}"
               class="border border-slate-300 rounded px-2 py-1 text-xs w-40">
      {% endif %}
    </div>

    <div class="md:px-2 md:py-1 md:border-t flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Anwendung</span>
      {{ row.form.application }}
    </div>

    <div class="md:px-2 md:py-1 md:border-t flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Gateway</span>
      {{ row.form.is_gateway }}
    </div>

    <div class="md:px-2 md:py-1 md:border-t flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Label</span>
      {{ row.form.label }}
    </div>

    <div class="md:px-2 md:py-1 md:border-t flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Notes</span>
      {{ row.form.notes }}
    </div>

    <div class="md:px-2 md:py-1 md:border-t flex justify-end items-center mt-3 md:mt-0 gap-2 whitespace-nowrap">
      <button type="submit" name="action" value="save"
              class="bg-slate-700 hover:bg-slate-600 text-white px-3 py-2 md:py-1 rounded">
        Speichern
      </button>
      {% if row.ip_assignment %}
      <button type="submit" name="action" value="delete" formnovalidate
              class="text-red-600 hover:underline bg-transparent border-0 cursor-pointer p-2 md:p-0"
              title="IP-Zuordnung löschen">×</button>
      <input type="hidden" name="ip_id" value="{{ row.ip_assignment.id }}">
      {% endif %}
    </div>
  </form>

  {% if row.form.errors %}
  <div class="bg-red-50 px-2 py-2 text-red-700 text-xs md:col-span-6 mb-2 md:mb-0">
    {% for field, errors in row.form.errors.items %}
      <strong>{{ field }}:</strong>
      {% for e in errors %}{{ e }}{% endfor %}
    {% endfor %}
  </div>
  {% endif %}

  {% empty %}
  <div class="px-2 py-4 text-center text-slate-400 italic md:col-span-6">
    Keine IPs zugeordnet.
  </div>
  {% endfor %}

  {% if is_sparse_mode %}
  <form method="post" action="{% url 'ipam:ip_assignment_save' assignment.id %}"
        class="block md:contents bg-slate-50 border md:border-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0">
    {% csrf_token %}
    <div class="md:px-2 md:py-1 md:border-t-2 md:border-slate-300 md:bg-slate-50 flex justify-between items-center md:block">
      <span class="md:hidden text-xs font-semibold text-slate-500">Adresse</span>
      <input type="text" name="address" placeholder="z.B. 10.0.0.1"
             class="border border-slate-300 rounded px-2 py-1 text-xs w-40">
    </div>
    <div class="md:px-2 md:py-1 md:border-t-2 md:border-slate-300 md:bg-slate-50 flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Anwendung</span>
      <select name="application" class="border border-slate-300 rounded px-2 py-1 text-xs">
        <option value="">---</option>
        {% for app in assignment.applications.all %}
        <option value="{{ app.id }}">{{ app.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="md:px-2 md:py-1 md:border-t-2 md:border-slate-300 md:bg-slate-50 flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Gateway</span>
      <input type="checkbox" name="is_gateway">
    </div>
    <div class="md:px-2 md:py-1 md:border-t-2 md:border-slate-300 md:bg-slate-50 flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Label</span>
      <input type="text" name="label" class="border border-slate-300 rounded px-2 py-1 text-xs w-32">
    </div>
    <div class="md:px-2 md:py-1 md:border-t-2 md:border-slate-300 md:bg-slate-50 flex justify-between items-center md:block mt-2 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">Notes</span>
      <input type="text" name="notes" class="border border-slate-300 rounded px-2 py-1 text-xs">
    </div>
    <div class="md:px-2 md:py-1 md:border-t-2 md:border-slate-300 md:bg-slate-50 flex justify-end items-center mt-3 md:mt-0">
      <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 md:py-1 rounded">
        + IP hinzufügen
      </button>
    </div>
  </form>
  {% endif %}
</div>
```

`md:col-span-6` ersetzt das bisherige `style="grid-column: 1 / -1;"` —
Tailwind-native und nur auf md+ aktiv.

### 5.3 Tap-Targets

Buttons werden auf Mobile mit `py-2 px-3` (~ 36 px hoch) statt
`py-1 px-2` (~ 24 px) gerendert. Reicht für Touch.

## 6. Tables → Cards: Anwendungs-Liste und -Detail

### 6.1 Pattern

Ein `<div>`-basiertes Layout, das auf md+ als Grid wie eine Tabelle aussieht.
Header-Row hat `hidden md:grid`, Body-Rows haben `block md:grid` mit
gemeinsamen `md:grid-cols-...`. Auf Mobile sind die Body-Rows Cards mit
gestackter Information.

### 6.2 `application_list.html`

```html
<div class="bg-white rounded shadow overflow-hidden">
  <div class="hidden md:grid grid-cols-[1fr_140px] bg-slate-100 text-sm font-semibold">
    <div class="p-2">Name</div>
    <div class="p-2">Zuweisungen</div>
  </div>
  {% for a in applications %}
  <a href="{% url 'ipam:application_detail' a.id %}"
     class="block md:grid md:grid-cols-[1fr_140px] border-t hover:bg-slate-50 p-3 md:p-0">
    <div class="md:p-2 font-medium md:font-normal">{{ a.name }}</div>
    <div class="md:p-2 text-sm text-slate-600 mt-1 md:mt-0">{{ a.n_assignments }} Zuweisung(en)</div>
  </a>
  {% empty %}
  <div class="p-4 text-center text-slate-500">Noch keine Anwendungen.</div>
  {% endfor %}
</div>
```

Wichtig: der `<a>` umschließt die ganze Row → eine große Tap-Fläche auf Mobile.

### 6.3 `application_detail.html`

```html
<div class="bg-white rounded shadow overflow-hidden">
  <div class="hidden md:grid grid-cols-[200px_200px_1fr_120px] bg-slate-100 text-sm font-semibold">
    <div class="p-2">Pool</div><div class="p-2">CIDR</div>
    <div class="p-2">Notes</div><div class="p-2"></div>
  </div>
  {% for a in assignments %}
  <div class="block md:grid md:grid-cols-[200px_200px_1fr_120px] border-t p-3 md:p-0 hover:bg-slate-50">
    <div class="md:p-2 font-mono flex justify-between md:block">
      <span class="md:hidden text-xs font-semibold text-slate-500">Pool</span>
      <a href="{% url 'ipam:pool_detail' a.pool.id %}" class="underline">{% cidr_tooltip a.pool.cidr %}</a>
    </div>
    <div class="md:p-2 font-mono flex justify-between md:block mt-1 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500">CIDR</span>
      {% cidr_tooltip a.cidr %}
    </div>
    <div class="md:p-2 text-sm text-slate-600 mt-1 md:mt-0">
      <span class="md:hidden text-xs font-semibold text-slate-500 block">Notes</span>
      {{ a.notes|truncatechars:80 }}
    </div>
    <div class="md:p-2 mt-2 md:mt-0 md:text-right">
      <a href="{% url 'ipam:assignment_edit' a.id %}"
         class="inline-block underline text-sm">bearbeiten</a>
    </div>
  </div>
  {% empty %}
  <div class="p-4 text-center text-slate-500">Keine Zuweisungen.</div>
  {% endfor %}
</div>
```

### 6.4 `pool_detail.html` — IPv6-Tabelle

Aktuell `<table>`, wird durch das gleiche Pattern wie 6.3 ersetzt. Spalten
sind CIDR, Anwendungen, Aktion → drei Spalten auf md+, Stack auf Mobile.

## 7. Form-Seiten

Pool-Form, Application-Form, Assignment-New, Login: bereits schmal mit
`max-w-2xl mx-auto` und `w-full`-Inputs.

Eine zentrale Anpassung: `<main class="p-4 md:p-6 ...">` statt fixem `p-6`.
Damit hängt der Form-Inhalt auf Mobile mit 16 px Padding, auf Desktop mit
24 px wie bisher.

Submit-Buttons sind bereits `px-5 py-2` → ausreichend Tap-Target auf Mobile.

## 8. Header-Verhalten

Wie in §4.1 implementiert:
- Hamburger nur `<md`.
- Titel: "Subnetly" auf `<md`, "Subnetly – KNT IP Planer" auf `md+`.
- Username + Anwendungs-Link: `hidden sm:inline` — auf phone-portrait
  (<640 px) ausgeblendet. Beide sind über die Sidebar erreichbar.
- Logout-Button: immer sichtbar.

## 9. Was bleibt unverändert

- `index.html` Pool-Card-Übersicht (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`)
  — schon responsiv.
- `pool_detail.html` IPv4-Block-Grid mit `flex flex-wrap` + Block-Widths in
  rem. Auf Mobile horizontaler Scroll + Pinch-Zoom; bewusst nicht angepasst,
  weil Density-Visualisierung essenziell ist.
- Alle Service- und View-Logiken (Python). Nur Templates ändern sich.

## 10. Tests

- Bestehende Tests laufen weiter (Assertions auf "frei", "hinzufügen",
  Application-Namen etc. bleiben gültig — die Strings sind im Markup
  vorhanden, nur die CSS-Klassen sind anders).
- Ergänzend ein Test, der den Hamburger und das Off-Canvas-Markup
  überprüft:

```python
@pytest.mark.django_db
def test_mobile_navigation_markup_present(auth_client):
    response = auth_client.get("/")
    body = response.content.decode()
    # Checkbox-Toggle für die Off-Canvas-Sidebar
    assert 'id="nav-toggle"' in body
    # Hamburger-Label vorhanden
    assert 'for="nav-toggle"' in body
    # Sidebar hat peer-checked-Klasse
    assert "peer-checked/drawer:translate-x-0" in body
```

Erwartung: bestehende 84 Tests + 1 = **85 Tests**.

## 11. Out of Scope (Mobile v1.1, später)

- IPv4-Block-Grid mit dynamischem Layout je Viewport.
- Bottom-Tabs / native-App-Optik.
- Touch-Gesten (Swipe-to-close für die Drawer).
- ARIA-Live-Regions / detaillierter Screen-Reader-Support über das
  HTML-Native hinaus.
- Dark Mode.
- Visuelle Theme-Tweaks (Farben, Typografie).

## 12. Offene Punkte

Keine — Anforderungen sind vollständig geklärt.
