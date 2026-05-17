# Mobile-Responsive UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subnetly läuft auf Mobile bedienbar — Off-Canvas-Sidebar via Checkbox-Hack, IP-Liste und Tabellen als Stack-Cards auf <md.

**Architecture:** Pure Template + Tailwind. Keine neue JS-Dependency. Eine versteckte `<input type="checkbox">` togglt CSS-Klassen über `peer-checked/drawer:`-Modifier; `<label>`-Elemente sind Hamburger und Backdrop. Datenfluss und Views bleiben unverändert — nur HTML/CSS-Klassen ändern sich.

**Tech Stack:** Django 5 Templates, Tailwind (CDN), pytest-django.

**Test-Befehl:** `docker compose exec web pytest ipam/tests/ -v` (aus `/srv/docker/IP-Planer/`).

**Spec:** `docs/superpowers/specs/2026-05-17-mobile-responsive-design.md`.

**File-Liste:**
- Modify: `web/ipam/templates/base.html` — Off-Canvas-Drawer, responsiver Header, Main-Padding
- Modify: `web/ipam/templates/_sidebar.html` — Close-Button auf Mobile
- Modify: `web/ipam/templates/assignment_form.html` — IP-Liste als Stack-Cards
- Modify: `web/ipam/templates/application_list.html` — Tabelle → Cards
- Modify: `web/ipam/templates/application_detail.html` — Tabelle → Cards
- Modify: `web/ipam/templates/pool_detail.html` — IPv6-Tabelle → Cards (IPv4 bleibt)
- Modify: `web/ipam/tests/test_views.py` — neuer Test für Mobile-Markup

---

## Task 1: base.html — Off-Canvas-Sidebar + responsiver Header

**Files:**
- Modify: `web/ipam/templates/base.html`
- Test: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Failing Test schreiben**

Am Ende von `web/ipam/tests/test_views.py` anhängen:

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

- [ ] **Step 2: Test verifiziert FAIL**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_mobile_navigation_markup_present -v
```

Erwartet: FAIL (nav-toggle nicht im aktuellen Template).

- [ ] **Step 3: base.html neu schreiben**

Ersetze `/srv/docker/IP-Planer/web/ipam/templates/base.html` vollständig durch:

```html
<!doctype html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Subnetly{% endblock %} – KNT IP Planer</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900">

<input type="checkbox" id="nav-toggle" class="peer/drawer hidden">

<header class="bg-slate-800 text-slate-100 h-14 px-4 flex items-center gap-3">
    {% if user.is_authenticated %}
    <label for="nav-toggle" class="md:hidden p-2 -ml-2 cursor-pointer" aria-label="Menü öffnen">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
    </label>
    {% endif %}
    <a href="{% url 'ipam:index' %}" class="font-semibold truncate">
        <span class="md:hidden text-base">Subnetly</span>
        <span class="hidden md:inline text-lg">Subnetly – KNT IP Planer</span>
    </a>
    <div class="ml-auto flex items-center gap-2 md:gap-4">
        {% if user.is_authenticated %}
            <a href="{% url 'ipam:application_list' %}" class="hidden sm:inline text-sm hover:underline">Anwendungen</a>
            <span class="hidden sm:inline text-sm">{{ user.username }}</span>
            <form action="{% url 'logout' %}" method="post" class="inline">
                {% csrf_token %}
                <button class="bg-slate-700 hover:bg-slate-600 px-3 py-1 rounded text-sm">Logout</button>
            </form>
        {% endif %}
    </div>
</header>

{% if user.is_authenticated %}
{# Backdrop, only on mobile when drawer open #}
<label for="nav-toggle"
       class="md:hidden hidden peer-checked/drawer:block fixed inset-0 z-30 bg-black/40"
       aria-hidden="true"></label>
{% endif %}

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

Wichtig:
- Header-Höhe ist jetzt fix `h-14` (3.5 rem = 56 px). Sidebar startet darunter auf Mobile (`top-14`).
- Auf md+ ist die Sidebar `md:static md:top-0 md:h-auto` — sie nimmt wieder ihren normalen Platz im Flex-Container ein.
- Backdrop ist ein zweites `<label for="nav-toggle">` — Klick togglt die Checkbox = Sidebar schließt.
- Main hat `min-w-0`, damit lange Inhalte (Block-Grid) den Flex-Container nicht aufblasen.
- `p-4 md:p-6` ersetzt das alte `p-6` — auf Mobile 16 px Padding.

- [ ] **Step 4: Test verifiziert PASS**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_mobile_navigation_markup_present -v
```

Erwartet: PASS.

- [ ] **Step 5: Volltest läuft weiter**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -10
```

Erwartet: 85 passed (84 + 1 neu) / 0 failed.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/templates/base.html web/ipam/tests/test_views.py
git commit -m "feat(ui): off-canvas sidebar via checkbox-hack + responsive header"
```

---

## Task 2: _sidebar.html — Close-Button auf Mobile

**Files:**
- Modify: `web/ipam/templates/_sidebar.html`

- [ ] **Step 1: Close-Button am Anfang einfügen**

Füge in `/srv/docker/IP-Planer/web/ipam/templates/_sidebar.html` als ersten Block VOR dem bestehenden Inhalt ein:

```html
<div class="flex md:hidden justify-end mb-2">
    <label for="nav-toggle"
           class="cursor-pointer text-slate-400 hover:text-slate-700 text-2xl leading-none px-2 -mr-2"
           aria-label="Menü schließen">×</label>
</div>
```

Der Rest der Datei bleibt unverändert.

- [ ] **Step 2: Volltest**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -5
```

Erwartet: 85 passed / 0 failed.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/templates/_sidebar.html
git commit -m "feat(ui): mobile close button in sidebar"
```

---

## Task 3: assignment_form.html — IP-Liste als Stack-Cards auf Mobile

**Files:**
- Modify: `web/ipam/templates/assignment_form.html`

- [ ] **Step 1: Template komplett ersetzen**

Ersetze `/srv/docker/IP-Planer/web/ipam/templates/assignment_form.html` vollständig durch:

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

    <div class="md:bg-white md:border md:border-slate-200 md:rounded md:overflow-x-auto">
        <div class="md:grid md:items-center text-xs"
             style="grid-template-columns: auto auto auto auto auto auto;">

            {# Header row — md+ only #}
            <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Adresse</div>
            <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Anwendung</div>
            <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Gateway</div>
            <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Label</div>
            <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Notes</div>
            <div class="hidden md:block bg-slate-100 text-slate-600 px-2 py-2 font-semibold">Aktion</div>

            {% for row in ip_rows %}
            <form method="post" action="{% url 'ipam:ip_assignment_save' assignment.id %}"
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
    </div>
    {% endif %}
    {% endif %}
</div>
{% endblock %}
```

Key changes:
- Container wechselt zwischen `md:bg-white md:border md:rounded md:overflow-x-auto` (Card-wrapper auf Desktop) und leerer Hülle auf Mobile (jedes Form wird selbst zur Card).
- Header-Row hat `hidden md:block` — versteckt auf Mobile.
- Per-Row-Form: `block md:contents bg-white border md:border-0 rounded md:rounded-none p-3 md:p-0 mb-2 md:mb-0` — Mobile: Card-Style; Desktop: contents (transparent fürs Grid).
- Jede Zelle: `md:px-2 md:py-1 md:border-t flex justify-between items-center md:block` — Mobile: Label+Wert nebeneinander; Desktop: Grid-Zelle.
- Mini-Labels: `<span class="md:hidden text-xs font-semibold text-slate-500">Adresse</span>` — nur auf Mobile sichtbar.
- Buttons: `px-3 py-2 md:py-1` — größere Tap-Targets auf Mobile.
- Spalten-spannende Reihen (Error, Empty): `md:col-span-6` statt inline-style.

- [ ] **Step 2: Verifikation**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v -k "renders_full_iplist or renders_sparse_iplist or add_row_for_empty"
```

Erwartet: alle 3 PASS — die Substring-Asserts ("hinzufügen", "IP-Zuordnung", "217.61.249.X") bleiben gültig.

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -5
```

Erwartet: 85 passed / 0 failed.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/templates/assignment_form.html
git commit -m "feat(ui): IP list as stacked cards on mobile (md:contents grid)"
```

---

## Task 4: application_list.html — Tabelle → Card-Layout

**Files:**
- Modify: `web/ipam/templates/application_list.html`

- [ ] **Step 1: Template ersetzen**

Ersetze `/srv/docker/IP-Planer/web/ipam/templates/application_list.html` vollständig durch:

```html
{% extends "base.html" %}
{% block title %}Anwendungen{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-4 gap-2">
    <h1 class="text-2xl font-semibold">Anwendungen</h1>
    <a href="{% url 'ipam:application_new' %}"
       class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium whitespace-nowrap">
        + Anwendung
    </a>
</div>
<div class="bg-white rounded shadow overflow-hidden">
    <div class="hidden md:grid grid-cols-[1fr_140px] bg-slate-100 text-sm font-semibold">
        <div class="p-2">Name</div>
        <div class="p-2">Zuweisungen</div>
    </div>
    {% for a in applications %}
    <a href="{% url 'ipam:application_detail' a.id %}"
       class="block md:grid md:grid-cols-[1fr_140px] border-t hover:bg-slate-50 p-3 md:p-0 text-sm">
        <div class="md:p-2 font-medium md:font-normal underline">{{ a.name }}</div>
        <div class="md:p-2 text-slate-600 mt-1 md:mt-0">{{ a.n_assignments }} Zuweisung(en)</div>
    </a>
    {% empty %}
    <div class="p-4 text-center text-slate-500">Noch keine Anwendungen.</div>
    {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 2: Verifikation**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_application_list_shows_count -v
```

Erwartet: PASS (die Asserts "BINSS" und "2" bleiben gültig).

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -5
```

Erwartet: 85 passed / 0 failed.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/templates/application_list.html
git commit -m "feat(ui): application list as responsive card layout"
```

---

## Task 5: application_detail.html — Tabelle → Card-Layout

**Files:**
- Modify: `web/ipam/templates/application_detail.html`

- [ ] **Step 1: Template ersetzen**

Ersetze `/srv/docker/IP-Planer/web/ipam/templates/application_detail.html` vollständig durch:

```html
{% extends "base.html" %}
{% load cidr_tags %}
{% block title %}{{ application.name }}{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-1 gap-2">
    <h1 class="text-2xl font-semibold truncate">{{ application.name }}</h1>
    <a href="{% url 'ipam:application_edit' application.id %}"
       class="bg-slate-200 hover:bg-slate-300 text-slate-900 px-3 py-1 rounded text-sm whitespace-nowrap">
        Bearbeiten
    </a>
</div>
{% if application.notes %}<p class="text-slate-700 mb-3">{{ application.notes }}</p>{% endif %}

<div class="bg-white rounded shadow overflow-hidden text-sm">
    <div class="hidden md:grid grid-cols-[200px_200px_1fr_120px] bg-slate-100 font-semibold">
        <div class="p-2">Pool</div>
        <div class="p-2">CIDR</div>
        <div class="p-2">Notes</div>
        <div class="p-2"></div>
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
        <div class="md:p-2 text-slate-600 mt-1 md:mt-0">
            <span class="md:hidden text-xs font-semibold text-slate-500 block">Notes</span>
            {{ a.notes|truncatechars:80 }}
        </div>
        <div class="md:p-2 mt-2 md:mt-0 md:text-right">
            <a href="{% url 'ipam:assignment_edit' a.id %}"
               class="inline-block underline">bearbeiten</a>
        </div>
    </div>
    {% empty %}
    <div class="p-4 text-center text-slate-500">Keine Zuweisungen.</div>
    {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 2: Verifikation**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_application_detail_lists_assignments -v
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -5
```

Erwartet: PASS / 85 passed.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/templates/application_detail.html
git commit -m "feat(ui): application detail as responsive card layout"
```

---

## Task 6: pool_detail.html — IPv6-Tabelle → Card-Layout

**Files:**
- Modify: `web/ipam/templates/pool_detail.html`

- [ ] **Step 1: IPv6-Tabellen-Block ersetzen**

In `/srv/docker/IP-Planer/web/ipam/templates/pool_detail.html`, finde den Block `{% else %}...{% endif %}` ab Zeile 50 (der IPv6-Branch mit `<table>`). Ersetze den gesamten Block durch:

```html
{% else %}
    <div class="bg-white rounded shadow overflow-hidden text-sm">
        <div class="hidden md:grid grid-cols-[1fr_1fr_120px] bg-slate-100 text-slate-600 font-semibold">
            <div class="px-3 py-2">CIDR</div>
            <div class="px-3 py-2">Anwendungen</div>
            <div class="px-3 py-2">Aktion</div>
        </div>
        {% for row in v6_rows %}
        <div class="block md:grid md:grid-cols-[1fr_1fr_120px] border-t p-3 md:p-0 hover:bg-slate-50">
            <div class="md:px-3 md:py-2 font-mono flex justify-between md:block">
                <span class="md:hidden text-xs font-semibold text-slate-500">CIDR</span>
                {% cidr_tooltip row.cidr %}
            </div>
            <div class="md:px-3 md:py-2 flex justify-between md:block mt-1 md:mt-0">
                <span class="md:hidden text-xs font-semibold text-slate-500">Anwendungen</span>
                <span>{{ row.app_names }}</span>
            </div>
            <div class="md:px-3 md:py-2 mt-2 md:mt-0">
                <a href="{% url 'ipam:assignment_edit' row.id %}"
                   class="text-blue-600 hover:underline text-xs">Bearbeiten</a>
            </div>
        </div>
        {% empty %}
        <div class="px-3 py-4 text-center text-slate-400 italic">
            Keine Zuweisungen vorhanden.
        </div>
        {% endfor %}
    </div>
{% endif %}
```

Die IPv4-Branch (`{% if pool.ip_version == 4 %}...`) bleibt vollständig unverändert.

- [ ] **Step 2: Verifikation**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v -k "pool_detail"
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -5
```

Erwartet: PASS / 85 passed.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/templates/pool_detail.html
git commit -m "feat(ui): IPv6 pool detail as responsive card layout"
```

---

## Task 7: End-to-end Smoke + Doku

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Volltest**

```bash
docker compose exec web pytest ipam/tests/ -v 2>&1 | tail -10
```

Erwartet: ALL 85 PASS.

- [ ] **Step 2: Mobile-Smoke via curl**

```bash
docker compose exec web python manage.py shell <<'PYEOF'
from django.conf import settings
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ["testserver"]
from django.test import Client
from django.contrib.auth import get_user_model
su = get_user_model().objects.filter(is_superuser=True).first()
c = Client()
c.force_login(su)
for url in ["/", "/anwendungen/", "/pool/1/", "/assignment/1/edit/"]:
    r = c.get(url)
    body = r.content.decode()
    has_hamburger = 'for="nav-toggle"' in body
    has_drawer = "peer-checked/drawer:translate-x-0" in body
    print(f"{url:35s} -> {r.status_code}  hamburger:{has_hamburger}  drawer-cls:{has_drawer}")
PYEOF
```

Erwartet: alle 4 URLs `200`, alle haben `hamburger:True` und `drawer-cls:True`.

- [ ] **Step 3: CLAUDE.md-Notiz**

Öffne `/srv/docker/IP-Planer/CLAUDE.md` und ergänze am Ende:

```markdown
- Mobile-Layout: Off-Canvas-Sidebar via Checkbox-Hack (`<input id="nav-toggle">`
  + `peer-checked/drawer:`-Modifier). Breakpoint `md` (768 px). Tables
  (Anwendungs-Liste/-Detail, IPv6 pool) und IP-Liste werden auf <md zu
  Stack-Cards mit Mini-Labels. IPv4-Block-Grid bleibt density-Visualisierung
  mit horizontalem Scroll.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note mobile-responsive layout pattern in CLAUDE.md"
```

- [ ] **Step 5: Container neustarten (Production)**

Da gunicorn beim Start Python-Module lädt — nicht Templates. Templates werden bei jedem Request frisch geladen, also kein Restart nötig. Smoke-Test im Browser von der Live-URL.

(Operator-Schritt: in einem Mobile-Browser `https://subnetly.kntinternet.de/` öffnen → Hamburger sichtbar, Sidebar schiebt rein, Tap auf einen Pool → Block-Grid horizontal scrollbar, Tap auf Subnetz → IP-Liste als Cards.)

---

## Done.

**Erwartete Endzustände:**
- 7 Tasks abgeschlossen.
- 85 Tests grün (84 + 1 für Mobile-Markup).
- Mobile bedienbar: Off-Canvas-Sidebar, IP-Liste als Cards, Tabellen als Cards.
- Keine neue JS-Dependency.
- Desktop-Layout unverändert.
