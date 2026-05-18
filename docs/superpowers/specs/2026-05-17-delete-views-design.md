# Delete-Views für Pool, Application, Assignment

Aktuell lassen sich `Pool`, `Application` und `Assignment` nur via `/admin/`
löschen. Diese Spec ergänzt das fehlende UI-CRUD um Lösch-Endpoints für
alle drei Entitäten.

## Scope und Nicht-Scope

**In Scope:**
- POST-only Delete-Endpoints für Pool, Application, Assignment.
- Bestätigungs-Modal pro Detail-Seite (natives `<dialog>`).
- Pre-Check: Anzahl/Liste der betroffenen Kinder vor dem Klick anzeigen.
- Defense-in-depth: View prüft Blocker erneut, ignoriert POSTs die die
  UI-Sperre umgehen.

**Nicht in Scope:**
- Kein Cascade-Override („auch Kinder löschen"). User muss erst leeren.
- Kein Soft-Delete / Trash / Undo. Hard delete.
- Kein „Name eintippen zum Bestätigen". Pre-Check im Modal reicht.
- Kein Bulk-Delete von Listen-Seiten. Nur Detail-Seite.

## DB-Realität (gegeben)

| Entity | FK-Verhalten |
|---|---|
| `Pool` | PROTECTed durch `Assignment.pool` |
| `Application` | PROTECTed durch `IPAssignment.application`; M2M `Assignment.applications` löst sich automatisch |
| `Assignment` | CASCADEt zu eigenen `IPAssignment`s; M2M zu `Application` löst sich automatisch |

## URLs

```python
path("pool/<int:pool_id>/delete/",             views.pool_delete,        name="pool_delete"),
path("anwendung/<int:application_id>/delete/", views.application_delete, name="application_delete"),
path("assignment/<int:assignment_id>/delete/", views.assignment_delete,  name="assignment_delete"),
```

## Views

Drei kleine Views, gleiches Muster, `@login_required` + `@require_POST`.

```python
@login_required
@require_POST
def pool_delete(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    if pool.assignments.exists():
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
    asgn.delete()  # CASCADEs to IPAssignments
    return redirect("ipam:pool_detail", pool_id=pool_id)
```

Re-Check vor `delete()` ist Defense-in-depth: der Pre-Check im Modal hat
den Button schon ausgeblendet, aber ein manuell konstruierter POST darf
die DB nicht in einen `ProtectedError` rennen lassen.

## Pre-Check-Daten

Jeder Detail-View erweitert sein Context um `delete_blockers` und
`delete_cascade_message`.

| View | `delete_blockers` (Liste von Strings) | `delete_cascade_message` |
|---|---|---|
| `pool_detail` | `f"{a.cidr} ({apps_or_dash})"` für jede Assignment | leer |
| `application_detail` | `f"{ip.address} (Subnetz {ip.assignment.cidr})"` für jede `IPAssignment` mit dieser App | bei leeren Blockern: `f"Wird aus {n} Subnetz(en) entfernt."` (n = M2M-Refs) oder `"Keine Referenzen — wird komplett entfernt."` |
| `assignment_edit` | leer (CASCADE) | `f"Wird mit {n} IP-Zuordnung(en) gelöscht."` (n = `ip_assignments.count()`) |

## Modal-Markup

Ein `<dialog>`-Element pro Detail-Seite, unter dem Lösch-Button platziert.
Wiederverwendet als Partial `_delete_dialog.html`:

```django
{% load static %}
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

Partial-Pfad: `web/ipam/templates/_delete_dialog.html`.

Kontext-Variablen pro Seite (via `{% include %}` mit `with`-Klausel):
- `delete_title` — feste Strings:
  - Pool: `"Pool löschen?"`
  - Application: `"Anwendung löschen?"`
  - Assignment: `"Subnetz löschen?"`
- `delete_action`:
  - Pool: `{% url 'ipam:pool_delete' pool.pk %}`
  - Application: `{% url 'ipam:application_delete' application.pk %}`
  - Assignment: `{% url 'ipam:assignment_delete' assignment.pk %}`
- `delete_blockers`, `delete_cascade_message` (siehe Tabelle oben)

## Detail-Seiten — Integration

Im Header jeder Detail-Seite kommt der Lösch-Button rechts neben dem
bestehenden `Bearbeiten`-Button hinzu. Konkret:

- `pool_detail.html`: Header-Buttons-Reihe → `[Bearbeiten] [+ Zuweisung] [Löschen]`
- `application_detail.html`: → `[Bearbeiten] [Löschen]`
- `assignment_form.html` (nur Edit-Modus, also `{% if assignment %}`):
  unter den Subnetz-Buttons.

Das Partial `_delete_dialog.html` wird via `{% include %}` mit den oben
beschriebenen Context-Variablen eingebunden.

## Tests

Pro Entity drei View-Tests + ein Detail-Render-Test (≈12 neue Tests):

### Pool
- `test_pool_delete_happy_path` — leerer Pool, POST → 302 zu `index`, Pool weg
- `test_pool_delete_blocked_by_assignments_does_not_delete` — POST trotz Assignment → 302, Pool noch da
- `test_pool_delete_get_returns_405`
- `test_pool_detail_shows_delete_dialog_with_blockers_when_assignments_exist`

### Application
- `test_application_delete_happy_path` — App ohne IPs, POST → 302 zu `application_list`, App weg
- `test_application_delete_blocked_by_ip_assignments_does_not_delete`
- `test_application_delete_get_returns_405`
- `test_application_detail_shows_cascade_message_when_no_blockers`

### Assignment
- `test_assignment_delete_happy_path` — POST → 302 zu `pool_detail`, Assignment weg
- `test_assignment_delete_cascades_ip_assignments` — IPs vorher, alle weg nachher
- `test_assignment_delete_get_returns_405`
- `test_assignment_edit_shows_cascade_message_with_ip_count`

## Risiken / Edge Cases

1. **CSRF auf POST-only Endpoints:** Django-Middleware kümmert sich, da die
   Form im `<dialog>` `{% csrf_token %}` hat.
2. **`@require_POST` und Tests:** GET liefert 405, nicht 302. Tests müssen
   das berücksichtigen (bestehende `ip_assignment_delete`-Tests gehen
   noch von 302 aus — separate Migration, nicht Teil dieser Spec).
3. **`<dialog>`-Browser-Support:** Alle aktuellen Browser seit 2022; bei
   uralten Browsern fällt das Element auf inline-Rendering zurück und
   stört das Layout — akzeptabel für eine interne LAN-Anwendung.
4. **Modal-Fokus-Trap:** `showModal()` trapped Fokus automatisch (native
   API). Esc schließt nativ. Backdrop-Klick schließt nicht (Standard) —
   das ist hier sogar gewünscht, damit nicht versehentlich abgebrochen
   wird.
5. **Pool/Application mit vielen Blockern:** Liste hat `max-h-40
   overflow-y-auto`, damit das Modal nicht über die Viewport-Höhe
   wächst.
