# Mehrere Anwendungen pro Subnetz + IP-Zuordnungen (Design)

**Datum:** 2026-05-17
**Status:** Spec, zur Plan-Erstellung
**Basis:** Subnetly nach `2026-05-16-customer-rename-and-crud-design.md`
**Repo:** `/srv/docker/IP-Planer/`

## 1. Zweck

Heute hängt ein Subnetz (`Assignment`) an genau einer Anwendung. Das passt
nicht zu Punkt-zu-Punkt-Subnetzen: ein /30 zwischen zwei Routern wird von
beiden Routern genutzt — beide sind eigenständige Anwendungen.

Zwei verknüpfte Erweiterungen:

1. **M2M Subnetz ↔ Anwendung.** Ein Subnetz kann mehreren Anwendungen
   zugeordnet sein. Die Subnetz-Liste der Anwendungen wird explizit
   gepflegt — unabhängig davon, ob bereits IPs vergeben sind.
2. **IP-Zuordnungen.** Auf der Bearbeiten-Seite des Subnetzes gibt es
   eine Liste der IPs, und jede IP kann einer der Subnetz-Anwendungen
   zugeordnet werden (strikt: nur Anwendungen aus der Subnetz-Liste).

Beide Ebenen werden unabhängig gepflegt: die Subnetz-Liste folgt nicht
automatisch aus den IP-Zuordnungen.

Out of Scope: siehe §10.

## 2. Datenmodell

### 2.1 `Assignment` — von FK zu M2M

```python
class Assignment(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.PROTECT, related_name="assignments")
    applications = models.ManyToManyField(Application, related_name="assignments")
    cidr = CidrAddressField()
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]
```

Wegfallend:
- `application` (FK)
- `gateway` (IP-Adresse)

`related_name="assignments"` auf der M2M bleibt — `Application.assignments`
ist also weiterhin gültig (jetzt durch die M2M-Beziehung).

### 2.2 Neues Modell `IPAssignment`

```python
class IPAssignment(models.Model):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="ip_assignments"
    )
    address = models.GenericIPAddressField()
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="ip_assignments"
    )
    is_gateway = models.BooleanField(default=False)
    label = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["address"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "address"],
                name="ip_unique_per_assignment",
            ),
            models.UniqueConstraint(
                fields=["assignment"],
                condition=models.Q(is_gateway=True),
                name="ip_one_gateway_per_assignment",
            ),
        ]

    def clean(self):
        super().clean()
        # 1) Adresse muss im CIDR des Subnetzes liegen
        # 2) application muss in assignment.applications enthalten sein
```

**Constraints (DB-Ebene):**
- Eindeutigkeit `(assignment, address)`.
- Partieller Unique-Index: max. ein `is_gateway=True` pro Subnetz.

**Validierung (`clean`, App-Ebene):**
- `address` liegt im `assignment.cidr` (gleiche IP-Familie, in-pool ist
  schon durch `Assignment.clean` garantiert).
- `application` ist in `assignment.applications.all()`.

**`on_delete`:**
- `assignment`: CASCADE — löschst du das Subnetz, sind die IP-Zuordnungen
  bedeutungslos.
- `application`: PROTECT — verhindert das Löschen einer Anwendung, solange
  sie noch IPs hält. Konsistent mit `Pool ← Assignment`.

### 2.3 Beziehungen — Übersicht

```
Pool ──< Assignment >── Application       (M2M, neu)
            │
            └──< IPAssignment >── Application (FK, neu)
```

## 3. Migration `0004_multi_app_subnets`

Eine Datei, drei logische Schritte:

### 3.1 Schema (vorwärts, Phase 1)
- Anlegen der M2M-Tabelle `ipam_assignment_applications`.
- Anlegen von `IPAssignment` mit allen Constraints.
- Alte Felder `Assignment.application` und `Assignment.gateway` noch da.

### 3.2 Datenmigration (`RunPython`)

```python
def migrate_data(apps, schema_editor):
    Assignment = apps.get_model("ipam", "Assignment")
    IPAssignment = apps.get_model("ipam", "IPAssignment")
    for a in Assignment.objects.all():
        a.applications.add(a.application)
        if a.gateway:
            IPAssignment.objects.create(
                assignment=a,
                address=a.gateway,
                application=a.application,
                is_gateway=True,
            )

def reverse_data(apps, schema_editor):
    Assignment = apps.get_model("ipam", "Assignment")
    for a in Assignment.objects.all():
        first = a.applications.order_by("name").first()
        if first is not None:
            a.application = first
        gw = a.ip_assignments.filter(is_gateway=True).first()
        if gw is not None:
            a.gateway = gw.address
        a.save()
```

### 3.3 Schema (vorwärts, Phase 2)
- Drop `Assignment.application`.
- Drop `Assignment.gateway`.

**Pre-Migration-Schritt im Plan:** `pg_dump`-Backup von Tabellen
`ipam_assignment`, `ipam_application`. Wird als Checkpoint im Plan
verankert.

**Datenverlust-Risiko:** keiner — alle bestehenden Daten bleiben
erhalten, Down-Migration über `reverse_data` definiert.

## 4. UI: Subnetz-Edit-Seite

### 4.1 Aufbau

```
┌─────────────────────────────────────────────────┐
│  Subnetz bearbeiten — 10.0.0.0/30                │
├─────────────────────────────────────────────────┤
│  [Form 1: Subnetz-Metadaten]                     │
│  CIDR:        10.0.0.0/30                        │
│  Anwendungen: ☑ Router-A  ☑ Router-B  ☐ DB ...   │
│  Notes:       [                     ]            │
│              [Speichern]                         │
├─────────────────────────────────────────────────┤
│  IP-Zuordnungen (4 IPs — vollständig)            │
│  ┌──────────┬───────────┬─────┬─────┬────┬────┐  │
│  │ Adresse  │ Anwendung │ GW  │Label│Notes│ ✓ │  │
│  ├──────────┼───────────┼─────┼─────┼────┼────┤  │
│  │ 10.0.0.0 │  —        │ ○   │     │    │ ✓  │  │
│  │ 10.0.0.1 │ [Router-A]│ ●   │ WAN │    │ ✓  │  │
│  │ 10.0.0.2 │ [Router-B]│ ○   │ WAN │    │ ✓  │  │
│  │ 10.0.0.3 │  —        │ ○   │     │    │ ✓  │  │
│  └──────────┴───────────┴─────┴─────┴────┴────┘  │
└─────────────────────────────────────────────────┘
```

### 4.2 Zwei getrennte Formulare

- **Form 1 (Subnetz-Metadaten):** klassisches Subnetz-Form, ein Submit
  speichert `cidr`, `applications`, `notes`. POST an `assignment_edit`.
- **Form 2..N (IP-Zeile):** jede IP-Zeile ist ein eigenes
  `<form method="POST">` mit eigenem Submit-Icon. POST an
  `ip_assignment_save`. Bedeutung: Subnetz-Metadaten und IP-Details
  werden nie gemeinsam abgeschickt — Fehler bleiben pro Zeile lokal.

### 4.3 Vollständige vs sparse Ansicht

Cut-off bei **32 IPs** (entspricht IPv4 /27 bzw. IPv6 /123):
- **Vollständig** (Subnetz hat ≤ 32 IPs): die Server-Seite rendert für
  jede Adresse im CIDR eine Zeile. Existiert ein `IPAssignment`, ist die
  Zeile vorbefüllt; sonst ist sie eine leere Eingabezeile mit "Anlegen"-
  Submit.
- **Sparse** (Subnetz hat > 32 IPs): nur bestehende `IPAssignment`-Zeilen
  werden gerendert + eine "+ IP hinzufügen"-Eingabezeile am Ende. Kein
  AJAX/JS nötig — der Submit fügt eine Zeile hinzu, Seite lädt neu.

### 4.4 Felder pro IP-Zeile

- `address`: bei vollständiger Variante als hidden + sichtbar, bei
  sparse als textbasiertes Eingabefeld.
- `application`: `<select>` mit `queryset = assignment.applications.all()`.
  Leere Auswahl entspricht "noch nicht zugeordnet" → Zeile existiert
  dann (noch) nicht in der DB (vollständige Ansicht: keine Speicherung
  ohne Application).
- `is_gateway`: Checkbox pro Zeile, im jeweiligen Zeilen-Form. Wenn beim
  Save einer Zeile `is_gateway=True` ankommt, entfernt die View das Flag
  bei allen anderen IPs des Subnetzes in derselben Transaktion. Visuelle
  Konsistenz (in den nicht-gespeicherten Zeilen): das Template
  rendert den Checkbox-State aus der aktuellen DB-Lage (`ip.is_gateway`),
  ein Klick allein ohne Submit verändert nichts. (Radio-Buttons sind in
  HTML pro `<form>` gegruppt — bei der mehr-`<form>`-Struktur dieser
  Seite reicht ein Radio nicht; die Cross-Form-Uniqueness wird daher
  ausschließlich serverseitig durchgesetzt — siehe auch DB-Constraint
  `ip_one_gateway_per_assignment` als Sicherheitsnetz.)
- `label`: optionaler Kurzname (z.B. "WAN").
- `notes`: optional, einzeilig.

### 4.5 Fehlersituation: leere Anwendungs-Liste

Wenn `assignment.applications` leer ist, ist das App-Dropdown leer und
oberhalb der IP-Liste steht eine Hinweismeldung: "Erst Anwendungen am
Subnetz hinterlegen, dann können IPs zugeordnet werden." Submit der
Subnetz-Form mit leerer M2M ist erlaubt — Subnetz ohne Anwendung ist
nicht verboten (z.B. Reservierung für späteren Ausbau).

### 4.6 Entfernen einer Anwendung mit existierenden IP-Zuordnungen

Wenn der Operator eine Anwendung aus der Subnetz-M2M entfernt, die noch
IP-Zuordnungen hat, würde das die `application-must-be-in-subnet-apps`-
Validierung in `IPAssignment.clean` verletzen. `AssignmentForm.clean`
blockt das mit einer Fehlermeldung:

```python
def clean_applications(self):
    apps = self.cleaned_data["applications"]
    if self.instance.pk:
        used = set(
            self.instance.ip_assignments.values_list("application_id", flat=True)
        )
        missing = used - {a.id for a in apps}
        if missing:
            names = Application.objects.filter(pk__in=missing).values_list("name", flat=True)
            raise ValidationError(
                f"Diese Anwendungen haben noch IP-Zuordnungen und können nicht "
                f"entfernt werden: {', '.join(names)}. Erst die IPs löschen."
            )
    return apps
```

Keine stillen Kaskaden-Löschungen — der Operator entscheidet aktiv.

### 4.6 Pool-Detail-Visualisierung

- IPv4-Block-Farbe: Blockfarbe bestimmt sich aus der **alphabetisch
  ersten** Anwendung der M2M-Liste. Bei leerer M2M: neutrale Farbe (`—`).
- Block-Tooltip/`title`-Attribut zeigt alle Anwendungen kommagetrennt.
- `colors_for_set` wird mit einer Liste der "ersten Anwendung" pro
  Subnetz aufgerufen — die übrige Logik bleibt.
- IPv6-Liste (`pool_detail`-Listansicht): Spalte "Anwendung" wird
  kommagetrennt gerendert.

## 5. URLs & Views

### 5.1 Neue URLs

```python
path("subnet/<int:assignment_id>/ip/save/",
     views.ip_assignment_save, name="ip_assignment_save"),
path("subnet/<int:assignment_id>/ip/<int:ip_id>/delete/",
     views.ip_assignment_delete, name="ip_assignment_delete"),
```

URL-Namensraum: weiterhin `ipam:`. Pfadbasis `subnet/` analog zu
`anwendung/` aus dem vorigen Spec — bewusst nicht `assignment/`, weil
die UI-Sprache ohnehin "Subnetz" lautet.

### 5.2 Views

**`assignment_edit`** wird erweitert:
- `AssignmentForm` rendert M2M-Multi-Select für `applications`.
- Im Context zusätzlich `ip_rows`: vorberechnete Liste aus
  `services/ip_list.py: build_ip_rows(assignment)`.

**`ip_assignment_save`:**

```python
@login_required
def ip_assignment_save(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method != "POST":
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)
    address = request.POST.get("address")
    instance = IPAssignment.objects.filter(
        assignment=assignment, address=address,
    ).first()
    form = IPAssignmentForm(request.POST, instance=instance, assignment=assignment)
    if form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.assignment = assignment
            if obj.is_gateway:
                IPAssignment.objects.filter(
                    assignment=assignment, is_gateway=True,
                ).exclude(pk=obj.pk).update(is_gateway=False)
            obj.save()
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)
    # Fehlerpfad: Edit-Seite direkt rendern (kein Redirect — sonst
    # gehen Form-Errors verloren). Das `build_ip_rows`-Ergebnis wird
    # für die fehlerhafte Zeile durch das bound, ungültige `form`
    # ersetzt, sodass `form.errors` neben dem Submit angezeigt werden
    # kann.
    rows = build_ip_rows(assignment)
    for row in rows:
        if row["address"] == address:
            row["form"] = form
            break
    else:
        # Sparse-Modus, Adresse noch nicht in rows — als neue Zeile anhängen
        rows.append({"address": address, "ip_assignment": None,
                     "form": form, "is_full_mode": False})
    return render(request, "assignment_form.html", {
        "form": AssignmentForm(instance=assignment, pool=assignment.pool),
        "assignment": assignment,
        "pool": assignment.pool,
        "ip_rows": rows,
    })
```

**`ip_assignment_delete`:**

```python
@login_required
def ip_assignment_delete(request, assignment_id, ip_id):
    obj = get_object_or_404(IPAssignment, pk=ip_id, assignment_id=assignment_id)
    obj.delete()
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)
```

### 5.3 `IPAssignmentForm`

```python
class IPAssignmentForm(forms.ModelForm):
    class Meta:
        model = IPAssignment
        fields = ["address", "application", "is_gateway", "label", "notes"]
        widgets = {"notes": forms.TextInput()}

    def __init__(self, *args, assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        if assignment is not None:
            self.fields["application"].queryset = assignment.applications.all()

    def clean(self):
        cleaned = super().clean()
        if self.assignment is None:
            return cleaned
        instance = self.instance or IPAssignment()
        instance.assignment = self.assignment
        instance.address = cleaned.get("address")
        instance.application = cleaned.get("application")
        try:
            instance.clean()
        except ValidationError as exc:
            self.add_error(None, exc)
        return cleaned
```

### 5.4 `AssignmentForm` — angepasst

- Feld `application` (FK) → `applications` (M2M, `CheckboxSelectMultiple`
  oder Tailwind-Multi-Select).
- `gateway` entfällt.
- Overlap-Fehlermeldung: `"Überschneidung mit {cidr} ({apps_str})"`, wo
  `apps_str = ", ".join(a.name for a in other.applications.all()) or "—"`.

### 5.5 Hilfsmodul `services/ip_list.py`

```python
def build_ip_rows(assignment):
    """Returns list of dicts: {"address", "ip_assignment", "form", "is_full_mode"}."""
    net = IPNetwork(str(assignment.cidr))
    size = net.size
    existing = {str(ip.address): ip for ip in assignment.ip_assignments.all()}
    if size <= 32:
        return [
            {
                "address": str(ip),
                "ip_assignment": existing.get(str(ip)),
                "form": IPAssignmentForm(
                    instance=existing.get(str(ip)),
                    assignment=assignment,
                    initial={"address": str(ip)},
                ),
                "is_full_mode": True,
            }
            for ip in net
        ]
    return [
        {
            "address": addr,
            "ip_assignment": ip,
            "form": IPAssignmentForm(instance=ip, assignment=assignment),
            "is_full_mode": False,
        }
        for addr, ip in existing.items()
    ]
```

Reine Service-Funktion ohne Django-DB-Magie außer `assignment.ip_assignments`.

## 6. Auswirkungen auf bestehende Module

| Datei | Änderung |
|---|---|
| `models.py` | M2M `applications`, neues `IPAssignment`, alte Felder weg |
| `migrations/0004_*.py` | neue Migration (Schema + RunPython + Schema) |
| `forms.py` | `AssignmentForm.application` → `applications`; neue `IPAssignmentForm` |
| `views.py` | `assignment_edit` erweitert um `ip_rows`; neue Views `ip_assignment_save`/`_delete`; Pool-Color-Logik nutzt `_first_app_name(a)` |
| `urls.py` | neue Routen `ip_assignment_save`/`_delete` |
| `services/ip_list.py` | **neu** — `build_ip_rows` |
| `services/colors.py` | unverändert (Key-Logik bleibt name-basiert) |
| `templates/assignment_form.html` | erweitert um IP-Liste + zweites Submit pro Zeile |
| `templates/pool_detail.html` | Spalte "Anwendung" → kommagetrennt; Block-Tooltip mit voller Liste |
| `templates/application_detail.html` | unverändert — `application.assignments` läuft jetzt über M2M, identische Semantik |
| `admin.py` | `AssignmentAdmin.fields`: `applications`/`cidr`/`notes` (M2M-Widget); `IPAssignmentInline` als TabularInline |
| `management/commands/import_wiki.py` | importierte App via `a.applications.add(app)` statt `a.application = app` |
| `services/wiki_parser.py` | unverändert — Parser-Ausgabe-Feld bleibt `application` (Single) |
| `tests/*.py` | siehe §7 |

## 7. Tests

### 7.1 Bestehende Tests anpassen

- Überall, wo `assignment.application` gelesen wird → `assignment.applications.first()`.
- `AssignmentForm`-Tests: Feld-Name `application` → `applications`.
- Wiki-Import-Test: importierte App landet in `applications.all()`.
- Overlap-Fehlertext-Test: neuer Format (erste App alphabetisch).

### 7.2 Neue Tests

**Modell:**
- `test_ip_assignment_address_must_be_in_cidr`
- `test_ip_assignment_application_must_be_in_subnet_apps`
- `test_ip_assignment_unique_per_assignment`
- `test_only_one_gateway_per_assignment`
- `test_deleting_assignment_cascades_to_ip_assignments`
- `test_application_delete_protected_when_ip_assigned`

**View:**
- `test_ip_assignment_save_creates_new_row`
- `test_ip_assignment_save_updates_existing_row`
- `test_ip_assignment_save_setting_gateway_clears_others`
- `test_ip_assignment_save_rejects_app_outside_subnet`
- `test_ip_assignment_save_renders_errors_inline_on_validation_failure`
- `test_ip_assignment_delete_removes_row`
- `test_assignment_edit_renders_full_iplist_for_small_subnet` (/30 → 4 Zeilen)
- `test_assignment_edit_renders_sparse_iplist_for_large_subnet` (/24)
- `test_assignment_form_rejects_removal_of_app_with_ip_assignments`

**Migration:**
- `test_0004_migrates_single_app_to_m2m` (MigrationExecutor-basiert)

**Services:**
- `test_build_ip_rows_full_mode_includes_all_addresses_with_gaps`
- `test_build_ip_rows_sparse_mode_only_returns_existing`

**Pool-Visualisierung:**
- `test_pool_color_uses_first_app_alphabetically`

**Erwartung:** 43 + ~17 = **~60 Tests** nach Abschluss.

## 8. Auth

Alle neuen Views `@login_required`.

## 9. Reverse-Proxy / Repo

- Caddy: keine Änderungen.
- Repo: alle Änderungen unter `/srv/docker/IP-Planer/`. Keine Änderungen
  in `/home/kai/reverse-proxy/`.

## 10. Out of Scope (v1.2)

- Bulk-Edit von IPs (z.B. "alle .10..20 → DB-Cluster").
- HTMX/AJAX-Inline-Edit. Sparse-Modus arbeitet vorerst mit Server-
  Roundtrip + nativer Form.
- Reservierung von IPs ohne Anwendung (`IPAssignment.application` ist
  nicht-nullable).
- Hostname-/DNS-Lookup für `label`.
- Audit-Log.
- Pool-Block-Visualisierung "gestreift pro Anwendung" — Farbe folgt
  bewusst der ersten App alphabetisch.

## 11. Offene Punkte

Keine — alle Anforderungen geklärt.
