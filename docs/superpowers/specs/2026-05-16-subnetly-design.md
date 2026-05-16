# Subnetly – KNT IP Planer (Design)

**Datum:** 2026-05-16
**Status:** Spec, freigegeben zur Plan-Erstellung
**Domain:** `subnetly.kntinternet.de`
**Projektpfad:** `/srv/docker/IP-Planer/`

## 1. Zweck

Ersatz für den aktuellen Wiki-Eintrag, in dem die IP-Vergaben unseres Netzes
dokumentiert werden. Ziel:

- Überblick, welche Bereiche unserer Pool-Netze (z.B. `217.61.248.0/23`,
  `2a05:ed80:100::/48`) bereits an Kunden/Standorte vergeben sind.
- Freie Bereiche auf einen Blick erkennen.
- Doppelvergaben durch DB-Constraints und Validierung verhindern.

Ausdrücklich **nicht** im Scope: DHCP/DNS-Anbindung, Ping/SNMP-Status,
Rack-/Device-Management, History/Audit-Log, REST-API, Mehrsprachigkeit, LDAP.

## 2. Stack & Deployment

- Django 5.x + Gunicorn
- PostgreSQL 16
- nginx (Static-Files + Reverse Proxy zu Gunicorn)
- Docker Compose, drei Services: `web`, `nginx`, `db`
- Externer Reverse Proxy (bereits vorhanden) terminiert TLS und leitet
  `subnetly.kntinternet.de` → `nginx:8080` auf dem Host.
- Frontend: Server-rendered Django-Templates + Tailwind CSS via CDN
  (kein Node-Build-Step).

## 3. Datenmodell

Bewusst minimal: drei Tabellen.

### 3.1 `Pool`
"Was uns offiziell zugewiesen wurde."

| Feld           | Typ                          | Hinweis                                            |
| -------------- | ---------------------------- | -------------------------------------------------- |
| `id`           | PK                           |                                                    |
| `name`         | CharField(100)               | Anzeigename, z.B. "Anycast 217.61.248.0/23"        |
| `cidr`         | `django-netfields` CidrField | z.B. `217.61.248.0/23` oder `2a05:ed80:100::/48`   |
| `ip_version`  | SmallInt (4 oder 6)          | abgeleitet aus `cidr` beim Speichern              |
| `block_prefix` | SmallInt, nullable           | nur IPv4: Auflösung der Blockansicht (z.B. `30`)   |
| `notes`        | TextField, blank              |                                                    |

### 3.2 `Customer`
"Kunde / Standort / Verwendungszweck."

| Feld    | Typ            |
| ------- | -------------- |
| `id`    | PK             |
| `name`  | CharField(100) unique |
| `notes` | TextField, blank |

### 3.3 `Assignment`
"Subnetz X gehört Kunde Y aus Pool Z."

| Feld       | Typ                             |
| ---------- | ------------------------------- |
| `id`       | PK                              |
| `pool`     | FK → Pool, on_delete=PROTECT    |
| `customer` | FK → Customer, on_delete=PROTECT |
| `cidr`     | CidrField                       |
| `gateway`  | InetField, null=True            |
| `notes`    | TextField, blank                |

### 3.4 Constraints (DB-seitig, nicht nur Application-Level)

1. `Assignment.cidr` muss vollständig in `Assignment.pool.cidr` enthalten sein.
   - Validierung im `clean()` + `CheckConstraint` (Postgres `<<=` Operator
     via `inet`-Typ).
2. Zwei `Assignment`s im selben Pool dürfen sich **nicht** überlappen.
   - Realisierung: Postgres `EXCLUDE USING gist` Constraint mit
     `pool_id WITH =, cidr WITH &&` (Overlap-Operator für `inet`).
   - Migration nutzt `RunSQL` falls Django das nicht direkt abbildet.
3. `Pool.cidr` ist unique.
4. `Pool.ip_version` wird via `pre_save`-Signal aus `cidr` gesetzt.

## 4. UI / Seiten

### 4.1 Globales Layout
- Header: Titel "Subnetly – KNT IP Planer", rechts Username + Logout.
- Linke Sidebar (alle Seiten sichtbar): Baum.
- Hauptfeld: kontextabhängig.

### 4.2 Sidebar-Baum
```
▼ 217.61.248.0/23  (IPv4 Anycast)
    ▼ BINSS
        · 217.61.249.0/28
        · 217.61.249.16/28
    ▶ Falcon
    ▶ SWE
▼ 2a05:ed80:100::/48  (IPv6)
    ▶ Cyter
    ▶ Falcon
▶ 45.151.168.0/30
```
- Pool klick → Pool-Detail.
- Kunde klick → springt zu seinen Subnetzen im Pool-Detail (Highlight).
- Subnetz klick → öffnet Detail-Panel im Pool-Detail.

### 4.3 Seiten

| Route                  | Inhalt |
| ---------------------- | ------ |
| `/`                    | Übersichtskarten aller Pools: CIDR, Bezeichnung, Auslastungs-Balken (% belegt), Anzahl freier Blöcke. |
| `/pool/<id>/`          | IPv4: Blockansicht (siehe 4.4). IPv6: Listenansicht (siehe 4.5). |
| `/customers/`          | Alphabetische Kundenliste mit Anzahl Assignments. |
| `/customer/<id>/`      | Alle Assignments des Kunden über alle Pools. |
| `/assignment/new/`     | Form: Pool, Kunde, CIDR, Gateway, Notes. |
| `/assignment/<id>/edit/` | Form, gleiche Felder. |
| `/login/`, `/logout/`  | Django-Auth-Views. |
| `/admin/`              | Django-Admin (Notfall + User-Verwaltung). |

### 4.4 IPv4-Blockansicht (Pool-Detail)
- Grid in `pool.block_prefix`-Einheiten (z.B. /30).
- Belegte Blöcke: farbig (Farbe pro Kunde stabil über Hash auf `customer.name`),
  Label = Kundenname + verkürzte CIDR (z.B. "BINSS · .0/28").
- Größere Assignments überspannen mehrere Blöcke per `colspan`.
- Freie zusammenhängende Bereiche: ein einzelner grauer Block "frei (N IPs)".
- Klick auf belegten Block → Detail-Panel rechts (Notes, Gateway, Edit-Button).
- Klick auf freien Block → "Hier neu zuweisen…" mit vorausgefülltem Pool +
  Vorschlag-CIDR (kleinste passende, anpassbar).

**Render-Algorithmus (vereinfachte Skizze):**
```
blocks = []
pos = pool.cidr.network_address
sorted_assigns = sorted(pool.assignments, key=lambda a: a.cidr.network_address)
for a in sorted_assigns:
    if pos < a.cidr.network_address:
        blocks.append(("free", pos, a.cidr.network_address - 1))
    blocks.append(("assigned", a))
    pos = a.cidr.broadcast_address + 1
if pos <= pool.cidr.broadcast_address:
    blocks.append(("free", pos, pool.cidr.broadcast_address))
```

Jeder Block belegt im Grid `2^(pool.block_prefix - block_prefix_length)`
Zellen, wobei `block_prefix_length` die Prefixlänge des jeweiligen Blocks
ist (für Assignments: deren Prefix; für Frei-Bereiche: die größte
Prefixlänge, die den Frei-Bereich vollständig abdeckt — ggf. mehrere
Frei-Blöcke, falls sich der Bereich nicht in einem einzigen CIDR
ausdrücken lässt).

Beispiel: Pool `/23` mit `block_prefix=30` → Grid hat 128 Zellen.
Ein `/28`-Assignment belegt `2^(30-28) = 4` Zellen.

### 4.5 IPv6-Pool-Detail (Listenansicht)
- Tabelle: CIDR | Kunde | Notes | Aktionen.
- Sortiert nach IP, Lücken zwischen vergebenen Subnetzen werden als
  separate "frei"-Zeile angedeutet (z.B. "frei: 2a05:ed80:100:401:: – 2a05:ed80:100:1612::").

### 4.6 Forms / Validierung
- Standard-Django-Forms, gerendert mit Tailwind-Klassen.
- Vor dem Speichern: `clean()` prüft Overlap und CIDR-in-Pool — bei
  Verletzung verständliche Fehlermeldung ("Überschneidung mit
  217.61.249.0/28 (BINSS)").
- DB-Constraint ist die Backstop; wenn das greift, wurde die Form-Validierung
  umgangen — als 500 fangen und User mit generischer Meldung informieren.

## 5. Authentifizierung

- Alle Views `@login_required`, inkl. `/`.
- Login-Seite: Django-eigener `LoginView`.
- User-Verwaltung über `/admin/`.
- Initial-Superuser via Env-Vars (`DJANGO_SUPERUSER_USERNAME`,
  `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_EMAIL`) wird beim ersten
  Containerstart per `entrypoint.sh` angelegt (idempotent: nur wenn noch kein
  Superuser existiert).
- Reverse Proxy davor schützt zusätzlich.

## 6. Wiki-Import

Management-Command: `python manage.py import_wiki <pfad>`

### 6.1 Voraussetzung
Pools müssen vor dem Import existieren (manuell über `/admin/` oder ein
separates Command anlegen). Initial-Pools voraussichtlich:
- `217.61.248.0/23` (Block-Prefix /30)
- `45.151.168.0/30` (oder größer, falls bekannt)
- `185.91.196.0/29` (oder größer)
- `2a05:ed80:100::/48`

Die genauen Pool-Definitionen liegen beim User; werden vor dem Import-Lauf
geklärt.

### 6.2 Parser-Regeln
1. `==== Name ====` → Customer (get_or_create).
2. CIDR-Regex (IPv4 + IPv6, mit/ohne Prefix-Länge) extrahiert
   Netzangaben aus der Zeile.
3. Einzel-IPs ohne Prefix → `/32` (IPv4) bzw. `/128` (IPv6).
4. `185.91.196.6, 7, 8` → drei `/32`-Assignments (`.6`, `.7`, `.8`).
5. Restlicher Zeilentext (z.B. "MT Router GB Straße") → `Assignment.notes`.
6. Pool-Zuordnung: kleinster Pool, der die Assignment-CIDR umschließt.
   Falls kein Pool passt → Eintrag wird übersprungen und geloggt.
7. Idempotent: existiert bereits ein `Assignment` mit gleichem
   `(pool, cidr)` → wird übersprungen (nicht überschrieben).
8. Constraint-Verletzungen (Overlap) → Eintrag wird übersprungen und geloggt,
   Import bricht nicht ab.

### 6.3 Output
```
Customers angelegt:   12
Customers vorhanden:   3
Assignments angelegt: 27
Übersprungen:          2  (siehe Log)
```

Übersprungene Einträge werden mit Begründung in eine Logdatei
`import_wiki_<timestamp>.log` geschrieben.

## 7. Repo-Struktur

```
/srv/docker/IP-Planer/
├── docker-compose.yml
├── .env                # secrets (gitignored)
├── .env.example
├── CLAUDE.md
├── README.md
├── docs/
│   ├── wiki-export.txt # initialer Wiki-Dump
│   └── superpowers/specs/2026-05-16-subnetly-design.md
├── nginx/
│   └── default.conf
└── web/
    ├── Dockerfile
    ├── entrypoint.sh
    ├── requirements.txt
    ├── manage.py
    ├── subnetly/        # Projekt-Settings, urls, wsgi
    └── ipam/            # App: models, views, forms, urls,
                         #      templates, static, management/commands, tests
```

## 8. Tests

- pytest-django.
- Modell-Tests: CIDR-in-Pool-Validierung, Overlap-Constraint, Superuser-Init.
- Parser-Tests: Wiki-Auszug als Fixture, deckt jede Wiki-Variante ab
  (CIDR, Einzel-IP, IP-Range-Aufzählung, IPv6, Doppelnetze pro Kunde).
- View-Tests: smoke (`/`, `/pool/<id>/`, `/customer/<id>/`, Login-Required).

## 9. Backup

- Daily Cron im `db`-Container: `pg_dump` nach Volume `/backups/`,
  Rotation 7 Tage.
- Konsistent mit Pattern aus `radiusmanager`.

## 10. Out-of-Scope (v1) — explizit weggelassen

- Einzelne Host-Einträge (Router/Switch pro IP) — passt in `Assignment.notes`,
  wird bei Bedarf später als 4. Modell `Host` ergänzt.
- DHCP/DNS-Sync.
- Ping-/SNMP-Status.
- REST-API.
- Historie/Audit-Log.
- LDAP/AD-Auth.
- IPv6-Blockansicht (Liste reicht).
- Dark-Mode.

## 11. Offene Punkte vor Implementierung

1. Genaue Pool-Definitionen für `45.151.168.0/?` und `185.91.196.0/?` —
   beim User abfragen.
2. Wiki-Dump als Textdatei nach `docs/wiki-export.txt` legen
   (User liefert / kopiert aus aktuellem Wiki).
3. Konfiguration des externen Reverse Proxy für
   `subnetly.kntinternet.de` → Host:8080 (separate Aufgabe, nicht Teil dieses
   Projekts).
