# Subnetly – KNT IP Planer

IP-Subnetz-Dokumentation für KNT-Internet.
Erreichbar unter https://subnetly.kntinternet.de.

## Setup
Siehe `docs/superpowers/specs/2026-05-16-subnetly-design.md` und
`docs/superpowers/plans/2026-05-16-subnetly-implementation.md`.

## Quickstart
```bash
cp .env.example .env
# .env editieren (DJANGO_SECRET_KEY, DB-Passwort, Superuser)
docker compose up -d
docker compose exec web python manage.py import_wiki docs/wiki-export.txt
```
