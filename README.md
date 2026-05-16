# Subnetly – KNT IP Planer

Dokumentation und Verwaltung der IP-Subnetz-Vergaben.
Erreichbar unter <https://subnetly.kntinternet.de> (Reverse Proxy →
`<host>:${NGINX_HOST_PORT}`).

## Stack
Django 5 · PostgreSQL 16 · Gunicorn · nginx · Docker Compose.

## First-run setup

```bash
cd /srv/docker/IP-Planer
cp .env.example .env
$EDITOR .env   # SECRET_KEY, DB_PASSWORD, SUPERUSER_*
docker compose up -d --build
```

Beim ersten Hochfahren werden:
- die DB initialisiert,
- Migrations gefahren (inkl. EXCLUDE-Constraint),
- statische Dateien gesammelt,
- der Superuser aus `DJANGO_SUPERUSER_*` angelegt (idempotent).

Im Browser unter `http://<host>:8080/login/` einloggen.

## Pools anlegen

Über `/admin/`: neuer `Pool` mit CIDR (z.B. `217.61.248.0/23`),
optional `block_prefix` (Auflösung der Blockansicht, z.B. `30`).

## Wiki-Import

1. Wiki-Dump als Textdatei nach `docs/wiki-export.txt` legen.
2. Import laufen lassen:
   ```bash
   docker compose exec web python manage.py import_wiki docs/wiki-export.txt
   ```
   Übersprungene Einträge stehen im Logfile `import_wiki_<ts>.log`
   im Arbeitsverzeichnis des Containers.

## Backups

Container `backup` dumpt täglich um 02:30 nach Volume `db_backups`
(`/backups/subnetly_<ts>.sql.gz`, Rotation 7 Tage).
Restore:

```bash
gunzip -c subnetly_<ts>.sql.gz | docker compose exec -T db psql -U "${DB_USER}" -d "${DB_NAME}"
```

## Tests

```bash
docker compose exec web pytest -v
```

## Reverse-Proxy-Beispiel (nginx, extern)

```nginx
server {
    listen 443 ssl http2;
    server_name subnetly.kntinternet.de;
    # ssl_certificate / ssl_certificate_key ...

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```
