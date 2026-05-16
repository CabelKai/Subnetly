#!/usr/bin/env bash
set -euo pipefail

TS=$(date +%Y-%m-%d_%H%M)
OUT="/backups/subnetly_${TS}.sql.gz"

echo "[backup] starting pg_dump → ${OUT}"
TMP="${OUT}.tmp"
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" -p "${DB_PORT}" \
    -U "${DB_USER}" "${DB_NAME}" \
  | gzip > "${TMP}"
mv "${TMP}" "${OUT}"

# rotation: keep last 7
ls -1t /backups/subnetly_*.sql.gz | tail -n +8 | xargs -r rm --

echo "[backup] done"
