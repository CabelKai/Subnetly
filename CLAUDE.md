# Subnetly – Notes for Claude

- Django app under `web/`, Docker Compose at repo root.
- Pure services live in `web/ipam/services/` — no Django imports there.
- All views require login (`@login_required`).
- Postgres-specific constraints (overlap-exclusion) are in migration 0002.
- IPv4 pool detail = visual block grid. IPv6 pool detail = list view only.
- Wiki import: idempotent, skip on conflict, log to file.
- Subnet ↔ Application ist M2M (Migration 0005). Jede IP im Subnet kann
  über `IPAssignment` einer Anwendung zugeordnet werden; `is_gateway` ist
  ein partieller Unique-Constraint (max. ein Gateway pro Subnet).
- Subnet-Edit-Seite zeigt vollständige IP-Liste bis 32 IPs (Cut-off in
  `services/ip_list.FULL_LIST_MAX`), darüber sparse.
- Mobile-Layout: Off-Canvas-Sidebar via Checkbox-Hack (`<input id="nav-toggle">`
  + `peer-checked/drawer:`-Modifier). Breakpoint `md` (768 px). Tables
  (Anwendungs-Liste/-Detail, IPv6 pool) und IP-Liste werden auf <md zu
  Stack-Cards mit Mini-Labels. IPv4-Block-Grid bleibt density-Visualisierung
  mit horizontalem Scroll.
