#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] waiting for database..."
until python -c "import psycopg; psycopg.connect(host='${DB_HOST}', port='${DB_PORT}', user='${DB_USER}', password='${DB_PASSWORD}', dbname='${DB_NAME}')" 2>/dev/null; do
  sleep 1
done

echo "[entrypoint] running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] ensuring superuser..."
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
name = os.environ.get("DJANGO_SUPERUSER_USERNAME")
pwd  = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
mail = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
if name and pwd and not User.objects.filter(username=name).exists():
    User.objects.create_superuser(username=name, password=pwd, email=mail)
    print(f"[entrypoint] superuser '{name}' created")
else:
    print("[entrypoint] superuser already present or env vars missing")
PY

echo "[entrypoint] starting: $*"
exec "$@"
