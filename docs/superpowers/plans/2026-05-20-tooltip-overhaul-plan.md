# Tooltip-Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ersetze CSS-Hover-Tooltips (`hidden group-hover:block absolute bottom-full`) durch HTML-`popover="auto"`-basierte Info-Boxen mit Hover/Focus auf Desktop und Long-Press auf Touch — escaped `overflow:auto`-Clipping und ist WCAG 2.1 SC 1.4.13 konform.

**Architecture:** Drei Template-Tag-Familien (`cidr_info`, `cidr_info_trigger`+`cidr_info_panel`, `free_suggestions_info_panel`) erzeugen Trigger-Attribute (`data-info-trigger`, `aria-describedby`) und ein Top-Layer-`<div popover="auto">`. Ein einziges JS-Modul (`web/ipam/static/ipam/js/popover.js`) bindet Hover (Desktop), Focus (Keyboard) und 500ms-Long-Press (Touch) an alle `[data-info-trigger]`-Elemente und positioniert das Popover viewport-aware. Templates werden in einem Sweep migriert, danach werden die Legacy-Tags entfernt.

**Tech Stack:** Django Template-Tags (`web/ipam/templatetags/cidr_tags.py`), pytest, Vanilla-JS mit `pointerdown`/`pointerup`-Events und HTML-`popover`-API, Tailwind-Klassen via JIT-Scan.

**Spec:** `docs/superpowers/specs/2026-05-20-tooltip-overhaul-design.md`

---

## Repo-Konventionen für diesen Plan

- Tests laufen via `docker compose exec web pytest` oder lokal `pytest` aus `web/`. Wir nutzen im Plan `pytest <pfad>` und gehen davon aus, dass das aus `web/` ausgeführt wird (CWD enthält `manage.py`).
- Alle Commits ohne `--no-verify`. Falls Pre-Commit-Hook fehlschlägt: Issue fixen, neu committen, NICHT `--amend`.
- Frontend wird im Browser geprüft (Spec §9.3) — JS-Tests sind out of scope.

---

## File Structure

**Modified:**
- `web/ipam/templatetags/cidr_tags.py` — neue Tags + entferne Legacy-Tags am Ende
- `web/ipam/tests/test_cidr_tags.py` — neue Tests + entferne Legacy-Tests am Ende
- `web/ipam/templates/base.html` — `<script src="{% static 'ipam/js/popover.js' %}" defer>` einfügen
- `web/ipam/templates/pool_detail.html` — 4 Aufrufstellen migrieren
- `web/ipam/templates/application_detail.html` — 2 Aufrufstellen migrieren
- `web/ipam/templates/assignment_form.html` — IP-Delete-Button `aria-label` ergänzen

**Created:**
- `web/ipam/static/ipam/js/popover.js` — Hover/Focus/Long-Press-Binding + Positionierung
- (App-Static-Dir `web/ipam/static/ipam/js/` wird per Mkdir angelegt; Django-`AppDirectoriesFinder` findet sie automatisch.)

**Deleted (in Task 9):**
- Funktionen `cidr_tooltip`, `cidr_tooltip_panel`, `free_suggestions_tooltip_panel` aus `cidr_tags.py`
- Alle zugehörigen Test-Funktionen aus `test_cidr_tags.py`

---

## Task 1: Test-Helper umstellen + `cidr_info` (self-contained Tag) hinzufügen

Wir behalten die Legacy-Tags vorerst, damit das Repo zwischendurch durchgängig grün bleibt.

**Files:**
- Modify: `web/ipam/tests/test_cidr_tags.py` (Helper erweitern, neue Tests ans Ende)
- Modify: `web/ipam/templatetags/cidr_tags.py` (Counter + neuer Tag)

- [ ] **Step 1.1: Generischen Render-Helper ans Ende der Test-Datei einfügen**

Edit `web/ipam/tests/test_cidr_tags.py` — am ENDE der Datei (nach den existierenden Tests) anfügen:

```python


# ------------------------------------------------------------------
# Generic helper for the new info-popover tags (Task 1+)
# ------------------------------------------------------------------
import re  # noqa: E402

def render_tpl(template_str, ctx=None):
    t = Template("{% load cidr_tags %}" + template_str)
    return t.render(Context(ctx or {}))
```

- [ ] **Step 1.2: Failing test für `cidr_info` schreiben**

Edit `web/ipam/tests/test_cidr_tags.py` — am ENDE anfügen (nach Step 1.1):

```python


def test_cidr_info_renders_trigger_and_panel():
    out = render_tpl("{% cidr_info '10.0.0.0/24' %}")
    assert "10.0.0.0/24" in out
    assert 'data-info-trigger="cidr-info-' in out
    assert 'aria-describedby="cidr-info-' in out
    assert 'popover="auto"' in out
    assert 'role="button"' in out
    assert 'tabindex="0"' in out


def test_cidr_info_panel_contains_lines():
    out = render_tpl("{% cidr_info '10.0.0.0/24' %}")
    assert "Network" in out
    assert "10.0.0.0" in out
    assert "10.0.0.1" in out
    assert "10.0.0.254" in out
    assert "Broadcast" in out


def test_cidr_info_uses_no_legacy_hover_classes():
    out = render_tpl("{% cidr_info '10.0.0.0/24' %}")
    assert "group-hover:" not in out
    assert "pointer-events-none" not in out


def test_cidr_info_invalid_input_renders_text_without_popover():
    out = render_tpl("{% cidr_info 'not-a-cidr' %}")
    assert "not-a-cidr" in out
    assert "popover" not in out
    assert "data-info-trigger" not in out


def test_cidr_info_escapes_user_input():
    out = render_tpl("{% cidr_info '<script>alert(1)</script>' %}")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_cidr_info_panel_ids_unique_across_calls():
    out = render_tpl(
        "{% cidr_info '10.0.0.0/24' %}{% cidr_info '10.0.1.0/24' %}"
    )
    ids = re.findall(r'popover="auto" id="([^"]+)"', out)
    assert len(ids) == 2
    assert ids[0] != ids[1]
```

- [ ] **Step 1.3: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest ipam/tests/test_cidr_tags.py -v -k cidr_info`

Expected: Tests scheitern mit Django-Template-`TemplateSyntaxError: Invalid block tag 'cidr_info'`.

- [ ] **Step 1.4: Counter + `cidr_info` in `cidr_tags.py` implementieren**

Edit `web/ipam/templatetags/cidr_tags.py` — die Datei beginnt mit Import-Block. Nach der Zeile `from netaddr import IPNetwork` (Zeile 5) `import itertools` ergänzen:

```python
import itertools
```

Direkt nach `register = template.Library()` (Zeile 7), VOR der `_tooltip_lines`-Funktion, einfügen:

```python


# Monotonic counter for unique popover ids across a single page render.
# Thread-safe in CPython thanks to the GIL.
_INFO_ID_COUNTER = itertools.count()


def _next_info_id():
    return f"cidr-info-{next(_INFO_ID_COUNTER)}"


def _info_panel_html(lines, panel_id):
    body = "<br>".join(
        f"<span class='inline-block w-28'>{escape(k)}:</span>{escape(v)}"
        for k, v in lines
    )
    return (
        f'<div popover="auto" id="{panel_id}" '
        'class="info-panel bg-slate-900 text-white text-xs font-mono '
        'rounded shadow-lg px-3 py-2 normal-case font-normal m-0 '
        'max-w-xs whitespace-nowrap">'
        f'{body}'
        '</div>'
    )
```

Am ENDE der Datei (nach `free_suggestions_tooltip_panel`) einfügen:

```python


@register.simple_tag
def cidr_info(cidr):
    """Render CIDR as text with a popover info-box (self-contained).

    Trigger and panel both rendered; panel uses HTML popover='auto' for
    top-layer rendering (escapes overflow:auto containers and viewport
    edges). Hover/focus/long-press behavior bound by popover.js.
    """
    lines = _tooltip_lines(cidr)
    cidr_display = escape(str(cidr))
    if lines is None:
        return mark_safe(cidr_display)
    panel_id = _next_info_id()
    trigger = (
        f'<span data-info-trigger="{panel_id}" '
        f'aria-describedby="{panel_id}" '
        f'tabindex="0" role="button" '
        f'class="cursor-help inline-block select-none">'
        f'{cidr_display}'
        f'</span>'
    )
    panel = _info_panel_html(lines, panel_id)
    return mark_safe(trigger + panel)
```

- [ ] **Step 1.5: Tests ausführen, Erfolg bestätigen**

Run: `pytest ipam/tests/test_cidr_tags.py -v -k cidr_info`

Expected: Alle 6 neuen `test_cidr_info_*`-Tests grün.

- [ ] **Step 1.6: Gesamten Test-Lauf prüfen (Regression)**

Run: `pytest ipam/tests/test_cidr_tags.py -v`

Expected: Alle Tests grün — die alten `cidr_tooltip`-Tests funktionieren weiter (wir haben sie nicht angefasst).

- [ ] **Step 1.7: Commit**

```bash
git add web/ipam/templatetags/cidr_tags.py web/ipam/tests/test_cidr_tags.py
git commit -m "$(cat <<'EOF'
feat(tags): add cidr_info template tag with popover="auto"

Self-contained replacement for cidr_tooltip that renders trigger +
panel using the HTML popover API. Legacy cidr_tooltip stays in place
until templates are migrated.
EOF
)"
```

---

## Task 2: `cidr_info_trigger` + `cidr_info_panel` (split-mode für Caller mit eigenem Element)

Für Blöcke im Grid: der Block-Wrapper ist ein `<a>` mit eigener Klasse — wir liefern nur die Attribute zum Spread und das Panel als Sibling.

**Files:**
- Modify: `web/ipam/tests/test_cidr_tags.py`
- Modify: `web/ipam/templatetags/cidr_tags.py`

- [ ] **Step 2.1: Failing tests anfügen**

Edit `web/ipam/tests/test_cidr_tags.py` — am ENDE der Datei anfügen:

```python


def test_cidr_info_trigger_renders_only_attributes():
    out = render_tpl("{% cidr_info_trigger '10.0.0.0/24' 'pid-1' %}")
    assert 'data-info-trigger="pid-1"' in out
    assert 'aria-describedby="pid-1"' in out
    assert "popover" not in out
    assert "<div" not in out
    assert "<span" not in out


def test_cidr_info_trigger_invalid_returns_empty():
    out = render_tpl("{% cidr_info_trigger 'not-a-cidr' 'pid-1' %}")
    assert out.strip() == ""


def test_cidr_info_panel_uses_given_id():
    out = render_tpl("{% cidr_info_panel '10.0.0.0/24' 'my-id' %}")
    assert 'popover="auto"' in out
    assert 'id="my-id"' in out
    assert "Network" in out
    assert "Broadcast" in out


def test_cidr_info_panel_invalid_returns_empty():
    out = render_tpl("{% cidr_info_panel 'not-a-cidr' 'pid-1' %}")
    assert out.strip() == ""


def test_cidr_info_panel_does_not_include_outer_trigger():
    out = render_tpl("{% cidr_info_panel '10.0.0.0/24' 'pid-1' %}")
    # Panel only — no trigger span, no data-info-trigger
    assert "data-info-trigger" not in out
    assert 'role="button"' not in out
```

- [ ] **Step 2.2: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest ipam/tests/test_cidr_tags.py -v -k "cidr_info_trigger or cidr_info_panel"`

Expected: 5 neue Tests scheitern mit `Invalid block tag 'cidr_info_trigger'` / `'cidr_info_panel'`.

- [ ] **Step 2.3: Implementierung anfügen**

Edit `web/ipam/templatetags/cidr_tags.py` — am ENDE der Datei (nach `cidr_info` aus Task 1) anfügen:

```python


@register.simple_tag
def cidr_info_trigger(cidr, panel_id):
    """Render only the trigger attributes for a CIDR popover.

    Caller spreads these attributes onto an existing element (e.g. an
    <a> wrapping a grid block). Caller must also render
    cidr_info_panel with the SAME panel_id as a sibling.

    Returns empty string for invalid CIDR (no popover rendered).
    """
    if _tooltip_lines(cidr) is None:
        return ""
    pid = escape(str(panel_id))
    return mark_safe(
        f'data-info-trigger="{pid}" aria-describedby="{pid}"'
    )


@register.simple_tag
def cidr_info_panel(cidr, panel_id):
    """Render only the popover panel <div> for a CIDR.

    Caller provides panel_id and places the panel as a sibling of the
    element bearing the matching cidr_info_trigger attributes.

    Returns empty string for invalid CIDR.
    """
    lines = _tooltip_lines(cidr)
    if lines is None:
        return ""
    return mark_safe(_info_panel_html(lines, escape(str(panel_id))))
```

- [ ] **Step 2.4: Tests ausführen, Erfolg bestätigen**

Run: `pytest ipam/tests/test_cidr_tags.py -v -k "cidr_info_trigger or cidr_info_panel"`

Expected: Alle 5 neuen Tests grün.

- [ ] **Step 2.5: Vollständiger Test-Lauf der Datei**

Run: `pytest ipam/tests/test_cidr_tags.py -v`

Expected: alle Tests (alt + neu) grün.

- [ ] **Step 2.6: Commit**

```bash
git add web/ipam/templatetags/cidr_tags.py web/ipam/tests/test_cidr_tags.py
git commit -m "$(cat <<'EOF'
feat(tags): add cidr_info_trigger + cidr_info_panel split-mode tags

Split variant for callers that need to attach trigger attributes to an
existing element (e.g. an <a> wrapping a grid block) and render the
panel as a sibling.
EOF
)"
```

---

## Task 3: `free_suggestions_info_panel` (Variant für freie Grid-Blöcke)

**Files:**
- Modify: `web/ipam/tests/test_cidr_tags.py`
- Modify: `web/ipam/templatetags/cidr_tags.py`

- [ ] **Step 3.1: Failing tests anfügen**

Edit `web/ipam/tests/test_cidr_tags.py` — am ENDE anfügen:

```python


def test_free_suggestions_info_panel_renders_list():
    sugs = [
        {"prefix": 23, "network": "45.151.170.0", "size": 512, "cidr": "45.151.170.0/23"},
        {"prefix": 24, "network": "45.151.169.0", "size": 256, "cidr": "45.151.169.0/24"},
    ]
    out = render_tpl(
        "{% free_suggestions_info_panel suggestions 1020 'free-1' %}",
        {"suggestions": sugs},
    )
    assert 'popover="auto"' in out
    assert 'id="free-1"' in out
    assert "Frei" in out
    assert "1020 IPs" in out
    assert "Vorschläge" in out
    assert "/23" in out and "45.151.170.0" in out and "512 IPs" in out
    assert "/24" in out and "45.151.169.0" in out and "256 IPs" in out


def test_free_suggestions_info_panel_empty_returns_empty():
    out = render_tpl(
        "{% free_suggestions_info_panel suggestions 0 'free-1' %}",
        {"suggestions": []},
    )
    assert out.strip() == ""


def test_free_suggestions_info_panel_uses_no_legacy_hover_classes():
    sugs = [{"prefix": 24, "network": "10.0.0.0", "size": 256, "cidr": "10.0.0.0/24"}]
    out = render_tpl(
        "{% free_suggestions_info_panel suggestions 256 'free-1' %}",
        {"suggestions": sugs},
    )
    assert "group-hover:" not in out
    assert "pointer-events-none" not in out
```

- [ ] **Step 3.2: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest ipam/tests/test_cidr_tags.py -v -k free_suggestions_info_panel`

Expected: 3 Tests scheitern mit `Invalid block tag 'free_suggestions_info_panel'`.

- [ ] **Step 3.3: Implementierung anfügen**

Edit `web/ipam/templatetags/cidr_tags.py` — am ENDE der Datei anfügen:

```python


@register.simple_tag
def free_suggestions_info_panel(suggestions, size, panel_id):
    """Popover panel for a free grid block, listing aligned-subnet suggestions.

    Returns empty string if suggestions is empty.
    """
    if not suggestions:
        return ""
    lines = [f"<span class='inline-block w-28'>Frei:</span>{escape(str(size))} IPs"]
    lines.append("<span class='block mt-2 mb-1 text-slate-400'>Vorschläge:</span>")
    for s in suggestions:
        lines.append(
            f"<span class='inline-block w-12 text-slate-300'>/{escape(str(s['prefix']))}</span>"
            f"<span class='inline-block w-44'>ab {escape(str(s['network']))}</span>"
            f"({escape(str(s['size']))} IPs)"
        )
    body = "<br>".join(lines)
    pid = escape(str(panel_id))
    return mark_safe(
        f'<div popover="auto" id="{pid}" '
        'class="info-panel bg-slate-900 text-white text-xs font-mono '
        'rounded shadow-lg px-3 py-2 normal-case font-normal m-0 '
        'max-w-xs whitespace-nowrap">'
        f'{body}'
        '</div>'
    )
```

- [ ] **Step 3.4: Tests ausführen, Erfolg bestätigen**

Run: `pytest ipam/tests/test_cidr_tags.py -v -k free_suggestions_info_panel`

Expected: 3 Tests grün.

- [ ] **Step 3.5: Commit**

```bash
git add web/ipam/templatetags/cidr_tags.py web/ipam/tests/test_cidr_tags.py
git commit -m "$(cat <<'EOF'
feat(tags): add free_suggestions_info_panel popover variant

Same content as the legacy free_suggestions_tooltip_panel, rendered as
a popover="auto" panel with a caller-supplied id.
EOF
)"
```

---

## Task 4: JS-Modul `popover.js` + Einbindung in `base.html`

**Files:**
- Create: `web/ipam/static/ipam/js/popover.js`
- Modify: `web/ipam/templates/base.html` (script-Tag im `<head>`)
- Modify: `web/ipam/tests/test_views.py` (Smoke-Test, dass Script-Tag gerendert wird)

- [ ] **Step 4.1: Verzeichnis anlegen**

Run: `ls web/ipam/static 2>/dev/null || mkdir -p web/ipam/static/ipam/js && ls web/ipam/static/ipam/js`

Expected: Verzeichnis existiert (entweder schon da oder eben angelegt).

- [ ] **Step 4.2: Failing Smoke-Test in test_views.py finden und schreiben**

Run: `grep -n "def test_" web/ipam/tests/test_views.py | head -20`

Expected: Liste bestehender View-Tests. Such ein Pattern für authentifizierte Index-Aufrufe als Vorlage.

Edit `web/ipam/tests/test_views.py` — am ENDE der Datei anfügen:

```python


@pytest.mark.django_db
def test_base_template_includes_popover_js_script(auth_client):
    """Regression guard: popover.js must be wired into base.html so that
    cidr_info popovers actually bind on the client."""
    response = auth_client.get("/")
    body = response.content.decode()
    assert "popover.js" in body
    # Defer attribute keeps page-render unblocked
    assert "defer" in body
```

Falls die Datei den Import `pytest` oder die Fixture `auth_client` noch nicht hat — vor Step 4.3 prüfen:

Run: `grep -n "auth_client\|^import pytest" web/ipam/tests/test_views.py | head -5`

Expected: `auth_client`-Fixture und `import pytest` vorhanden (von früheren Tests). Falls nicht: in `conftest.py` nachschlagen, welche Fixture für eingeloggte User existiert, und stattdessen die nutzen.

- [ ] **Step 4.3: Test ausführen, Fehlschlag bestätigen**

Run: `pytest ipam/tests/test_views.py::test_base_template_includes_popover_js_script -v`

Expected: FAIL mit `assert "popover.js" in body` schlägt fehl (Script-Tag noch nicht im Template).

- [ ] **Step 4.4: `popover.js` schreiben**

Write `web/ipam/static/ipam/js/popover.js`:

```javascript
// Info-popover binding for [data-info-trigger] elements.
// Renders via HTML popover="auto" (top-layer, escapes overflow:auto).
// Desktop: hover (with 150ms delay) + keyboard focus open the popover.
// Touch: 500ms long-press opens it and suppresses the following click
// so a link/button trigger doesn't navigate.
(function () {
  'use strict';

  const HOVER_DELAY_MS = 150;
  const LONGPRESS_MS = 500;
  const GAP_PX = 4;
  const EDGE_PX = 8;
  const SUPPRESS_RESET_MS = 100;

  function positionPopover(trigger, panel) {
    panel.style.position = 'fixed';
    panel.style.margin = '0';
    const r = trigger.getBoundingClientRect();
    let top = r.bottom + GAP_PX;
    let left = r.left;
    const h = panel.offsetHeight;
    const w = panel.offsetWidth;
    if (top + h > window.innerHeight - EDGE_PX) {
      top = r.top - h - GAP_PX;
    }
    if (top < EDGE_PX) {
      top = r.bottom + GAP_PX;
    }
    if (left + w > window.innerWidth - EDGE_PX) {
      left = window.innerWidth - w - EDGE_PX;
    }
    if (left < EDGE_PX) {
      left = EDGE_PX;
    }
    panel.style.top = top + 'px';
    panel.style.left = left + 'px';
  }

  function showPopover(trigger, panel) {
    try {
      if (!panel.matches(':popover-open')) {
        panel.showPopover();
      }
    } catch (e) {
      return;
    }
    positionPopover(trigger, panel);
  }

  function hidePopover(panel) {
    try {
      if (panel.matches(':popover-open')) {
        panel.hidePopover();
      }
    } catch (e) {
      /* ignore */
    }
  }

  function bindTrigger(trigger) {
    const panelId = trigger.dataset.infoTrigger;
    const panel = document.getElementById(panelId);
    if (!panel) return;

    const hoverSupported = window.matchMedia('(hover: hover)').matches;
    let hoverTimer = null;
    let pressTimer = null;
    let suppressClick = false;

    // Desktop hover (with small delay against flicker)
    trigger.addEventListener('mouseenter', function () {
      if (!hoverSupported) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(function () {
        showPopover(trigger, panel);
      }, HOVER_DELAY_MS);
    });
    trigger.addEventListener('mouseleave', function () {
      clearTimeout(hoverTimer);
      hidePopover(panel);
    });

    // Keyboard focus
    trigger.addEventListener('focus', function () {
      showPopover(trigger, panel);
    });
    trigger.addEventListener('blur', function () {
      hidePopover(panel);
    });

    // Touch long-press
    trigger.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'touch') return;
      clearTimeout(pressTimer);
      pressTimer = setTimeout(function () {
        showPopover(trigger, panel);
        suppressClick = true;
        setTimeout(function () { suppressClick = false; }, SUPPRESS_RESET_MS);
      }, LONGPRESS_MS);
    });
    const cancelPress = function () { clearTimeout(pressTimer); };
    trigger.addEventListener('pointerup', cancelPress);
    trigger.addEventListener('pointermove', cancelPress);
    trigger.addEventListener('pointercancel', cancelPress);
    trigger.addEventListener('pointerleave', cancelPress);

    // Click suppression after long-press (capture phase to beat link/button default)
    trigger.addEventListener('click', function (e) {
      if (suppressClick) {
        e.preventDefault();
        e.stopPropagation();
        suppressClick = false;
      }
    }, true);

    // Re-position on resize/scroll while open
    const reposition = function () {
      if (panel.matches(':popover-open')) {
        positionPopover(trigger, panel);
      }
    };
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
  }

  function initInfoPopovers() {
    document.querySelectorAll('[data-info-trigger]').forEach(bindTrigger);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initInfoPopovers);
  } else {
    initInfoPopovers();
  }
})();
```

- [ ] **Step 4.5: Script-Tag in `base.html` einfügen**

Edit `web/ipam/templates/base.html` — Zeile 12 (direkt nach dem `<link rel="stylesheet" href="{% static 'css/tailwind.css' %}">` und vor `</head>`) so erweitern:

Aktuelle Zeilen 7–13:
```html
    {% django_debug as is_debug %}
    {% if is_debug %}
    <script src="https://cdn.tailwindcss.com"></script>
    {% else %}
    <link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
    {% endif %}
</head>
```

Ersetzen durch:
```html
    {% django_debug as is_debug %}
    {% if is_debug %}
    <script src="https://cdn.tailwindcss.com"></script>
    {% else %}
    <link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
    {% endif %}
    <script src="{% static 'ipam/js/popover.js' %}" defer></script>
</head>
```

- [ ] **Step 4.6: Test ausführen, Erfolg bestätigen**

Run: `pytest ipam/tests/test_views.py::test_base_template_includes_popover_js_script -v`

Expected: PASS.

- [ ] **Step 4.7: Voller Test-Lauf**

Run: `pytest ipam/tests -v`

Expected: Alle bisherigen Tests + neuer Smoke-Test grün.

- [ ] **Step 4.8: Manuell prüfen, dass die Datei via Static-Finder gefunden wird**

Run: `python web/manage.py findstatic ipam/js/popover.js`

Expected: Pfad zur Datei wird ausgegeben (z.B. `Found 'ipam/js/popover.js' here: web/ipam/static/ipam/js/popover.js`). Falls nicht: Verzeichnis-Layout (`web/ipam/static/ipam/js/`) prüfen — Django-`AppDirectoriesFinder` braucht das App-Namen-Subverzeichnis.

- [ ] **Step 4.9: Commit**

```bash
git add web/ipam/static/ipam/js/popover.js web/ipam/templates/base.html web/ipam/tests/test_views.py
git commit -m "$(cat <<'EOF'
feat(js): popover.js — hover/focus/long-press info popovers

Binds HTML popover="auto" panels to [data-info-trigger] elements:
- Desktop: 150ms-delay hover + keyboard focus.
- Touch:  500ms long-press, suppresses the trailing click so wrapped
          links/buttons do not navigate.
Viewport-aware fixed positioning with edge clamping.
EOF
)"
```

---

## Task 5: `pool_detail.html` migrieren (4 Aufrufstellen)

**Files:**
- Modify: `web/ipam/templates/pool_detail.html`

Die Datei hat 4 Stellen mit Legacy-Tags:
- Zeile 8: `{% cidr_tooltip pool.cidr %}` (Pool-Header)
- Zeile 29: `title="{{ b.app_names }}"` + Zeile 39: `{% cidr_tooltip_panel b.cidr %}` (belegter Block)
- Zeile 47: `{% free_suggestions_tooltip_panel b.suggestions b.size %}` (freier Block)
- Zeile 66: `{% cidr_tooltip row.cidr %}` (IPv6-Zeile)

- [ ] **Step 5.1: Pool-Header (Zeile 8) migrieren**

Edit `web/ipam/templates/pool_detail.html` — ersetze:

```html
        <p class="text-slate-500 font-mono text-sm">{% cidr_tooltip pool.cidr %}</p>
```

durch:

```html
        <p class="text-slate-500 font-mono text-sm">{% cidr_info pool.cidr %}</p>
```

- [ ] **Step 5.2: Belegten Block (Zeilen 26–40) migrieren**

Edit `web/ipam/templates/pool_detail.html` — ersetze den Block:

```html
            {% if b.kind == "assigned" %}
                <div class="group relative grow rounded p-2 text-xs cursor-pointer hover:opacity-80 transition-opacity"
                     style="flex-basis: {{ b.width_rem }}rem; min-width: max-content; max-width: 100%; background-color: {{ b.color }};"
                     title="{{ b.app_names }}">
                    <a href="{% url 'ipam:assignment_edit' b.obj.id %}"
                       class="block no-underline text-slate-900">
                        {% for name in b.app_list %}
                            <span class="font-semibold block">{{ name }}</span>
                        {% empty %}
                            <span class="font-semibold block">—</span>
                        {% endfor %}
                        <span class="font-mono block">{{ b.cidr }}</span>
                    </a>
                    {% cidr_tooltip_panel b.cidr %}
                </div>
```

durch:

```html
            {% if b.kind == "assigned" %}
                {% with pid="info-blk-"|add:forloop.counter %}
                <div class="relative grow rounded p-2 text-xs cursor-pointer hover:opacity-80 transition-opacity select-none [-webkit-touch-callout:none]"
                     style="flex-basis: {{ b.width_rem }}rem; min-width: max-content; max-width: 100%; background-color: {{ b.color }};">
                    <a href="{% url 'ipam:assignment_edit' b.obj.id %}"
                       class="block no-underline text-slate-900"
                       {% cidr_info_trigger b.cidr pid %}>
                        {% for name in b.app_list %}
                            <span class="font-semibold block">{{ name }}</span>
                        {% empty %}
                            <span class="font-semibold block">—</span>
                        {% endfor %}
                        <span class="font-mono block">{{ b.cidr }}</span>
                    </a>
                    {% cidr_info_panel b.cidr pid %}
                </div>
                {% endwith %}
```

Änderungen im Diff (zur Kontrolle):
- `group relative` → `relative` (kein CSS-`group-hover` mehr)
- Tailwind-Klassen ergänzt: `select-none [-webkit-touch-callout:none]` (iOS-Selektion bei Long-Press verhindern)
- `title="{{ b.app_names }}"` ENTFERNT (redundant; App-Namen sichtbar im Block)
- `{% with pid="info-blk-"|add:forloop.counter %}` … `{% endwith %}` neu drumherum
- `{% cidr_info_trigger b.cidr pid %}` auf das `<a>` (Attribut-Spread)
- `{% cidr_tooltip_panel b.cidr %}` → `{% cidr_info_panel b.cidr pid %}`

- [ ] **Step 5.3: Freien Block (Zeilen 42–48) migrieren**

Edit `web/ipam/templates/pool_detail.html` — ersetze:

```html
            {% else %}
                <a href="{% url 'ipam:assignment_new' pool.id %}{% if b.suggestions %}?cidr={{ b.suggestions.0.cidr }}{% endif %}"
                   class="group relative grow block rounded border border-dashed border-blue-800 bg-blue-50 p-2 text-xs text-blue-500 hover:bg-blue-100 hover:border-blue-900 no-underline"
                   style="flex-basis: {{ b.width_rem }}rem; min-width: max-content; max-width: 100%;">
                    <span class="block">frei</span>
                    <span class="font-mono block">{{ b.size }} IPs</span>
                    {% free_suggestions_tooltip_panel b.suggestions b.size %}
                </a>
            {% endif %}
```

durch:

```html
            {% else %}
                {% with pid="info-free-"|add:forloop.counter %}
                <a href="{% url 'ipam:assignment_new' pool.id %}{% if b.suggestions %}?cidr={{ b.suggestions.0.cidr }}{% endif %}"
                   class="relative grow block rounded border border-dashed border-blue-800 bg-blue-50 p-2 text-xs text-blue-500 hover:bg-blue-100 hover:border-blue-900 no-underline select-none [-webkit-touch-callout:none]"
                   style="flex-basis: {{ b.width_rem }}rem; min-width: max-content; max-width: 100%;"
                   {% if b.suggestions %}{% cidr_info_trigger b.suggestions.0.cidr pid %}{% endif %}>
                    <span class="block">frei</span>
                    <span class="font-mono block">{{ b.size }} IPs</span>
                </a>
                {% if b.suggestions %}{% free_suggestions_info_panel b.suggestions b.size pid %}{% endif %}
                {% endwith %}
            {% endif %}
```

Hinweis: das Free-Suggestions-Panel ist KEIN Cidr-Panel, daher binden wir den Trigger an `b.suggestions.0.cidr` (für `cidr_info_trigger`-Validierung) und rendern stattdessen `free_suggestions_info_panel` als Panel. Beide nutzen dieselbe `pid`. Falls `b.suggestions` leer ist, kein Popover (Tag liefert "").

- [ ] **Step 5.4: IPv6-Zeile (Zeile 66) migrieren**

Edit `web/ipam/templates/pool_detail.html` — ersetze:

```html
                {% cidr_tooltip row.cidr %}
```

durch:

```html
                {% cidr_info row.cidr %}
```

- [ ] **Step 5.5: Verifizieren, dass keine Legacy-Tags mehr in der Datei sind**

Run: `grep -n "cidr_tooltip\|free_suggestions_tooltip_panel\|group-hover\|group relative" web/ipam/templates/pool_detail.html`

Expected: Keine Ausgabe (alle Legacy-Aufrufe ersetzt, kein `group-hover`, kein `group relative` mehr in der Datei).

- [ ] **Step 5.6: Bestehende Tests laufen lassen**

Run: `pytest ipam/tests -v`

Expected: Alle Tests grün. Die bestehenden `test_blocks.py`-Tests prüfen sichtbare Strings im Pool-Detail-View und sollten weiter funktionieren — wir haben nur Markup-Klassen geändert, keine sichtbaren Inhalte.

Falls ein Test scheitert: prüfen, ob die Assertion auf `group-hover` / `cidr_tooltip` / `pointer-events-none` zielt. Diese Assertions sind nicht mehr gültig und werden in Task 9 entfernt — für diesen Task die fehlschlagenden test_blocks-Assertions notieren und im Notes-Feld des Commits erwähnen, NICHT überschreiben.

- [ ] **Step 5.7: Commit**

```bash
git add web/ipam/templates/pool_detail.html
git commit -m "$(cat <<'EOF'
refactor(ui): pool_detail.html uses cidr_info popovers

Migrate four call sites (pool header, assigned block, free block,
IPv6 row) from legacy cidr_tooltip* tags to popover-based cidr_info*.
Drop redundant title= attribute on assigned blocks (app names are
visible inline).

Add select-none + -webkit-touch-callout:none on block triggers to
suppress iOS selection menu during long-press.
EOF
)"
```

---

## Task 6: `application_detail.html` migrieren (2 Aufrufstellen)

**Files:**
- Modify: `web/ipam/templates/application_detail.html`

- [ ] **Step 6.1: Beide Aufrufe ersetzen**

Edit `web/ipam/templates/application_detail.html` — zwei `{% cidr_tooltip … %}`-Aufrufe (Zeilen 28 und 32) jeweils durch `{% cidr_info … %}` ersetzen:

Zeile 28: ersetze

```html
            <a href="{% url 'ipam:pool_detail' a.pool.id %}" class="underline">{% cidr_tooltip a.pool.cidr %}</a>
```

durch

```html
            <a href="{% url 'ipam:pool_detail' a.pool.id %}" class="underline">{% cidr_info a.pool.cidr %}</a>
```

Zeile 32: ersetze

```html
            {% cidr_tooltip a.cidr %}
```

durch

```html
            {% cidr_info a.cidr %}
```

- [ ] **Step 6.2: Verifizieren, dass keine Legacy-Tags mehr in der Datei sind**

Run: `grep -n "cidr_tooltip" web/ipam/templates/application_detail.html`

Expected: Keine Ausgabe.

- [ ] **Step 6.3: Tests laufen lassen**

Run: `pytest ipam/tests -v`

Expected: alle grün (außer Legacy-Klassen-Assertions, die in Task 9 fallen).

- [ ] **Step 6.4: Commit**

```bash
git add web/ipam/templates/application_detail.html
git commit -m "$(cat <<'EOF'
refactor(ui): application_detail.html uses cidr_info popovers
EOF
)"
```

---

## Task 7: ARIA-Label am IP-Delete-Button in `assignment_form.html`

**Files:**
- Modify: `web/ipam/templates/assignment_form.html`

Der Button `×` hat aktuell nur `title="IP-Zuordnung löschen"` — auf Touch unsichtbar und für Screen-Reader inkonsistent.

- [ ] **Step 7.1: `aria-label` ergänzen**

Edit `web/ipam/templates/assignment_form.html` — Zeile 120–125, ersetze:

```html
                    <button type="submit" formnovalidate
                            formaction="{% url 'ipam:ip_assignment_delete' assignment.id row.ip_assignment.id %}"
                            class="text-red-600 hover:underline bg-transparent border-0 cursor-pointer
                                   min-w-[44px] min-h-[44px] flex items-center justify-center
                                   md:min-w-0 md:min-h-0 md:block md:p-0"
                            title="IP-Zuordnung löschen">×</button>
```

durch:

```html
                    <button type="submit" formnovalidate
                            formaction="{% url 'ipam:ip_assignment_delete' assignment.id row.ip_assignment.id %}"
                            class="text-red-600 hover:underline bg-transparent border-0 cursor-pointer
                                   min-w-[44px] min-h-[44px] flex items-center justify-center
                                   md:min-w-0 md:min-h-0 md:block md:p-0"
                            title="IP-Zuordnung löschen"
                            aria-label="IP-Zuordnung löschen">×</button>
```

- [ ] **Step 7.2: Tests laufen lassen**

Run: `pytest ipam/tests -v`

Expected: alle grün.

- [ ] **Step 7.3: Commit**

```bash
git add web/ipam/templates/assignment_form.html
git commit -m "$(cat <<'EOF'
fix(a11y): aria-label on IP-Delete button in assignment_form

title= alone is invisible on touch and read inconsistently by screen
readers. aria-label gives the × button an explicit accessible name.
EOF
)"
```

---

## Task 8: Manuelle Browser-Verifikation (vor Cleanup)

Vor dem Entfernen der Legacy-Tags: prüfen, dass das neue System in Real-Browsern funktioniert.

**Files:** keine — manuelle Verifikation.

- [ ] **Step 8.1: Dev-Server starten (falls noch nicht laufend)**

Run (im Repo-Root): `docker compose up -d`

Expected: Container laufen. URL z.B. `http://localhost:8000` (siehe `docker-compose.yml`).

- [ ] **Step 8.2: Tailwind-Klassen-Build prüfen**

Tailwind wird ins `web`-Image gebuilded (siehe Settings: `_TAILWIND_BUILD = Path("/srv/tailwind/static")`). Bei `DEBUG=True` lädt der Browser stattdessen das CDN-Tailwind (`<script src="https://cdn.tailwindcss.com">` in `base.html`) — das deckt jede Klasse zur Laufzeit ab, also kein Build nötig für DEV-Verifikation.

Falls in Production-Build (DEBUG=False) verifiziert wird: Web-Image neu builden (`docker compose build web`), damit der Tailwind-JIT-Scan die neuen Klassen aus den geänderten Templates erfasst.

- [ ] **Step 8.3: Desktop-Hover prüfen**

In Chrome/Firefox: Pool-Detail-Seite öffnen, Maus über die CIDR-Anzeige im Header bewegen → Popover öffnet sich (mit ~150ms Verzögerung), zeigt Network/Nutzbare-IPs/Broadcast, ist NICHT von oberer Viewport-Kante abgeschnitten.

Maus über ersten Block der ersten Grid-Zeile → Popover unter (oder über, je nach Platz) dem Block; nicht clippt durch den Grid-Container.

Maus weg → Popover schließt.

Tab-Taste zum Block-Trigger fokussieren → Popover öffnet sich via Focus. Esc → schließt.

- [ ] **Step 8.4: Touch-Long-Press prüfen (Chrome DevTools Device Mode)**

In Chrome DevTools: Toggle Device Toolbar (Ctrl/Cmd+Shift+M), Gerät z.B. „iPhone 14 Pro" wählen. Pool-Detail-Seite öffnen.

Kurzer Tap auf belegten Block → navigiert zur Edit-Seite (kein Popover).

Lang drücken (≥ 500ms) auf belegten Block → Popover öffnet sich, Trigger-Click wird unterdrückt (keine Navigation). Erneuter Tap außerhalb → Popover schließt (light-dismiss).

Long-Press auf zweiten Block → erstes Popover schließt automatisch, zweites öffnet.

- [ ] **Step 8.5: Mobile-Echtgerät (optional, falls Zugang vorhanden)**

Auf iOS Safari oder Android Chrome am echten Gerät dieselben Long-Press-/Tap-Szenarien prüfen — bestätigt, dass `-webkit-touch-callout: none` das Selektions-Menü tatsächlich verhindert.

- [ ] **Step 8.6: Bei Defekten: zurück zum entsprechenden Task**

Notiere konkretes Symptom + URL. Springe zurück zum Task, der das fehlerhafte Verhalten eingeführt hat (vermutlich Task 4 oder 5).

Kein Commit in diesem Task — reine Verifikation.

---

## Task 9: Legacy-Tags + Legacy-Tests entfernen

Nach erfolgreicher Verifikation den alten Code löschen.

**Files:**
- Modify: `web/ipam/templatetags/cidr_tags.py`
- Modify: `web/ipam/tests/test_cidr_tags.py`

- [ ] **Step 9.1: Sicherstellen, dass kein Template mehr Legacy-Tags nutzt**

Run: `grep -rn "cidr_tooltip\|free_suggestions_tooltip_panel" web/ipam/templates/`

Expected: Keine Ausgabe. Falls doch: vorher diesen Aufruf migrieren (gleiches Muster wie Task 5/6).

- [ ] **Step 9.2: Legacy-Tags aus `cidr_tags.py` löschen**

Edit `web/ipam/templatetags/cidr_tags.py` — die folgenden drei Funktionen löschen (das sind die @register.simple_tag-Funktionen mit den alten Namen):

- `def cidr_tooltip(cidr)`
- `def cidr_tooltip_panel(cidr)`
- `def free_suggestions_tooltip_panel(suggestions, size)`

Auch die interne Hilfsfunktion `_panel_html(lines)` löschen — die wurde nur von den Legacy-Tags genutzt; das neue System nutzt `_info_panel_html(lines, panel_id)`.

Verifizieren via grep:

Run: `grep -n "_panel_html\|cidr_tooltip\|free_suggestions_tooltip_panel" web/ipam/templatetags/cidr_tags.py`

Expected: Keine Ausgabe.

- [ ] **Step 9.3: Legacy-Tests in `test_cidr_tags.py` löschen**

Edit `web/ipam/tests/test_cidr_tags.py` — die folgenden Test-Funktionen löschen (sie referenzieren die gelöschten Tags und würden jetzt scheitern):

- `def render(cidr)` (alter Helper, von Legacy-Tests genutzt)
- `def test_ipv4_standard_prefix_shows_network_usable_broadcast()`
- `def test_ipv4_slash30_shows_network_usable_broadcast()`
- `def test_ipv4_slash31_omits_usable_and_broadcast()`
- `def test_ipv4_slash32_omits_usable_and_broadcast()`
- `def test_ipv6_shows_network_prefix_and_address_count()`
- `def test_invalid_input_returns_escaped_text_without_crash()`
- `def test_html_escapes_user_input()`
- `def render_panel(cidr)`
- `def test_panel_ipv4_returns_only_inner_span()`
- `def test_panel_ipv6_returns_only_inner_span()`
- `def test_panel_uses_display_none_not_visibility_hidden_to_avoid_layout_overflow()`
- `def test_panel_invalid_returns_empty_string()`
- `def render_free_panel(suggestions, size)`
- `def test_free_suggestions_panel_renders_list()`
- `def test_free_suggestions_panel_empty_returns_empty()`

Die NEU hinzugefügten `test_cidr_info_*`-, `test_cidr_info_trigger_*`-, `test_cidr_info_panel_*`- und `test_free_suggestions_info_panel_*`-Tests sowie der `render_tpl`-Helper aus Task 1/2/3 bleiben.

Verifizieren:

Run: `grep -n "cidr_tooltip\|free_suggestions_tooltip_panel\|def render(\|def render_panel\|def render_free_panel" web/ipam/tests/test_cidr_tags.py`

Expected: Keine Ausgabe.

- [ ] **Step 9.4: Voller Test-Lauf**

Run: `pytest ipam/tests -v`

Expected: Alle Tests grün. Erwartete Test-Anzahl: bestehende ~85 minus 15 Legacy-Tests plus 14 neue (Task 1: 6, Task 2: 5, Task 3: 3) plus 1 Smoke-Test in test_views (Task 4) = ~85 total.

Falls in `test_blocks.py` (oder anderswo) Assertions auf `group-hover` / `cidr_tooltip` / `pointer-events-none` / `title="…"` scheitern: diese Assertions sind durch den Refactor inhaltlich ungültig geworden und müssen ersetzt werden.

Beispiel — falls `test_blocks.py` `assert "group-hover" in html` enthält:

Edit die entsprechende Assertion zu `assert 'data-info-trigger="info-blk-' in html` (prüft, dass ein Popover-Trigger gerendert wurde).

Falls `assert 'title="' in html` (App-Namen-Tooltip): entfernen — das Attribut existiert nicht mehr; stattdessen `assert b.app_names in html` (App-Namen erscheinen sichtbar).

- [ ] **Step 9.5: Commit**

```bash
git add web/ipam/templatetags/cidr_tags.py web/ipam/tests/test_cidr_tags.py
# Plus weitere geänderte Test-Dateien aus Step 9.4 falls nötig:
git status
git add -p   # selektiv weitere Tests übernehmen
git commit -m "$(cat <<'EOF'
chore: remove legacy cidr_tooltip + free_suggestions_tooltip_panel

All template call sites migrated to cidr_info / cidr_info_trigger /
cidr_info_panel / free_suggestions_info_panel (Tasks 5–7). Legacy
tag functions, helper _panel_html, and the corresponding tests are
no longer needed.
EOF
)"
```

---

## Task 10: Endgültiger Sanity-Check

**Files:** keine.

- [ ] **Step 10.1: Repo-weiter Grep auf Legacy-Bezeichner**

Run:
```bash
grep -rn "cidr_tooltip\|free_suggestions_tooltip_panel" web/ docs/ 2>/dev/null | grep -v "docs/superpowers/" | grep -v ".git/"
```

Expected: Keine Ausgabe (außer im neuen Spec/Plan, die per `grep -v` ausgeschlossen sind).

- [ ] **Step 10.2: Repo-weiter Grep auf Legacy-CSS-Patterns**

Run:
```bash
grep -rn "group-hover:block\|pointer-events-none" web/ipam/ 2>/dev/null
```

Expected: Keine Ausgabe.

- [ ] **Step 10.3: Voller Test-Lauf, Erwartung dokumentiert**

Run: `pytest ipam/tests -v`

Expected: Alle Tests grün. Notiere die exakte Anzahl Tests zur Aufnahme in den finalen Status-Report.

- [ ] **Step 10.4: Status-Report**

Im Subagent-/Plan-Execution-Loop: melde den Status mit Test-Anzahl, Anzahl Commits, und „all 4 manual browser scenarios pass".

---

## Notes for the implementer

- **Pre-commit-Hooks NICHT umgehen.** Falls ein Hook fehlschlägt: Issue fixen, neuen Commit machen (NICHT `--amend`).
- **Counter-Reset:** der `itertools.count()` in `cidr_tags.py` ist modulglobal und läuft über Requests hinweg weiter. Das ist beabsichtigt — IDs müssen nur innerhalb eines einzelnen HTML-Dokuments eindeutig sein, was monoton steigend garantiert ist. Keine Race-Condition-Bedenken in CPython (GIL).
- **Tailwind JIT:** Klassen wie `select-none`, `[-webkit-touch-callout:none]`, `[hover:hover]:cursor-help`, `whitespace-nowrap`, `max-w-xs`, `cursor-help` MÜSSEN im Template-Output erscheinen (tun sie, durch unsere Tag-Funktionen) — der JIT-Scanner findet sie im Template/Tag-Code beim Build.
- **Popover-API-Voraussetzungen:** alle Ziel-Browser (Chrome 114+, Safari 17+, Firefox 125+) unterstützen `popover="auto"` und `:popover-open`. Kein Polyfill nötig.
- **Wenn ein Test in einem Task NICHT scheitert wie erwartet (TDD-Sanity):** STOPP, prüfe, ob du den Test im richtigen File schreibst oder ob versehentlich schon Code da ist. Nicht weitermachen, ohne dass „failing → passing" sauber durchlief.
