# Subnetly – Notes for Claude

- Django app under `web/`, Docker Compose at repo root.
- Pure services live in `web/ipam/services/` — no Django imports there.
- All views require login (`@login_required`).
- Postgres-specific constraints (overlap-exclusion) are in migration 0002.
- IPv4 pool detail = visual block grid. IPv6 pool detail = list view only.
- Wiki import: idempotent, skip on conflict, log to file.
