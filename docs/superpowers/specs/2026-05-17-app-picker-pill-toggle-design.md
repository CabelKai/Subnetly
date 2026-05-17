# Anwendungs-Picker als Pill-Toggles

## Ziel

Auf der Subnetz-Edit-Seite (`assignment_form.html`) das Feld `applications`
nicht mehr als vertikale Checkbox-Liste rendern, sondern als horizontale
Reihe von Pill-Toggles. Klick toggelt; ausgewählte Pills haben dunklen
Slate-900-Hintergrund mit weißer Schrift, nicht-ausgewählte sind hell und
neutral.

## Scope

- Nur das `applications`-Feld in `AssignmentForm` (forms.py:23).
- Andere Multi-Select-Felder im Projekt bleiben unverändert.
- Funktionsumfang gleich: M2M-Auswahl, gleicher POST-Payload, gleiche
  Validierung.

## Technischer Ansatz

### Custom Widget

Neue Datei `web/ipam/widgets.py`:

```python
from django import forms


class PillCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = "ipam/widgets/pill_checkbox_select.html"
    option_template_name = "ipam/widgets/pill_checkbox_option.html"
```

In `forms.py`:

```python
from .widgets import PillCheckboxSelectMultiple

# in AssignmentForm.Meta.widgets:
"applications": PillCheckboxSelectMultiple(),
```

### Widget-Templates

`web/ipam/templates/ipam/widgets/pill_checkbox_select.html` — Container:

```django
<div class="flex flex-wrap gap-2">
  {% for group, options, index in widget.optgroups %}
    {% for option in options %}
      {% include option.template_name with widget=option %}
    {% endfor %}
  {% endfor %}
</div>
```

`web/ipam/templates/ipam/widgets/pill_checkbox_option.html` — eine Pill.
Wir delegieren die Input-Attribute an Djangos eigenes
`django/forms/widgets/attrs.html`, das `name`, `value`, `id`, `checked`
und alle weiteren `attrs` korrekt rendert:

```django
<label class="px-3 py-1.5 rounded-full border border-slate-300 bg-slate-50
              text-sm text-slate-600 cursor-pointer select-none transition
              hover:border-slate-400 hover:bg-slate-100
              focus-within:ring-2 focus-within:ring-slate-400
              has-[:checked]:bg-slate-900 has-[:checked]:text-white
              has-[:checked]:border-slate-900">
  <input type="{{ widget.type }}" name="{{ widget.name }}"
         {% if widget.value != None %}value="{{ widget.value|stringformat:'s' }}"{% endif %}
         class="sr-only"
         {% include "django/forms/widgets/attrs.html" %}>
  {{ widget.label }}
</label>
```

Die `checked`-Markierung kommt automatisch über `widget.attrs.checked`,
das Django für selektierte Optionen setzt (gleiche Mechanik wie das
Standard-`CheckboxSelectMultiple.option_template`).

### Settings

`web/subnetly/settings.py`: `TEMPLATES[0]["DIRS"]` muss App-Template-Pfade
einschließen (üblicherweise schon der Fall durch
`APP_DIRS=True`). Falls Django die Widget-Templates aus dem App-Ordner
nicht findet, ggf. `FORM_RENDERER = "django.forms.renderers.TemplatesSetting"`
setzen und `django.forms` zu `INSTALLED_APPS` hinzufügen — nur falls
nötig, vorher testen.

## CSS / Browser

- Tailwind 3.4+ via CDN (in `base.html:7`) unterstützt den
  `has-[:checked]:`-Modifier.
- `:has()`-Selektor: Chrome 105+, Firefox 121+, Safari 15.4+. Alle
  aktuellen Browser ok. Kein Polyfill, kein Fallback.
- Echte Checkbox via `sr-only` versteckt (visuell, aber für Screenreader
  und Tastatur erreichbar). `focus-within:ring-*` macht Tastatur-Fokus
  sichtbar.

## Bestehendes JS bleibt funktional

`assignment_form.html:199` liest
`input[type="checkbox"][name="applications"]:checked` aus, um den
IP-Anwendungs-Dropdown live zu füllen. Da die Checkbox-Inputs als reale
DOM-Elemente weiter existieren (nur visuell als Pill gestylt), funktioniert
das JS unverändert.

## Validierung / Datenmodell

Unverändert:
- `ModelMultipleChoiceField` (automatisch aus M2M).
- POST-Payload `applications=<id>&applications=<id>` identisch.
- `AssignmentForm.clean_applications` (forms.py:65) — Logik unverändert.

## Empty-State

Wenn keine Anwendung im System existiert, ist der Pill-Container leer
(genau wie heute die Checkbox-Liste leer wäre). Das ist kein neuer
Edge-Case und wird in diesem Design nicht adressiert.

## Tests

- Bestehende View-Tests in `test_views.py` müssen grün bleiben
  (POST-Format unverändert).
- Neuer Smoke-Test: `assignment_form` rendert pro Application genau ein
  `<label>` mit `has-[:checked]:` in der Klassen-Liste und ein
  `<input type="checkbox" name="applications">` darin. Reicht aus, um
  Widget-Template-Brüche zu fangen.

## Out of Scope

- Suche / Filter im Picker.
- "Alle / Keine"-Buttons.
- Empty-State-Verbesserung wenn keine App existiert.
- Andere Formulare und Widgets.
- IPv6-spezifische Anpassungen — der Picker ist Pool-typ-agnostisch.
- Drag-and-Drop, Sortierung, Gruppierung der Pills.
