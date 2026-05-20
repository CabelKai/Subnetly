# Tooltip-Overhaul — Touch-fähige Info-Popover (Design)

**Datum:** 2026-05-20
**Status:** Spec, zur Plan-Erstellung
**Basis:** Subnetly Stand Commit `fd6eebe`
**Repo:** `/srv/docker/IP-Planer/`

## 1. Zweck

Die CSS-Hover-Tooltips (`hidden group-hover:block absolute bottom-full`)
verletzen WCAG 2.1 SC 1.4.13 (Content on Hover or Focus) und sind auf
Touch-Geräten nicht bedienbar. Zwei beobachtete Symptome:

- **Mobile:** Hover existiert auf Touch nicht. Tap zeigt Tooltip kurz,
  navigiert aber gleichzeitig zur Edit-Seite. `pointer-events-none` macht
  das Tooltip-Panel zudem nicht hoverbar.
- **Desktop:** Tooltips sind `bottom-full` positioniert (oberhalb).
  Die obere Leiste des Block-Grids (Pool-CIDR sowie erste Zeile der
  Blöcke) clippt. Im Block-Grid zwingt `overflow-x-auto` per CSS-Spec
  `overflow-y` ebenfalls auf `auto` → vertikales Clipping.

Ziel: einheitliches Info-Popover-System, das auf Desktop per Hover und
Tastatur, auf Touch per Long-Press öffnet, im Top-Layer rendert (escaped
alle `overflow:auto`-Container und Viewport-Kanten) und WCAG-konform
dismissable/hoverable/persistent ist.

## 2. Scope (in/out)

**In Scope:**
- Neue Template-Tags in `web/ipam/templatetags/cidr_tags.py`
  (`cidr_info`, `cidr_info_trigger`, `cidr_info_panel`,
  `free_suggestions_info_panel`).
- Neue Datei `web/static_src/js/popover.js` mit Hover/Long-Press-Bindung
  und viewport-aware Positionierung.
- `<script>`-Einbindung in `web/ipam/templates/base.html`.
- Migration aller Aufrufstellen in `pool_detail.html` und
  `application_detail.html`.
- Entfernung des redundanten `title=`-Attributs auf belegten Blöcken.
- ARIA-Hardening für IP-Delete-`×` in `assignment_form.html`.
- Tests in `web/ipam/tests/test_cidr_tags.py` umbenennen/erweitern.

**Out of Scope:**
- Toast-Auto-Dismiss in `base.html` (WCAG 2.2.1) — separater Spec.
- Visuelle Theme-Tweaks am Popover (Farben, Typografie bleiben wie
  jetzt: `bg-slate-900 text-white text-xs font-mono`).
- IPv4-Block-Grid-Layout selbst (`flex flex-wrap`, `overflow-x-auto`
  bleiben — das neue Popover escaped sauber).
- Mobile-Layout-Anpassungen jenseits der Popover-Mechanik.
- Refactoring nicht betroffener Templates oder Services.

## 3. Browser-Anforderungen

| Feature | Mindest-Browser | Stand |
|---|---|---|
| HTML `popover="auto"` | Chrome 114, Safari 17, Firefox 125 | seit 2024 stabil, in 2026 universell verfügbar |
| `matchMedia('(hover: hover)')` | seit ~2018 | universell |
| `pointerdown`/`pointerup` Events | seit ~2017 | universell |

Keine CSS-Anchor-Positioning-Abhängigkeit (Firefox-Lag) — Positionierung
läuft via JS.

## 4. Architektur

### 4.1 Modul-Grenzen

```
web/ipam/templatetags/cidr_tags.py     [REWRITE]
  ├─ cidr_info(cidr)                   — Trigger + Panel, self-contained
  ├─ cidr_info_trigger(cidr, panel_id) — nur Attribute (für externe <a>)
  ├─ cidr_info_panel(cidr, panel_id)   — nur das <div popover>
  ├─ free_suggestions_info_panel(suggestions, size, panel_id)
  └─ _panel_html(lines, panel_id)      — interner Renderer

web/static_src/js/popover.js           [NEU]
  ├─ initInfoPopovers()                — DOMContentLoaded-Init
  ├─ bindTrigger(trigger, panel)       — hover/focus/long-press
  └─ positionPopover(trigger, panel)   — fixed top/left, flip-if-overflow

web/ipam/templates/base.html           [EDIT]
  └─ <script src="{% static 'js/popover.js' %}" defer></script>

web/ipam/templates/pool_detail.html    [EDIT — 4 Tag-Aufrufe ersetzen]
web/ipam/templates/application_detail.html [EDIT — 2 Tag-Aufrufe ersetzen]
web/ipam/templates/assignment_form.html [EDIT — IP-Delete ARIA]

web/ipam/tests/test_cidr_tags.py       [REWRITE — neue Assertions]
```

Verantwortlichkeiten sauber getrennt:
- **Template-Tag:** Markup-Generierung, deterministische IDs.
- **JS-Modul:** Interaktions-Binding und Positionierung.
- **Browser:** Top-Layer-Rendering, Light-Dismiss, Esc-Handling.

### 4.2 Daten-/Event-Fluss

```
Template (Server)            Browser (Client)              User Action
───────────────────────────────────────────────────────────────────────
{% cidr_info_trigger %}  →   <a data-info-trigger="x" …>
                              aria-describedby="x">
{% cidr_info_panel %}    →   <div popover="auto" id="x" …>

popover.js  initInfoPopovers()
  • querySelectorAll('[data-info-trigger]')
  • pro Trigger:
      desktop  → mouseenter (150ms delay) → show + position
                 mouseleave → hide
                 focus      → show + position
                 blur       → hide
      touch    → pointerdown → 500ms timer → show + position
                                          → setze suppressClick=true
                 pointerup/move/cancel → clearTimeout
                 click (capture) → if suppressClick: preventDefault+stopProp
                                   reset suppressClick
  • Esc / outside-click  → automatisch (popover="auto")
```

### 4.3 Positionierungs-Algorithmus

```
positionPopover(trigger, panel):
  rect = trigger.getBoundingClientRect()
  panel.style.position = 'fixed'
  panel.style.margin = '0'

  // Default: unter dem Trigger, linksbündig
  let top  = rect.bottom + 4
  let left = rect.left

  // Flip nach oben, wenn unten kein Platz
  const panelH = panel.offsetHeight
  if (top + panelH > window.innerHeight - 8) {
    top = rect.top - panelH - 4
  }
  // Wenn auch oben kein Platz → bleibe unten, akzeptiere Scroll
  if (top < 8) top = rect.bottom + 4

  // Horizontal in Viewport halten
  const panelW = panel.offsetWidth
  if (left + panelW > window.innerWidth - 8) {
    left = window.innerWidth - panelW - 8
  }
  if (left < 8) left = 8

  panel.style.top  = `${top}px`
  panel.style.left = `${left}px`
```

Aufgerufen direkt nach `showPopover()`, weil offsetHeight/offsetWidth
erst nach dem Mount korrekte Werte liefern.

## 5. Template-Tags — Markup-Spezifikation

### 5.1 `cidr_info(cidr)` — self-contained

```html
<span data-info-trigger="cidr-info-{N}"
      aria-describedby="cidr-info-{N}"
      tabindex="0" role="button"
      class="cursor-help inline-block select-none">
  10.0.0.0/24
</span>
<div popover="auto" id="cidr-info-{N}"
     class="info-panel bg-slate-900 text-white text-xs font-mono
            rounded shadow-lg px-3 py-2 normal-case font-normal m-0
            max-w-xs whitespace-nowrap">
  <span class="inline-block w-28">Network:</span>10.0.0.0<br>
  <span class="inline-block w-28">Nutzbare IPs:</span>10.0.0.1 – 10.0.0.254<br>
  <span class="inline-block w-28">Broadcast:</span>10.0.0.255
</div>
```

`{N}` wird aus einem modul-globalen `itertools.count()` gezogen
(thread-safe in CPython dank GIL). Monoton steigender Counter, der über
Requests hinweg weiterläuft — irrelevant, weil IDs nur innerhalb eines
einzelnen HTML-Dokuments eindeutig sein müssen, was durch den
monotonen Wert garantiert ist.

### 5.2 `cidr_info_trigger(cidr, panel_id)` — Attribute-only

Rendert (zum Spread in ein bestehendes Element):

```
data-info-trigger="info-blk-1" aria-describedby="info-blk-1"
```

Setzt **kein** `tabindex`/`role` — das Caller-Element ist typischerweise
ein `<a>` mit eigenem Tabindex.

### 5.3 `cidr_info_panel(cidr, panel_id)` — Panel-only

Rendert nur das `<div popover="auto" id="…">…</div>`. Caller bestimmt
`panel_id` und positioniert das Panel als Sibling des Triggers.

### 5.4 `free_suggestions_info_panel(suggestions, size, panel_id)`

Analoge Panel-Markup, Inhalt aus existierender Logik
(`free_suggestions_tooltip_panel` in `cidr_tags.py:78`).

## 6. Template-Migration

### 6.1 `pool_detail.html`

**Pool-Header (Zeile 8):**
```diff
- <p class="text-slate-500 font-mono text-sm">{% cidr_tooltip pool.cidr %}</p>
+ <p class="text-slate-500 font-mono text-sm">{% cidr_info pool.cidr %}</p>
```

**Belegter Block (Zeilen 26–40):**
```diff
{% if b.kind == "assigned" %}
+ {% with pid="info-blk-"|add:forloop.counter %}
- <div class="group relative grow rounded p-2 text-xs cursor-pointer hover:opacity-80 transition-opacity"
+ <div class="relative grow rounded p-2 text-xs cursor-pointer hover:opacity-80 transition-opacity select-none [-webkit-touch-callout:none]"
       style="flex-basis: {{ b.width_rem }}rem; min-width: max-content; max-width: 100%; background-color: {{ b.color }};"
-      title="{{ b.app_names }}">
+      >
      <a href="{% url 'ipam:assignment_edit' b.obj.id %}"
-        class="block no-underline text-slate-900">
+        class="block no-underline text-slate-900"
+        {% cidr_info_trigger b.cidr pid %}>
          {% for name in b.app_list %}
              <span class="font-semibold block">{{ name }}</span>
          {% empty %}
              <span class="font-semibold block">—</span>
          {% endfor %}
          <span class="font-mono block">{{ b.cidr }}</span>
      </a>
-     {% cidr_tooltip_panel b.cidr %}
+     {% cidr_info_panel b.cidr pid %}
  </div>
+ {% endwith %}
```

Geändert:
- `title="{{ b.app_names }}"` entfernt — App-Namen stehen sichtbar im
  Block, native Browser-Tooltip stört (iOS-Callout).
- `group relative` → `relative` (kein CSS-Hover mehr).
- `select-none [-webkit-touch-callout:none]` verhindert iOS-Selektions-
  /Kopier-Menü bei Long-Press.

**Freier Block (Zeilen 42–48):** analog, `cidr_info_trigger` auf `<a>`,
`free_suggestions_info_panel` daneben mit gleichem `pid`-Pattern.

**IPv6-Zeile (Zeile 66):**
```diff
- {% cidr_tooltip row.cidr %}
+ {% cidr_info row.cidr %}
```

### 6.2 `application_detail.html`

Beide `{% cidr_tooltip … %}`-Aufrufe → `{% cidr_info … %}`.

### 6.3 `assignment_form.html`

IP-Delete-`×`-Button (Zeile 122–126):
```diff
  <button type="submit" name="action" value="delete" formnovalidate
          class="text-red-600 hover:underline bg-transparent border-0 cursor-pointer
                 min-w-[44px] min-h-[44px] flex items-center justify-center
                 md:min-w-0 md:min-h-0 md:block"
-         title="IP-Zuordnung löschen">×</button>
+         title="IP-Zuordnung löschen"
+         aria-label="IP-Zuordnung löschen">×</button>
```

`title` bleibt für Desktop-Hover-Hinweis; `aria-label` ergänzt für
Screen-Reader und Touch-Klarheit.

## 7. Interaktions-Verhalten

### 7.1 Desktop (Maus + Tastatur)

| Trigger | Aktion |
|---|---|
| `mouseenter` (mit 150ms Delay) | Popover öffnen, positionieren |
| `mouseleave` | Popover schließen |
| `focus` | Popover öffnen, positionieren |
| `blur` | Popover schließen |
| `Esc` während Popover offen | Popover schließen (nativ) |
| Klick auf Trigger-Link | Standard-Navigation (Popover schließt durch Page-Wechsel) |

Hover-Delay verhindert Flicker bei Maus-Bewegung über mehrere Trigger.
Popover bleibt offen, solange Maus innerhalb Trigger ODER Panel
(WCAG „hoverable" — kein `pointer-events-none`).

### 7.2 Touch

| Trigger | Aktion |
|---|---|
| `pointerdown` (touch) | 500ms-Timer starten |
| `pointerup`/`pointermove`/`pointercancel`/`pointerleave` vor Ablauf | Timer abbrechen → normales Tap → Link-Navigation |
| Timer läuft ab | Popover öffnen, positionieren; `suppressClick = true` |
| `click` nach Long-Press | abgefangen via Capture-Phase, `preventDefault`+`stopProp`; `suppressClick` wird im Handler zurückgesetzt |
| Kein `click` nach Long-Press (User tippt anderswo) | `suppressClick` wird 100ms nach Popover-Open via `setTimeout` zurückgesetzt — Fallback, damit ein späterer normaler Tap auf denselben Trigger wieder navigiert |
| Tap außerhalb | Popover schließen (nativ, `popover="auto"`) |
| Zweiter Long-Press auf anderen Trigger | erstes Popover schließt automatisch (nativ, eine `auto`-Popover gleichzeitig) |

Erkennung via `event.pointerType === 'touch'`. `mouse` und `pen`
fallen in den Desktop-Pfad.

### 7.3 Tastatur-only (kein Pointer)

- Trigger `<a>`/`<span tabindex="0">` ist fokussierbar.
- `focus` öffnet Popover, `blur` schließt.
- `Tab` durch das Popover-Innere? Nicht nötig — Popover hat keinen
  interaktiven Inhalt, ist read-only.
- `Esc` dismisst nativ (Browser-Default für `popover="auto"`).

## 8. CSS — Popover-Styling

Keine neue Stylesheet-Datei nötig. Tailwind-Klassen direkt in den
Template-Tags. Wichtig:

- `m-0` neutralisiert Browser-Default `margin: auto` für Popovers
  (würde sonst im Viewport zentrieren).
- `position: fixed` + `top`/`left` werden per JS gesetzt — Tailwind kann
  das nicht statisch ausdrücken.
- `whitespace-nowrap` für ein-zeilige Daten-Paare; `max-w-xs` als
  Sicherheit gegen extreme Inhalte.
- `[hover:hover]:cursor-help` als Arbitrary-Variant auf dem `<span>`-
  Trigger in `cidr_info` — Cursor-Hinweis nur dort, wo Hover existiert.

## 9. Tests

### 9.1 `test_cidr_tags.py` — neu/umbenannt

```python
def test_cidr_info_renders_trigger_and_panel():
    out = render("{% cidr_info '10.0.0.0/24' %}")
    assert 'data-info-trigger=' in out
    assert 'aria-describedby=' in out
    assert 'popover="auto"' in out
    assert 'role="button"' in out

def test_cidr_info_no_legacy_hover_classes():
    out = render("{% cidr_info '10.0.0.0/24' %}")
    assert 'group-hover:' not in out
    assert 'pointer-events-none' not in out

def test_cidr_info_panel_ids_unique_across_calls():
    out = render(
        "{% cidr_info '10.0.0.0/24' %}{% cidr_info '10.0.1.0/24' %}"
    )
    # Beide popover-divs vorhanden, ids unterscheiden sich
    ids = re.findall(r'popover="auto" id="([^"]+)"', out)
    assert len(ids) == 2 and ids[0] != ids[1]

def test_cidr_info_trigger_does_not_render_panel():
    out = render("{% cidr_info_trigger '10.0.0.0/24' 'pid-1' %}")
    assert 'popover' not in out
    assert 'data-info-trigger="pid-1"' in out

def test_cidr_info_panel_uses_given_id():
    out = render("{% cidr_info_panel '10.0.0.0/24' 'my-id' %}")
    assert 'id="my-id"' in out
    assert 'popover="auto"' in out

def test_free_suggestions_info_panel_lists_suggestions():
    suggestions = [{'prefix': 28, 'network': '10.0.0.0', 'size': 16}]
    out = render(
        "{% free_suggestions_info_panel s 16 'sug-1' %}",
        {'s': suggestions},
    )
    assert 'id="sug-1"' in out
    assert '/28' in out and '10.0.0.0' in out
```

### 9.2 `test_blocks.py`

Keine Änderung erwartet — bestehende Assertions prüfen sichtbare
Strings, nicht CSS-Klassen.

### 9.3 JS-Tests

Nicht in Scope. Manueller Test in Plan: Desktop hover, Desktop Tab-
Focus, Touch long-press in Chrome DevTools Device Mode.

Erwartung: bestehende ~85 Tests + 6 neue = **~91 Tests**.

## 10. Migration & Rollout

Single-PR-Rollout. Keine Feature-Flags, kein Backwards-Compat-Shim
(`cidr_tooltip`/`cidr_tooltip_panel` werden gelöscht und alle Aufrufer
in einem Sweep migriert; Grep im PR-Reviewer zeigt Vollständigkeit).

Build-Hinweis: Tailwind-Build muss `select-none`,
`[-webkit-touch-callout:none]`, `[hover:hover]:cursor-help` und
`whitespace-nowrap` enthalten — Klassen sind im Template-Output, der
JIT-Scan findet sie.

## 11. Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| iOS Long-Press zeigt Selektions-Callout vor 500ms | `-webkit-touch-callout: none` + `user-select: none` auf Trigger |
| Click-Suppress nach Long-Press feuert nicht (Race) | Timer-Callback setzt `suppressClick` direkt beim Öffnen des Popovers; Capture-Phase-Listener auf Trigger fängt nachfolgenden `click` und setzt Flag zurück. Zusätzlich 100ms-Fallback-Timeout, falls kein `click` mehr kommt. |
| Popover-Position falsch bei dynamischem Resize | Re-Position auf `resize`/`scroll` während offenes Popover (Listener bei show, entfernen bei hide) |
| Popover deckt eigenes Trigger-Element | 4 px Gap (top/bottom) im Positions-Algorithmus |
| Mehrere Popovers gleichzeitig | `popover="auto"` schließt vorheriges automatisch beim Öffnen eines neuen |
| Screen-Reader liest Panel doppelt vor | `aria-describedby` verlinkt Trigger → Panel; Browser handhabt Vorlesen einmalig |

## 12. Offene Punkte

Keine — alle Entscheidungen mit User geklärt:
- Vollsanierung (nicht Patch).
- Long-Press auf Touch (nicht Info-Icon, nicht Single-Tap-Toggle).
- Ansatz B (HTML `popover` + ~40 Zeilen JS).
