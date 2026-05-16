# Subnetly – KNT IP Planer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Django web app that documents IP subnet allocations for our network, with a visual block view per pool and a hierarchical sidebar (Pool → Customer → Assignment), deployed via Docker Compose behind an existing reverse proxy at `subnetly.kntinternet.de`.

**Architecture:** Django 5.x + PostgreSQL 16 + Gunicorn + nginx, all in Docker Compose. Three core models (`Pool`, `Customer`, `Assignment`) with DB-level constraints to prevent overlapping subnet assignments. Server-rendered templates with Tailwind CDN. Wiki import runs as a Django management command.

**Tech Stack:**
- Backend: Python 3.12, Django 5.x, gunicorn, psycopg 3
- DB: PostgreSQL 16 with `django-netfields` for native `inet`/`cidr` types
- Frontend: Django templates + Tailwind CSS via CDN (no Node build)
- Tests: pytest + pytest-django
- Deploy: Docker Compose (`web`, `nginx`, `db`, `backup`)

**Spec:** `/srv/docker/IP-Planer/docs/superpowers/specs/2026-05-16-subnetly-design.md`

---

## File Structure

```
/srv/docker/IP-Planer/
├── .env.example                       # Env var template
├── .gitignore
├── docker-compose.yml                 # Services: web, nginx, db, backup
├── README.md                          # Setup + ops instructions
├── CLAUDE.md                          # Notes for future Claude sessions
├── nginx/
│   └── default.conf                   # vhost: /static/ + proxy to web:8000
├── backup/
│   ├── Dockerfile                     # alpine + postgresql-client + cron
│   └── backup.sh                      # pg_dump + rotation
├── web/
│   ├── Dockerfile                     # python:3.12-slim + deps + app
│   ├── entrypoint.sh                  # migrate, collectstatic, ensure superuser, exec gunicorn
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── manage.py
│   ├── subnetly/                      # Project package
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py                    # includes ipam.urls + auth + admin
│   │   └── wsgi.py
│   └── ipam/                          # App package
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py                  # Pool, Customer, Assignment
│       ├── admin.py
│       ├── forms.py                   # AssignmentForm
│       ├── views.py                   # All HTTP views (small file, OK)
│       ├── urls.py
│       ├── context_processors.py      # sidebar_tree
│       ├── services/
│       │   ├── __init__.py
│       │   ├── blocks.py              # render_pool_blocks() pure logic
│       │   ├── colors.py              # color_for(customer_name) hash-based
│       │   └── wiki_parser.py         # parse(text) -> list of dicts, pure
│       ├── management/
│       │   ├── __init__.py
│       │   └── commands/
│       │       ├── __init__.py
│       │       └── import_wiki.py     # CLI wrapper around wiki_parser
│       ├── migrations/
│       │   ├── 0001_initial.py        # auto-generated
│       │   └── 0002_overlap_constraint.py  # RunSQL: EXCLUDE USING gist
│       ├── templates/
│       │   ├── base.html              # header + sidebar + main slot
│       │   ├── index.html             # pool overview cards
│       │   ├── pool_detail.html       # IPv4 block grid OR IPv6 list (branch)
│       │   ├── customer_list.html
│       │   ├── customer_detail.html
│       │   ├── assignment_form.html
│       │   └── registration/
│       │       └── login.html
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py
│           ├── test_models.py
│           ├── test_blocks.py
│           ├── test_wiki_parser.py
│           ├── test_views.py
│           └── fixtures/
│               └── wiki_sample.txt
└── docs/
    ├── wiki-export.txt                # user-supplied initial dump
    └── superpowers/
        ├── specs/2026-05-16-subnetly-design.md
        └── plans/2026-05-16-subnetly-implementation.md
```

**Boundaries**
- `services/blocks.py`, `services/colors.py`, `services/wiki_parser.py` are pure
  functions over plain data — no DB access, no Django imports. This keeps them
  trivially testable.
- `views.py` orchestrates: query models, call services, render template.
- `models.py` owns DB schema and validation rules (`clean()`, constraints).
- `management/commands/import_wiki.py` is a thin CLI wrapper that reads a file,
  calls `wiki_parser.parse()`, and writes results to the DB inside a
  transaction.

---

## Conventions used throughout the plan

- All commands run inside `/srv/docker/IP-Planer/` unless otherwise noted.
- `docker compose exec web <cmd>` is how we run Django/pytest commands once
  containers are up. Until Task 4 they aren't running yet, so early tasks use
  a host-side `python` after creating a venv (see Task 3).
- Commits use Conventional Commits (`feat:`, `chore:`, `test:`).
- Every model/service test uses pytest fixtures from `conftest.py`. The
  `db` fixture from pytest-django gives a transactional test DB.

---

## Phase 1 — Bootstrap

### Task 1: Repo skeleton and git init

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: directory layout (empty dirs with `.gitkeep`)

- [ ] **Step 1: Initialize git and create .gitignore**

```bash
cd /srv/docker/IP-Planer
git init
```

Create `.gitignore`:

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
.pytest_cache/
.venv/
venv/

# Django
*.log
db.sqlite3
/web/staticfiles/
/web/media/

# Env / secrets
.env
.env.local

# OS
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/
```

- [ ] **Step 2: Create README.md**

Create `README.md` with minimal stub:

```markdown
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
```

- [ ] **Step 3: Create CLAUDE.md**

Create `CLAUDE.md`:

```markdown
# Subnetly – Notes for Claude

- Django app under `web/`, Docker Compose at repo root.
- Pure services live in `web/ipam/services/` — no Django imports there.
- All views require login (`@login_required`).
- Postgres-specific constraints (overlap-exclusion) are in migration 0002.
- IPv4 pool detail = visual block grid. IPv6 pool detail = list view only.
- Wiki import: idempotent, skip on conflict, log to file.
```

- [ ] **Step 4: Create empty directory skeleton**

```bash
mkdir -p nginx backup web/subnetly web/ipam/{services,management/commands,migrations,templates/registration,tests/fixtures} docs
touch web/ipam/services/.gitkeep
touch web/ipam/management/.gitkeep
touch web/ipam/management/commands/.gitkeep
touch web/ipam/migrations/.gitkeep
touch web/ipam/templates/.gitkeep
touch web/ipam/templates/registration/.gitkeep
touch web/ipam/tests/fixtures/.gitkeep
touch nginx/.gitkeep backup/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore README.md CLAUDE.md nginx/ backup/ web/ docs/
git commit -m "chore: initialize subnetly repo skeleton"
```

---

### Task 2: Docker Compose stack (db, web, nginx, backup)

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `web/Dockerfile`
- Create: `web/entrypoint.sh`
- Create: `web/requirements.txt`
- Create: `nginx/default.conf`
- Create: `backup/Dockerfile`
- Create: `backup/backup.sh`

- [ ] **Step 1: Write requirements.txt**

Create `web/requirements.txt`:

```
Django>=5.0,<6.0
psycopg[binary]>=3.1,<4.0
gunicorn>=21.2,<23.0
django-netfields>=1.3,<2.0
pytest>=8.0,<9.0
pytest-django>=4.8,<5.0
```

- [ ] **Step 2: Write web/Dockerfile**

Create `web/Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "subnetly.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

- [ ] **Step 3: Write entrypoint.sh**

Create `web/entrypoint.sh`:

```bash
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
```

- [ ] **Step 4: Write nginx/default.conf**

Create `nginx/default.conf`:

```nginx
upstream subnetly_web {
    server web:8000;
}

server {
    listen 80;
    server_name _;

    client_max_body_size 5M;

    location /static/ {
        alias /static/;
        expires 7d;
        access_log off;
    }

    location / {
        proxy_pass http://subnetly_web;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
        proxy_read_timeout 60s;
    }
}
```

- [ ] **Step 5: Write backup/Dockerfile and backup.sh**

Create `backup/Dockerfile`:

```dockerfile
FROM postgres:16-alpine

RUN apk add --no-cache bash dcron tini

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

# crontab: daily at 02:30
RUN echo "30 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1" > /etc/crontabs/root

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["crond", "-f", "-d", "8"]
```

Create `backup/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

TS=$(date +%Y-%m-%d_%H%M)
OUT="/backups/subnetly_${TS}.sql.gz"

echo "[backup] starting pg_dump → ${OUT}"
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" -p "${DB_PORT}" \
    -U "${DB_USER}" "${DB_NAME}" \
  | gzip > "${OUT}"

# rotation: keep last 7
ls -1t /backups/subnetly_*.sql.gz | tail -n +8 | xargs -r rm --

echo "[backup] done"
```

- [ ] **Step 6: Write .env.example**

Create `.env.example`:

```bash
# Django
DJANGO_SECRET_KEY=change-me-to-a-long-random-string
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=subnetly.kntinternet.de,localhost

# Initial superuser (only used on first run)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=change-me
DJANGO_SUPERUSER_EMAIL=admin@kntinternet.de

# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=subnetly
DB_USER=subnetly
DB_PASSWORD=change-me

# Reverse proxy reaches nginx on this host port
NGINX_HOST_PORT=8080
```

- [ ] **Step 7: Write docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 5s
      timeout: 5s
      retries: 10

  web:
    build: ./web
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
      DJANGO_DEBUG: ${DJANGO_DEBUG}
      DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS}
      DJANGO_SUPERUSER_USERNAME: ${DJANGO_SUPERUSER_USERNAME}
      DJANGO_SUPERUSER_PASSWORD: ${DJANGO_SUPERUSER_PASSWORD}
      DJANGO_SUPERUSER_EMAIL: ${DJANGO_SUPERUSER_EMAIL}
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT}
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
    volumes:
      - static_files:/app/staticfiles
      - ./docs:/app/docs:ro

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    depends_on:
      - web
    ports:
      - "${NGINX_HOST_PORT}:80"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - static_files:/static:ro

  backup:
    build: ./backup
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT}
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_backups:/backups

volumes:
  db_data:
  static_files:
  db_backups:
```

- [ ] **Step 8: Verify docker compose config**

```bash
cd /srv/docker/IP-Planer
cp .env.example .env
docker compose config > /dev/null
```

Expected: no errors (file parses, env vars substituted).

- [ ] **Step 9: Commit**

```bash
git add docker-compose.yml .env.example web/Dockerfile web/entrypoint.sh web/requirements.txt nginx/default.conf backup/Dockerfile backup/backup.sh
git commit -m "feat: add docker compose stack (db, web, nginx, backup)"
```

---

### Task 3: Django project + ipam app + pytest config

**Files:**
- Create: `web/manage.py`
- Create: `web/subnetly/__init__.py`
- Create: `web/subnetly/settings.py`
- Create: `web/subnetly/urls.py`
- Create: `web/subnetly/wsgi.py`
- Create: `web/ipam/__init__.py`
- Create: `web/ipam/apps.py`
- Create: `web/ipam/urls.py`
- Create: `web/ipam/views.py`
- Create: `web/ipam/models.py` (empty for now)
- Create: `web/pytest.ini`
- Create: `web/ipam/tests/__init__.py`
- Create: `web/ipam/tests/conftest.py`

- [ ] **Step 1: Write manage.py**

Create `web/manage.py`:

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "subnetly.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write subnetly/settings.py**

Create `web/subnetly/__init__.py` (empty file).

Create `web/subnetly/settings.py`:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",") if h.strip()
]

# Reverse-proxy support
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "netfields",
    "ipam",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "subnetly.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ipam.context_processors.sidebar_tree",
            ],
        },
    },
]

WSGI_APPLICATION = "subnetly.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "subnetly"),
        "USER": os.environ.get("DB_USER", "subnetly"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
```

- [ ] **Step 3: Write subnetly/urls.py and wsgi.py**

Create `web/subnetly/urls.py`:

```python
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", include("ipam.urls")),
]
```

Create `web/subnetly/wsgi.py`:

```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "subnetly.settings")
application = get_wsgi_application()
```

- [ ] **Step 4: Write ipam app skeleton**

Create `web/ipam/__init__.py` (empty).

Create `web/ipam/apps.py`:

```python
from django.apps import AppConfig


class IpamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ipam"
```

Create `web/ipam/models.py`:

```python
# Models defined in Task 5+
```

Create `web/ipam/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def index(request):
    return HttpResponse("Subnetly placeholder")
```

Create `web/ipam/urls.py`:

```python
from django.urls import path

from . import views

app_name = "ipam"

urlpatterns = [
    path("", views.index, name="index"),
]
```

Create `web/ipam/context_processors.py`:

```python
def sidebar_tree(request):
    # Filled in Task 12
    return {"sidebar_pools": []}
```

- [ ] **Step 5: Write pytest config**

Create `web/pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = subnetly.settings
python_files = test_*.py
testpaths = ipam/tests
```

Create `web/ipam/tests/__init__.py` (empty).

Create `web/ipam/tests/conftest.py`:

```python
# Shared fixtures will live here (filled in Task 5+).
```

- [ ] **Step 6: Commit**

```bash
git add web/manage.py web/subnetly/ web/ipam/ web/pytest.ini
git commit -m "feat: scaffold django project and ipam app"
```

---

### Task 4: First container start + smoke test

**Files:** none (verification only).

- [ ] **Step 1: Build images**

```bash
cd /srv/docker/IP-Planer
docker compose build
```

Expected: builds complete without errors.

- [ ] **Step 2: Start stack**

```bash
docker compose up -d
docker compose logs -f web
```

Expected (in `web` logs): wait-for-db → migrate → collectstatic → superuser
created → "starting: gunicorn ...". Press Ctrl-C to stop following logs.

- [ ] **Step 3: Smoke test login page**

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8080/login/
```

Expected: `200`.

- [ ] **Step 4: Smoke test that index requires login**

```bash
curl -sS -o /dev/null -w "%{http_code} %{redirect_url}\n" http://localhost:8080/
```

Expected: `302 .../login/?next=/` (redirected to login).

- [ ] **Step 5: Run pytest inside container**

```bash
docker compose exec web pytest -v
```

Expected: `no tests collected` (0 tests so far). No errors.

- [ ] **Step 6: Commit (no code changes — verification milestone)**

No commit needed; tag the working state instead:

```bash
git tag -a milestone-bootstrap -m "stack boots, db reachable, login page served"
```

---

## Phase 2 — Data Model

### Task 5: Pool model + tests

**Files:**
- Modify: `web/ipam/models.py`
- Modify: `web/ipam/tests/conftest.py`
- Create: `web/ipam/tests/test_models.py`

- [ ] **Step 1: Write failing test for Pool creation and ip_version auto-set**

Replace `web/ipam/tests/conftest.py` with:

```python
import pytest


@pytest.fixture
def pool_v4(db):
    from ipam.models import Pool
    return Pool.objects.create(
        name="Anycast 217.61.248.0/23",
        cidr="217.61.248.0/23",
        block_prefix=30,
    )


@pytest.fixture
def pool_v6(db):
    from ipam.models import Pool
    return Pool.objects.create(
        name="IPv6 2a05:ed80:100::/48",
        cidr="2a05:ed80:100::/48",
    )
```

Create `web/ipam/tests/test_models.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ipam.models import Assignment, Customer, Pool


@pytest.mark.django_db
def test_pool_v4_auto_sets_ip_version(pool_v4):
    assert pool_v4.ip_version == 4


@pytest.mark.django_db
def test_pool_v6_auto_sets_ip_version(pool_v6):
    assert pool_v6.ip_version == 6


@pytest.mark.django_db
def test_pool_cidr_unique(pool_v4):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pool.objects.create(name="dup", cidr="217.61.248.0/23")
```

- [ ] **Step 2: Run test to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: errors — `Pool`, `Customer`, `Assignment` don't exist yet.

- [ ] **Step 3: Write Pool model**

Replace `web/ipam/models.py`:

```python
from django.db import models
from netfields import CidrAddressField, NetManager


class Pool(models.Model):
    name = models.CharField(max_length=100)
    cidr = CidrAddressField(unique=True)
    ip_version = models.PositiveSmallIntegerField(editable=False)
    block_prefix = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="IPv4 only: prefix length of one grid cell, e.g. 30",
    )
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]

    def save(self, *args, **kwargs):
        self.ip_version = self.cidr.version
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.cidr})"
```

- [ ] **Step 4: Generate and apply migration**

```bash
docker compose exec web python manage.py makemigrations ipam
docker compose exec web python manage.py migrate
```

Expected: `0001_initial.py` created; migration applied.

- [ ] **Step 5: Re-run tests**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: the two ip_version tests pass; the unique test will only pass once
Customer/Assignment exist (collection error). To fix collection-time
`ImportError`s, add temporary stub classes:

In `web/ipam/models.py`, append:

```python
class Customer(models.Model):
    name = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Assignment(models.Model):
    # Full definition in Task 7
    pool = models.ForeignKey(Pool, on_delete=models.PROTECT, related_name="assignments")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="assignments")
    cidr = CidrAddressField()
    gateway = models.GenericIPAddressField(null=True, blank=True)
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]
```

Re-run `makemigrations` + `migrate` and tests:

```bash
docker compose exec web python manage.py makemigrations ipam
docker compose exec web python manage.py migrate
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: 3/3 pass.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/models.py web/ipam/migrations/ web/ipam/tests/
git commit -m "feat(ipam): add Pool, Customer, Assignment models (basic fields)"
```

---

### Task 6: Customer + Assignment basic tests

**Files:**
- Modify: `web/ipam/tests/test_models.py`

- [ ] **Step 1: Add failing tests for Customer + Assignment basics**

Append to `web/ipam/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_customer_name_unique():
    Customer.objects.create(name="BINSS")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Customer.objects.create(name="BINSS")


@pytest.mark.django_db
def test_assignment_basic_create(pool_v4):
    c = Customer.objects.create(name="BINSS")
    a = Assignment.objects.create(
        pool=pool_v4,
        customer=c,
        cidr="217.61.249.0/28",
        gateway="217.61.249.1",
        notes="Router .1, Switch .2",
    )
    assert a.cidr.prefixlen == 28
    assert str(a.gateway) == "217.61.249.1"


@pytest.mark.django_db
def test_assignment_orders_by_cidr(pool_v4):
    c = Customer.objects.create(name="X")
    Assignment.objects.create(pool=pool_v4, customer=c, cidr="217.61.249.16/28")
    Assignment.objects.create(pool=pool_v4, customer=c, cidr="217.61.249.0/28")
    cidrs = [str(a.cidr) for a in pool_v4.assignments.all()]
    assert cidrs == ["217.61.249.0/28", "217.61.249.16/28"]
```

- [ ] **Step 2: Run tests**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: 6/6 pass (no model changes needed — fields already exist from Task 5).

- [ ] **Step 3: Commit**

```bash
git add web/ipam/tests/test_models.py
git commit -m "test(ipam): cover Customer uniqueness and Assignment basics"
```

---

### Task 7: CIDR-in-pool validation (application level)

**Files:**
- Modify: `web/ipam/models.py`
- Modify: `web/ipam/tests/test_models.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_assignment_must_be_inside_pool(pool_v4):
    c = Customer.objects.create(name="Outsider")
    a = Assignment(pool=pool_v4, customer=c, cidr="10.0.0.0/24")
    with pytest.raises(ValidationError) as exc:
        a.full_clean()
    assert "innerhalb" in str(exc.value).lower() or "inside" in str(exc.value).lower()


@pytest.mark.django_db
def test_assignment_ip_family_must_match_pool(pool_v4):
    c = Customer.objects.create(name="V6User")
    a = Assignment(pool=pool_v4, customer=c, cidr="2a05:ed80:100:1::/64")
    with pytest.raises(ValidationError):
        a.full_clean()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: two new tests FAIL (no validation yet).

- [ ] **Step 3: Implement clean() on Assignment**

In `web/ipam/models.py`, replace the `Assignment` class body with:

```python
class Assignment(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.PROTECT, related_name="assignments")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="assignments")
    cidr = CidrAddressField()
    gateway = models.GenericIPAddressField(null=True, blank=True)
    notes = models.TextField(blank=True)

    objects = NetManager()

    class Meta:
        ordering = ["cidr"]

    def clean(self):
        super().clean()
        if not self.pool_id or self.cidr is None:
            return
        from netaddr import IPNetwork
        pool_net = IPNetwork(str(self.pool.cidr))
        ass_net = IPNetwork(str(self.cidr))
        if pool_net.version != ass_net.version:
            raise ValidationError(
                {"cidr": f"IP-Familie passt nicht zum Pool (Pool ist IPv{pool_net.version})."}
            )
        if ass_net not in pool_net:
            raise ValidationError(
                {"cidr": f"{self.cidr} liegt nicht innerhalb des Pools {self.pool.cidr}."}
            )

    def __str__(self):
        return f"{self.cidr} → {self.customer.name}"
```

Add the import at the top of `models.py`:

```python
from django.core.exceptions import ValidationError
```

- [ ] **Step 4: Re-run tests**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: 8/8 pass.

- [ ] **Step 5: Commit**

```bash
git add web/ipam/models.py web/ipam/tests/test_models.py
git commit -m "feat(ipam): validate assignment CIDR is inside parent pool"
```

---

### Task 8: Overlap constraint (DB-level, Postgres EXCLUDE)

**Files:**
- Create: `web/ipam/migrations/0002_overlap_constraint.py`
- Modify: `web/ipam/tests/test_models.py`

- [ ] **Step 1: Write failing test for overlap rejection**

Append to `web/ipam/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_assignments_in_same_pool_cannot_overlap(pool_v4):
    c1 = Customer.objects.create(name="A")
    c2 = Customer.objects.create(name="B")
    Assignment.objects.create(pool=pool_v4, customer=c1, cidr="217.61.249.0/28")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(pool=pool_v4, customer=c2, cidr="217.61.249.8/29")


@pytest.mark.django_db
def test_assignments_in_different_pools_can_overlap_logically(pool_v4, pool_v6):
    # Different pools = different rows in the EXCLUDE constraint partition,
    # so logically overlapping CIDRs in unrelated pools are allowed.
    # Use CIDRs that match each pool's family.
    c = Customer.objects.create(name="Z")
    Assignment.objects.create(pool=pool_v4, customer=c, cidr="217.61.249.0/28")
    Assignment.objects.create(pool=pool_v6, customer=c, cidr="2a05:ed80:100:1::/64")
```

- [ ] **Step 2: Run tests to verify the overlap test fails**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: `test_assignments_in_same_pool_cannot_overlap` FAILS (no constraint yet).

- [ ] **Step 3: Write the migration**

Create `web/ipam/migrations/0002_overlap_constraint.py`:

```python
from django.db import migrations


SQL_FORWARD = """
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE ipam_assignment
ADD CONSTRAINT ipam_assignment_no_overlap
EXCLUDE USING gist (
    pool_id WITH =,
    cidr inet_ops WITH &&
);
"""

SQL_REVERSE = """
ALTER TABLE ipam_assignment
DROP CONSTRAINT IF EXISTS ipam_assignment_no_overlap;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("ipam", "0001_initial"),
    ]
    operations = [
        migrations.RunSQL(SQL_FORWARD, reverse_sql=SQL_REVERSE),
    ]
```

Note: if your `0001_initial` filename differs (e.g. Django created a second
auto-migration in Task 5/6), depend on the latest one — adjust the
`dependencies` tuple accordingly. Verify with:

```bash
docker compose exec web ls ipam/migrations/
```

- [ ] **Step 4: Apply migration**

```bash
docker compose exec web python manage.py migrate
```

Expected: migration applies cleanly.

- [ ] **Step 5: Re-run tests**

```bash
docker compose exec web pytest ipam/tests/test_models.py -v
```

Expected: 10/10 pass.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/migrations/0002_overlap_constraint.py web/ipam/tests/test_models.py
git commit -m "feat(ipam): DB-level EXCLUDE constraint preventing overlaps in same pool"
```

---

### Task 9: Django admin registration

**Files:**
- Create: `web/ipam/admin.py`

- [ ] **Step 1: Register models**

Create `web/ipam/admin.py`:

```python
from django.contrib import admin

from .models import Assignment, Customer, Pool


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "cidr", "ip_version", "block_prefix")
    search_fields = ("name", "cidr")
    readonly_fields = ("ip_version",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("cidr", "pool", "customer", "gateway")
    list_filter = ("pool", "customer")
    search_fields = ("cidr", "notes", "customer__name")
    autocomplete_fields = ("pool", "customer")
```

- [ ] **Step 2: Verify admin loads**

```bash
docker compose exec web python manage.py check
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8080/admin/login/
```

Expected: `check` reports no issues; HTTP `200`.

- [ ] **Step 3: Commit**

```bash
git add web/ipam/admin.py
git commit -m "feat(ipam): register Pool, Customer, Assignment in admin"
```

---

## Phase 3 — Auth + Layout

### Task 10: Login template + base layout + Tailwind

**Files:**
- Create: `web/ipam/templates/base.html`
- Create: `web/ipam/templates/registration/login.html`

- [ ] **Step 1: Write base.html**

Create `web/ipam/templates/base.html`:

```html
<!doctype html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Subnetly{% endblock %} – KNT IP Planer</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900">
<header class="bg-slate-800 text-slate-100 px-6 py-3 flex justify-between items-center">
    <a href="{% url 'ipam:index' %}" class="text-lg font-semibold">Subnetly – KNT IP Planer</a>
    <div>
        {% if user.is_authenticated %}
            <span class="text-sm mr-3">{{ user.username }}</span>
            <form action="{% url 'logout' %}" method="post" class="inline">
                {% csrf_token %}
                <button class="bg-slate-700 hover:bg-slate-600 px-3 py-1 rounded text-sm">Logout</button>
            </form>
        {% endif %}
    </div>
</header>
<div class="flex" style="min-height: calc(100vh - 56px);">
    {% if user.is_authenticated %}
    <aside class="w-72 bg-white border-r border-slate-200 p-3 overflow-y-auto text-sm">
        {% include "_sidebar.html" %}
    </aside>
    {% endif %}
    <main class="flex-1 p-6 overflow-x-auto">
        {% block content %}{% endblock %}
    </main>
</div>
</body>
</html>
```

- [ ] **Step 2: Write empty _sidebar.html (filled in Task 12)**

Create `web/ipam/templates/_sidebar.html`:

```html
{% for pool in sidebar_pools %}
    <details class="mb-2" open>
        <summary class="cursor-pointer font-mono">{{ pool.cidr }}</summary>
        <div class="pl-3 mt-1">
            {% for c in pool.customers %}
                <details class="mb-1">
                    <summary class="cursor-pointer">{{ c.name }}</summary>
                    <ul class="pl-4 mt-1 text-xs font-mono text-slate-600">
                        {% for a in c.assignments %}
                            <li>{{ a.cidr }}</li>
                        {% endfor %}
                    </ul>
                </details>
            {% endfor %}
        </div>
    </details>
{% empty %}
    <p class="text-slate-500 italic">Noch keine Pools angelegt.</p>
{% endfor %}
```

- [ ] **Step 3: Write login.html**

Create `web/ipam/templates/registration/login.html`:

```html
{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block content %}
<div class="max-w-sm mx-auto mt-12 bg-white p-6 rounded shadow">
    <h1 class="text-xl font-semibold mb-4">Login</h1>
    {% if form.errors %}
        <p class="text-red-600 mb-3">Anmeldung fehlgeschlagen.</p>
    {% endif %}
    <form method="post">
        {% csrf_token %}
        <label class="block mb-2 text-sm">Benutzername
            <input type="text" name="username" class="w-full border rounded px-2 py-1" autofocus>
        </label>
        <label class="block mb-4 text-sm">Passwort
            <input type="password" name="password" class="w-full border rounded px-2 py-1">
        </label>
        <button class="bg-slate-800 text-white px-4 py-2 rounded w-full">Anmelden</button>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 4: Verify login renders**

```bash
docker compose restart web
curl -sS http://localhost:8080/login/ | grep -q "KNT IP Planer"
echo $?
```

Expected: `0` (grep found the string).

- [ ] **Step 5: Commit**

```bash
git add web/ipam/templates/
git commit -m "feat(ui): add base layout, sidebar shell, login page"
```

---

### Task 11: Sidebar context processor

**Files:**
- Modify: `web/ipam/context_processors.py`
- Create: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Create `web/ipam/tests/test_views.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from ipam.models import Assignment, Customer, Pool


@pytest.fixture
def auth_client(db, client):
    User = get_user_model()
    User.objects.create_user(username="tester", password="pw")
    client.login(username="tester", password="pw")
    return client


@pytest.mark.django_db
def test_sidebar_groups_assignments_by_pool_then_customer(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.248.0/23", block_prefix=30)
    c1 = Customer.objects.create(name="BINSS")
    c2 = Customer.objects.create(name="Falcon")
    Assignment.objects.create(pool=p, customer=c1, cidr="217.61.249.0/28")
    Assignment.objects.create(pool=p, customer=c1, cidr="217.61.249.16/28")
    Assignment.objects.create(pool=p, customer=c2, cidr="217.61.249.32/29")

    response = auth_client.get("/")
    body = response.content.decode()

    # Each pool listed once
    assert body.count("217.61.248.0/23") == 1
    # Each customer listed once per pool
    assert body.count(">BINSS<") == 1
    assert body.count(">Falcon<") == 1
    # All three assignments visible
    assert "217.61.249.0/28" in body
    assert "217.61.249.16/28" in body
    assert "217.61.249.32/29" in body
```

- [ ] **Step 2: Run test to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v
```

Expected: FAIL — `sidebar_tree` returns empty list.

- [ ] **Step 3: Implement sidebar_tree**

Replace `web/ipam/context_processors.py`:

```python
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List

from .models import Assignment, Pool


@dataclass
class _CustomerNode:
    name: str
    assignments: List[Assignment] = field(default_factory=list)


@dataclass
class _PoolNode:
    cidr: str
    name: str
    id: int
    ip_version: int
    customers: List[_CustomerNode] = field(default_factory=list)


def sidebar_tree(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"sidebar_pools": []}

    pools = list(Pool.objects.all())
    assignments = (
        Assignment.objects
        .select_related("pool", "customer")
        .order_by("pool__cidr", "customer__name", "cidr")
    )

    by_pool = OrderedDict()
    for p in pools:
        by_pool[p.id] = _PoolNode(
            cidr=str(p.cidr), name=p.name, id=p.id, ip_version=p.ip_version
        )

    for a in assignments:
        pool_node = by_pool[a.pool_id]
        if not pool_node.customers or pool_node.customers[-1].name != a.customer.name:
            pool_node.customers.append(_CustomerNode(name=a.customer.name))
        pool_node.customers[-1].assignments.append(a)

    return {"sidebar_pools": list(by_pool.values())}
```

- [ ] **Step 4: Re-run test**

```bash
docker compose exec web pytest ipam/tests/test_views.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/ipam/context_processors.py web/ipam/tests/test_views.py
git commit -m "feat(ui): sidebar context processor groups assignments by pool→customer"
```

---

### Task 12: Pool overview page (index)

**Files:**
- Modify: `web/ipam/views.py`
- Create: `web/ipam/templates/index.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_index_shows_pool_card_with_utilization(auth_client):
    p = Pool.objects.create(name="Anycast", cidr="217.61.248.0/23", block_prefix=30)
    c = Customer.objects.create(name="X")
    # 16 of 512 IPs = 3.125% utilization
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/28")

    response = auth_client.get("/")
    body = response.content.decode()

    assert "Anycast" in body
    assert "217.61.248.0/23" in body
    assert "3" in body  # rounded percent appears somewhere
```

- [ ] **Step 2: Run test to verify failure**

Expected: FAIL — current `index` returns plain "Subnetly placeholder".

- [ ] **Step 3: Implement index view**

Replace `web/ipam/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from netaddr import IPNetwork

from .models import Pool


def _pool_utilization_percent(pool: Pool) -> int:
    pool_net = IPNetwork(str(pool.cidr))
    total = pool_net.size
    used = sum(IPNetwork(str(a.cidr)).size for a in pool.assignments.all())
    return round(used * 100 / total) if total else 0


@login_required
def index(request):
    pools = list(Pool.objects.prefetch_related("assignments"))
    cards = [
        {
            "pool": p,
            "utilization": _pool_utilization_percent(p),
            "assignment_count": p.assignments.count(),
        }
        for p in pools
    ]
    return render(request, "index.html", {"cards": cards})
```

Create `web/ipam/templates/index.html`:

```html
{% extends "base.html" %}
{% block title %}Übersicht{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-4">Pool-Übersicht</h1>
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {% for card in cards %}
    <a href="{% url 'ipam:pool_detail' card.pool.id %}" class="bg-white rounded shadow p-4 hover:shadow-md">
        <div class="text-xs text-slate-500">IPv{{ card.pool.ip_version }}</div>
        <div class="font-semibold">{{ card.pool.name }}</div>
        <div class="font-mono text-sm text-slate-600">{{ card.pool.cidr }}</div>
        <div class="mt-3">
            <div class="text-xs text-slate-500 mb-1">{{ card.utilization }}% belegt · {{ card.assignment_count }} Subnetz(e)</div>
            <div class="h-2 bg-slate-200 rounded overflow-hidden">
                <div class="h-full bg-slate-700" style="width: {{ card.utilization }}%"></div>
            </div>
        </div>
    </a>
    {% empty %}
    <p class="text-slate-500">Noch keine Pools. Im <a href="/admin/" class="underline">Admin</a> anlegen.</p>
    {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 4: Register pool_detail route placeholder so {% url %} resolves**

Replace `web/ipam/urls.py`:

```python
from django.urls import path

from . import views

app_name = "ipam"

urlpatterns = [
    path("", views.index, name="index"),
    path("pool/<int:pool_id>/", views.pool_detail, name="pool_detail"),
]
```

In `web/ipam/views.py`, append:

```python
from django.shortcuts import get_object_or_404


@login_required
def pool_detail(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    return render(request, "pool_detail.html", {"pool": pool})
```

Create empty placeholder `web/ipam/templates/pool_detail.html`:

```html
{% extends "base.html" %}
{% block content %}<h1>{{ pool.name }}</h1>{% endblock %}
```

- [ ] **Step 5: Re-run tests**

```bash
docker compose exec web pytest ipam/tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/views.py web/ipam/urls.py web/ipam/templates/index.html web/ipam/templates/pool_detail.html web/ipam/tests/test_views.py
git commit -m "feat(ui): pool overview page with utilization cards"
```

---

## Phase 4 — Block Service + Pool Detail (Core Feature)

### Task 13: Block-rendering service (pure logic)

**Files:**
- Create: `web/ipam/services/__init__.py`
- Create: `web/ipam/services/blocks.py`
- Create: `web/ipam/services/colors.py`
- Create: `web/ipam/tests/test_blocks.py`

- [ ] **Step 1: Write failing tests**

Create `web/ipam/services/__init__.py` (empty).

Create `web/ipam/tests/test_blocks.py`:

```python
import pytest
from netaddr import IPNetwork

from ipam.services.blocks import compute_blocks
from ipam.services.colors import color_for


def _assigned(cidr, label):
    return {"cidr": IPNetwork(cidr), "label": label}


def test_no_assignments_is_one_free_block():
    blocks = compute_blocks(IPNetwork("217.61.248.0/30"), [])
    assert len(blocks) == 1
    b = blocks[0]
    assert b["kind"] == "free"
    assert b["cidr"] == IPNetwork("217.61.248.0/30")
    assert b["span"] == 1  # block_prefix == pool prefix → 1 cell


def test_fully_assigned_pool_has_no_free_block():
    pool = IPNetwork("217.61.248.0/30")  # 4 IPs
    blocks = compute_blocks(pool, [_assigned("217.61.248.0/30", "X")])
    assert len(blocks) == 1
    assert blocks[0]["kind"] == "assigned"
    assert blocks[0]["span"] == 1


def test_assignment_in_middle_creates_three_blocks():
    pool = IPNetwork("217.61.248.0/28")  # 16 IPs, block_prefix=30 → 4 cells
    blocks = compute_blocks(pool, [_assigned("217.61.248.4/30", "X")], block_prefix=30)
    kinds = [b["kind"] for b in blocks]
    assert kinds == ["free", "assigned", "free"]
    # spans: free .0-.3 = 1 cell; assigned .4-.7 = 1 cell; free .8-.15 = 2 cells
    assert [b["span"] for b in blocks] == [1, 1, 2]


def test_larger_assignment_spans_multiple_cells():
    pool = IPNetwork("217.61.248.0/25")  # 128 IPs, block_prefix=30 → 32 cells
    blocks = compute_blocks(
        pool,
        [_assigned("217.61.248.0/28", "BINSS")],  # 16 IPs → 4 cells
        block_prefix=30,
    )
    assert blocks[0]["kind"] == "assigned"
    assert blocks[0]["span"] == 4
    # 16-127 = 112 IPs free = 28 cells, expressed as one block
    assert blocks[1]["kind"] == "free"
    assert blocks[1]["span"] == 28


def test_free_gap_between_two_assignments():
    pool = IPNetwork("217.61.249.0/28")  # 16 IPs, block_prefix=30 → 4 cells
    blocks = compute_blocks(
        pool,
        [
            _assigned("217.61.249.0/30", "A"),
            _assigned("217.61.249.8/30", "B"),
        ],
        block_prefix=30,
    )
    assert [b["kind"] for b in blocks] == ["assigned", "free", "assigned", "free"]
    assert [b["span"] for b in blocks] == [1, 1, 1, 1]


def test_color_stable_for_same_name():
    assert color_for("BINSS") == color_for("BINSS")
    assert color_for("BINSS") != color_for("Falcon")


def test_color_returns_hex():
    c = color_for("X")
    assert c.startswith("#") and len(c) == 7
```

- [ ] **Step 2: Run tests to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_blocks.py -v
```

Expected: collection error — `blocks` module doesn't exist.

- [ ] **Step 3: Implement colors.py**

Create `web/ipam/services/colors.py`:

```python
import hashlib

# Palette tuned for readable text on these backgrounds
_PALETTE = [
    "#FCA5A5", "#FDBA74", "#FCD34D", "#A7F3D0", "#86EFAC",
    "#7DD3FC", "#A5B4FC", "#C4B5FD", "#F0ABFC", "#FDA4AF",
    "#FEF08A", "#BEF264", "#67E8F9", "#93C5FD", "#D8B4FE",
]


def color_for(name: str) -> str:
    """Stable color hex for a customer name."""
    if not name:
        return "#E5E7EB"
    h = hashlib.md5(name.encode("utf-8")).digest()
    return _PALETTE[h[0] % len(_PALETTE)]
```

- [ ] **Step 4: Implement blocks.py**

Create `web/ipam/services/blocks.py`:

```python
from typing import List, Optional

from netaddr import IPNetwork


def compute_blocks(
    pool: IPNetwork,
    assignments: List[dict],
    block_prefix: Optional[int] = None,
) -> List[dict]:
    """Compute block list for a pool's visual grid.

    Each assignment is a dict with at least:
      - 'cidr': IPNetwork
      - 'label': str
    Returns list of dicts:
      - {'kind': 'assigned', 'cidr': IPNetwork, 'label': str, 'span': int}
      - {'kind': 'free',     'cidr': IPNetwork, 'span': int, 'size': int}

    `block_prefix` is the cell-size prefix length (e.g. 30 = each cell is /30).
    Defaults to the pool's own prefix length (= 1 cell total).
    `span` is the number of grid cells the block occupies.

    Free regions are emitted as one block per contiguous gap. The block's
    `cidr` is the smallest network covering that gap when the gap is itself
    a valid CIDR; otherwise the largest aligned subnet starting at the gap's
    first IP (caller can ignore — `span` is the source of truth for layout).
    """
    if block_prefix is None:
        block_prefix = pool.prefixlen

    total_bits = 32 if pool.version == 4 else 128
    cell_size = 2 ** (total_bits - block_prefix)

    sorted_assigns = sorted(assignments, key=lambda a: a["cidr"].first)
    blocks: List[dict] = []
    pos = pool.first

    for a in sorted_assigns:
        a_first = a["cidr"].first
        a_last = a["cidr"].last
        if pos < a_first:
            blocks.append(_free_block(pos, a_first - 1, cell_size, pool.version))
        blocks.append({
            "kind": "assigned",
            "cidr": a["cidr"],
            "label": a["label"],
            "span": max(1, a["cidr"].size // cell_size),
        })
        pos = a_last + 1

    if pos <= pool.last:
        blocks.append(_free_block(pos, pool.last, cell_size, pool.version))

    return blocks


def _free_block(first_int: int, last_int: int, cell_size: int, version: int) -> dict:
    size = last_int - first_int + 1
    span = max(1, size // cell_size)
    # Represent the gap with a best-effort CIDR (first IP / largest aligned prefix
    # that fits). Layout only depends on `span`/`size`.
    from netaddr import IPAddress
    return {
        "kind": "free",
        "cidr": IPNetwork(f"{IPAddress(first_int, version=version)}/{_prefix_for(size, version)}"),
        "size": size,
        "span": span,
    }


def _prefix_for(size: int, version: int) -> int:
    total = 32 if version == 4 else 128
    bits = 0
    while (1 << bits) < size:
        bits += 1
    return total - bits
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec web pytest ipam/tests/test_blocks.py -v
```

Expected: 7/7 pass.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/services/ web/ipam/tests/test_blocks.py
git commit -m "feat(ipam): pure services for block layout and customer color"
```

---

### Task 14: IPv4 pool detail view + block-grid template

**Files:**
- Modify: `web/ipam/views.py`
- Modify: `web/ipam/templates/pool_detail.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_ipv4_pool_detail_shows_grid_with_blocks(auth_client):
    p = Pool.objects.create(name="A", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="BINSS")
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/30")

    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "BINSS" in body
    assert "frei" in body.lower()
    # CSS grid present
    assert "grid-template-columns" in body or "grid-cols" in body
```

- [ ] **Step 2: Run to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_views.py::test_ipv4_pool_detail_shows_grid_with_blocks -v
```

Expected: FAIL (current template is empty placeholder).

- [ ] **Step 3: Implement pool_detail view**

Replace `pool_detail` in `web/ipam/views.py`:

```python
from netaddr import IPNetwork

from .services.blocks import compute_blocks
from .services.colors import color_for


@login_required
def pool_detail(request, pool_id):
    pool = get_object_or_404(Pool.objects.prefetch_related("assignments__customer"), pk=pool_id)

    assignments = [
        {
            "obj": a,
            "cidr": IPNetwork(str(a.cidr)),
            "label": f"{a.customer.name} · {a.cidr}",
            "customer": a.customer.name,
            "color": color_for(a.customer.name),
        }
        for a in pool.assignments.all()
    ]

    context = {"pool": pool, "assignments": assignments}

    if pool.ip_version == 4:
        blocks = compute_blocks(
            IPNetwork(str(pool.cidr)),
            assignments,
            block_prefix=pool.block_prefix or pool.cidr.prefixlen,
        )
        # Decorate blocks with color for template use
        for b in blocks:
            if b["kind"] == "assigned":
                src = next(a for a in assignments if a["cidr"] == b["cidr"])
                b["color"] = src["color"]
                b["customer"] = src["customer"]
                b["obj"] = src["obj"]
        total_cells = sum(b["span"] for b in blocks)
        context.update({
            "blocks": blocks,
            "total_cells": total_cells,
            "cells_per_row": min(16, total_cells),
        })
    return render(request, "pool_detail.html", context)
```

- [ ] **Step 4: Implement pool_detail.html**

Replace `web/ipam/templates/pool_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ pool.name }}{% endblock %}
{% block content %}
<div class="mb-4">
    <h1 class="text-2xl font-semibold">{{ pool.name }}</h1>
    <div class="font-mono text-slate-600">{{ pool.cidr }} · IPv{{ pool.ip_version }}{% if pool.block_prefix %} · Auflösung /{{ pool.block_prefix }}{% endif %}</div>
    {% if pool.notes %}<p class="mt-2 text-sm text-slate-700">{{ pool.notes }}</p>{% endif %}
</div>

{% if pool.ip_version == 4 %}
<div class="bg-white rounded shadow p-3 overflow-x-auto">
    <div class="grid gap-1" style="grid-template-columns: repeat({{ cells_per_row }}, minmax(0, 1fr));">
        {% for b in blocks %}
            {% if b.kind == "assigned" %}
            <a href="{% url 'ipam:assignment_edit' b.obj.id %}"
               style="grid-column: span {{ b.span }}; background-color: {{ b.color }};"
               class="border border-slate-300 rounded px-2 py-3 text-xs font-mono hover:ring-2 hover:ring-slate-800">
                <div class="font-semibold">{{ b.customer }}</div>
                <div>{{ b.cidr }}</div>
            </a>
            {% else %}
            <a href="{% url 'ipam:assignment_new' %}?pool={{ pool.id }}&cidr={{ b.cidr }}"
               style="grid-column: span {{ b.span }};"
               class="border border-dashed border-slate-300 rounded px-2 py-3 text-xs text-slate-500 bg-slate-50 hover:bg-slate-100">
                frei ({{ b.size }} IPs)
            </a>
            {% endif %}
        {% endfor %}
    </div>
</div>
{% else %}
{# IPv6 listing — filled in Task 15 #}
<p class="text-slate-500">IPv6-Ansicht folgt.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Add placeholder routes so {% url %} resolves**

In `web/ipam/urls.py`, append:

```python
urlpatterns += [
    path("assignment/new/", views.assignment_new, name="assignment_new"),
    path("assignment/<int:assignment_id>/edit/", views.assignment_edit, name="assignment_edit"),
]
```

In `web/ipam/views.py`, append stubs:

```python
@login_required
def assignment_new(request):
    from django.http import HttpResponse
    return HttpResponse("assignment_new placeholder")


@login_required
def assignment_edit(request, assignment_id):
    from django.http import HttpResponse
    return HttpResponse(f"assignment_edit {assignment_id} placeholder")
```

- [ ] **Step 6: Re-run tests**

```bash
docker compose exec web pytest ipam/tests/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add web/ipam/views.py web/ipam/urls.py web/ipam/templates/pool_detail.html web/ipam/tests/test_views.py
git commit -m "feat(ui): IPv4 pool detail block grid with customer colors"
```

---

### Task 15: IPv6 pool detail (list view)

**Files:**
- Modify: `web/ipam/views.py`
- Modify: `web/ipam/templates/pool_detail.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_ipv6_pool_detail_lists_assignments(auth_client):
    p = Pool.objects.create(name="V6", cidr="2a05:ed80:100::/48")
    c = Customer.objects.create(name="Falcon")
    Assignment.objects.create(pool=p, customer=c, cidr="2a05:ed80:100:400::/64")

    response = auth_client.get(f"/pool/{p.id}/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Falcon" in body
    assert "2a05:ed80:100:400::/64" in body
    # No grid for v6
    assert "grid-template-columns" not in body
```

- [ ] **Step 2: Run to verify failure**

Expected: FAIL — current template prints "IPv6-Ansicht folgt".

- [ ] **Step 3: Update pool_detail view for v6**

In `web/ipam/views.py`, replace the IPv6 branch in `pool_detail`:

After the `if pool.ip_version == 4:` block, add:

```python
    else:
        # IPv6: list assignments sorted by network; we don't compute gaps
        # explicitly because v6 pools dwarf any usable visualization.
        rows = sorted(assignments, key=lambda a: a["cidr"].first)
        context["v6_rows"] = rows
    return render(request, "pool_detail.html", context)
```

Make sure the existing function ends with one `return render(...)` — remove the
old duplicate return at the bottom of the IPv4 branch.

- [ ] **Step 4: Update template's IPv6 branch**

In `web/ipam/templates/pool_detail.html`, replace the IPv6 placeholder block
(the `{% else %}` branch) with:

```html
{% else %}
<table class="w-full text-sm bg-white rounded shadow">
    <thead class="bg-slate-100 text-slate-700">
        <tr>
            <th class="text-left p-2">CIDR</th>
            <th class="text-left p-2">Kunde</th>
            <th class="text-left p-2">Notes</th>
            <th class="p-2"></th>
        </tr>
    </thead>
    <tbody>
        {% for row in v6_rows %}
        <tr class="border-t">
            <td class="p-2 font-mono">{{ row.obj.cidr }}</td>
            <td class="p-2">{{ row.customer }}</td>
            <td class="p-2 text-slate-600">{{ row.obj.notes|truncatechars:80 }}</td>
            <td class="p-2 text-right">
                <a href="{% url 'ipam:assignment_edit' row.obj.id %}" class="text-slate-700 underline">bearbeiten</a>
            </td>
        </tr>
        {% empty %}
        <tr><td colspan="4" class="p-4 text-center text-slate-500">Noch keine Zuweisungen.</td></tr>
        {% endfor %}
    </tbody>
</table>
<div class="mt-3">
    <a href="{% url 'ipam:assignment_new' %}?pool={{ pool.id }}" class="bg-slate-800 text-white px-3 py-1 rounded text-sm">+ Zuweisung</a>
</div>
{% endif %}
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec web pytest ipam/tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/views.py web/ipam/templates/pool_detail.html web/ipam/tests/test_views.py
git commit -m "feat(ui): IPv6 pool detail as table view"
```

---

## Phase 5 — Forms + Customer Views

### Task 16: Assignment create/edit forms

**Files:**
- Create: `web/ipam/forms.py`
- Modify: `web/ipam/views.py`
- Create: `web/ipam/templates/assignment_form.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_assignment_new_rejects_overlap(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c1 = Customer.objects.create(name="A")
    Customer.objects.create(name="B")
    Assignment.objects.create(pool=p, customer=c1, cidr="217.61.249.0/30")

    response = auth_client.post("/assignment/new/", {
        "pool": p.id,
        "customer": Customer.objects.get(name="B").id,
        "cidr": "217.61.249.0/29",
        "gateway": "",
        "notes": "",
    })
    body = response.content.decode()
    assert response.status_code == 200  # form re-rendered, not 302
    assert "Überschneidung" in body or "überlappt" in body.lower() or "überschnei" in body.lower()


@pytest.mark.django_db
def test_assignment_new_happy_path_redirects(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="A")

    response = auth_client.post("/assignment/new/", {
        "pool": p.id,
        "customer": c.id,
        "cidr": "217.61.249.0/30",
        "gateway": "217.61.249.1",
        "notes": "Router",
    })
    assert response.status_code == 302
    assert Assignment.objects.filter(pool=p, cidr="217.61.249.0/30").exists()


@pytest.mark.django_db
def test_assignment_edit_loads_and_saves(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="A")
    a = Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/30", notes="old")

    response = auth_client.get(f"/assignment/{a.id}/edit/")
    assert response.status_code == 200

    response = auth_client.post(f"/assignment/{a.id}/edit/", {
        "pool": p.id,
        "customer": c.id,
        "cidr": "217.61.249.0/30",
        "gateway": "",
        "notes": "new",
    })
    assert response.status_code == 302
    a.refresh_from_db()
    assert a.notes == "new"
```

- [ ] **Step 2: Run tests to verify failure**

Expected: failures — current views are placeholders.

- [ ] **Step 3: Write AssignmentForm**

Create `web/ipam/forms.py`:

```python
from django import forms
from django.core.exceptions import ValidationError

from .models import Assignment


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["pool", "customer", "cidr", "gateway", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        data = super().clean()
        instance = Assignment(**{k: v for k, v in data.items() if v is not None})
        if self.instance.pk:
            instance.pk = self.instance.pk
        try:
            instance.clean()
        except ValidationError as e:
            self._update_errors(e)

        # Pre-empt the DB EXCLUDE constraint with a friendlier error
        cidr = data.get("cidr")
        pool = data.get("pool")
        if cidr is not None and pool is not None:
            from netaddr import IPNetwork
            new_net = IPNetwork(str(cidr))
            qs = Assignment.objects.filter(pool=pool)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            for other in qs:
                other_net = IPNetwork(str(other.cidr))
                if new_net.first <= other_net.last and other_net.first <= new_net.last:
                    raise ValidationError({
                        "cidr": f"Überschneidung mit {other.cidr} ({other.customer.name})."
                    })
        return data
```

- [ ] **Step 4: Replace assignment_new and assignment_edit**

In `web/ipam/views.py`, replace the placeholder stubs:

```python
from django.shortcuts import redirect

from .forms import AssignmentForm
from .models import Assignment


@login_required
def assignment_new(request):
    initial = {
        "pool": request.GET.get("pool") or None,
        "cidr": request.GET.get("cidr") or None,
    }
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("ipam:pool_detail", pool_id=form.cleaned_data["pool"].id)
    else:
        form = AssignmentForm(initial=initial)
    return render(request, "assignment_form.html", {"form": form, "mode": "new"})


@login_required
def assignment_edit(request, assignment_id):
    a = get_object_or_404(Assignment, pk=assignment_id)
    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=a)
        if form.is_valid():
            form.save()
            return redirect("ipam:pool_detail", pool_id=a.pool_id)
    else:
        form = AssignmentForm(instance=a)
    return render(request, "assignment_form.html", {"form": form, "mode": "edit", "obj": a})
```

- [ ] **Step 5: Write assignment_form.html**

Create `web/ipam/templates/assignment_form.html`:

```html
{% extends "base.html" %}
{% block title %}Zuweisung{% endblock %}
{% block content %}
<div class="max-w-xl bg-white p-6 rounded shadow">
    <h1 class="text-xl font-semibold mb-4">
        {% if mode == "new" %}Neue Zuweisung{% else %}Zuweisung bearbeiten{% endif %}
    </h1>
    <form method="post" class="space-y-4">
        {% csrf_token %}
        {% for field in form %}
        <div>
            <label class="block text-sm mb-1">{{ field.label }}</label>
            {{ field }}
            {% if field.help_text %}<p class="text-xs text-slate-500 mt-1">{{ field.help_text }}</p>{% endif %}
            {% if field.errors %}<p class="text-sm text-red-600 mt-1">{{ field.errors|join:" " }}</p>{% endif %}
        </div>
        {% endfor %}
        <div class="flex gap-2">
            <button class="bg-slate-800 text-white px-4 py-2 rounded">Speichern</button>
            <a href="javascript:history.back()" class="px-4 py-2 rounded border">Abbrechen</a>
        </div>
    </form>
</div>
<style>
    input[type=text], input[type=number], select, textarea {
        @apply border rounded w-full px-2 py-1;
    }
</style>
{% endblock %}
```

- [ ] **Step 6: Run tests**

```bash
docker compose exec web pytest ipam/tests/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add web/ipam/forms.py web/ipam/views.py web/ipam/templates/assignment_form.html web/ipam/tests/test_views.py
git commit -m "feat(ipam): assignment create/edit forms with friendly overlap error"
```

---

### Task 17: Customer list + customer detail

**Files:**
- Modify: `web/ipam/urls.py`
- Modify: `web/ipam/views.py`
- Create: `web/ipam/templates/customer_list.html`
- Create: `web/ipam/templates/customer_detail.html`
- Modify: `web/ipam/tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Append to `web/ipam/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_customer_list_shows_count(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="BINSS")
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/30")
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.4/30")

    response = auth_client.get("/customers/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "2" in body  # count appears


@pytest.mark.django_db
def test_customer_detail_lists_assignments(auth_client):
    p = Pool.objects.create(name="P", cidr="217.61.249.0/28", block_prefix=30)
    c = Customer.objects.create(name="BINSS")
    Assignment.objects.create(pool=p, customer=c, cidr="217.61.249.0/30")

    response = auth_client.get(f"/customer/{c.id}/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "BINSS" in body
    assert "217.61.249.0/30" in body
```

- [ ] **Step 2: Run to verify failure**

Expected: 404s (routes don't exist).

- [ ] **Step 3: Add routes**

In `web/ipam/urls.py`, append:

```python
urlpatterns += [
    path("customers/", views.customer_list, name="customer_list"),
    path("customer/<int:customer_id>/", views.customer_detail, name="customer_detail"),
]
```

- [ ] **Step 4: Add views**

In `web/ipam/views.py`, append:

```python
from django.db.models import Count

from .models import Customer


@login_required
def customer_list(request):
    customers = Customer.objects.annotate(
        n_assignments=Count("assignments")
    ).order_by("name")
    return render(request, "customer_list.html", {"customers": customers})


@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    assignments = customer.assignments.select_related("pool").order_by("pool__cidr", "cidr")
    return render(request, "customer_detail.html", {
        "customer": customer, "assignments": assignments,
    })
```

- [ ] **Step 5: Add templates**

Create `web/ipam/templates/customer_list.html`:

```html
{% extends "base.html" %}
{% block title %}Kunden{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-4">Kunden / Standorte</h1>
<table class="w-full bg-white rounded shadow text-sm">
    <thead class="bg-slate-100">
        <tr><th class="text-left p-2">Name</th><th class="text-left p-2">Zuweisungen</th></tr>
    </thead>
    <tbody>
    {% for c in customers %}
        <tr class="border-t">
            <td class="p-2"><a href="{% url 'ipam:customer_detail' c.id %}" class="underline">{{ c.name }}</a></td>
            <td class="p-2">{{ c.n_assignments }}</td>
        </tr>
    {% empty %}
        <tr><td colspan="2" class="p-4 text-center text-slate-500">Noch keine Kunden.</td></tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}
```

Create `web/ipam/templates/customer_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ customer.name }}{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-1">{{ customer.name }}</h1>
{% if customer.notes %}<p class="text-slate-700 mb-3">{{ customer.notes }}</p>{% endif %}
<table class="w-full bg-white rounded shadow text-sm">
    <thead class="bg-slate-100">
        <tr>
            <th class="text-left p-2">Pool</th>
            <th class="text-left p-2">CIDR</th>
            <th class="text-left p-2">Gateway</th>
            <th class="text-left p-2">Notes</th>
            <th class="p-2"></th>
        </tr>
    </thead>
    <tbody>
    {% for a in assignments %}
        <tr class="border-t">
            <td class="p-2 font-mono"><a href="{% url 'ipam:pool_detail' a.pool.id %}" class="underline">{{ a.pool.cidr }}</a></td>
            <td class="p-2 font-mono">{{ a.cidr }}</td>
            <td class="p-2 font-mono">{{ a.gateway|default_if_none:"" }}</td>
            <td class="p-2 text-slate-600">{{ a.notes|truncatechars:80 }}</td>
            <td class="p-2 text-right"><a href="{% url 'ipam:assignment_edit' a.id %}" class="underline">bearbeiten</a></td>
        </tr>
    {% empty %}
        <tr><td colspan="5" class="p-4 text-center text-slate-500">Keine Zuweisungen.</td></tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}
```

- [ ] **Step 6: Add nav link to base.html**

In `web/ipam/templates/base.html`, change the header right-side div to include
a customer link before the user/logout:

Replace:

```html
    <div>
        {% if user.is_authenticated %}
            <span class="text-sm mr-3">{{ user.username }}</span>
```

with:

```html
    <div>
        {% if user.is_authenticated %}
            <a href="{% url 'ipam:customer_list' %}" class="text-sm mr-4 hover:underline">Kunden</a>
            <span class="text-sm mr-3">{{ user.username }}</span>
```

- [ ] **Step 7: Run tests**

```bash
docker compose exec web pytest ipam/tests/ -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add web/ipam/urls.py web/ipam/views.py web/ipam/templates/ web/ipam/tests/test_views.py
git commit -m "feat(ui): customer list + customer detail pages"
```

---

## Phase 6 — Wiki Import

### Task 18: Wiki parser (pure)

**Files:**
- Create: `web/ipam/services/wiki_parser.py`
- Create: `web/ipam/tests/test_wiki_parser.py`
- Create: `web/ipam/tests/fixtures/wiki_sample.txt`

- [ ] **Step 1: Write failing tests**

Create `web/ipam/tests/fixtures/wiki_sample.txt` with this content (truncated
real wiki snippet — covers all variants):

```
==== Cyter/Checkov Kommunikation ====

45.151.168.0/30
2a05:ed80:100:1613::1/64

==== Clausberg ====

185.91.196.6, 7, 8

==== CCR2216 ====

217.61.248.1/30

217.61.248.5/30

==== SWE ====
217.61.249.192/30 MT Router GB Straße Unifi/Binss/Arena

217.61.249.218 Varia Router

==== BINSS ====

Netz:   217.61.249.0/28
Host-IPs:  217.61.249.1 - 217.61.249.14
Broadcast: 217.61.249.15

Netz:   217.61.249.16/28
Host-IPs:  217.61.249.17 - 217.61.249.30
Broadcast: 217.61.249.31

==== Falcon ====

IPv4

IP Netz: 217.61.249.32/29

nutzbare IPs: 217.61.249.34 - 217.61.249.38
Gateway: 217.61.249.33

IP Netz2: 217.61.249.64/28

IPv6

Netz: 2a05:ed80:100:400::/64
Gateway: 2a05:ed80:100:400::1
```

Create `web/ipam/tests/test_wiki_parser.py`:

```python
from pathlib import Path

from ipam.services.wiki_parser import parse

SAMPLE = (Path(__file__).parent / "fixtures" / "wiki_sample.txt").read_text()


def test_parse_returns_customer_with_cidr_entries():
    results = parse(SAMPLE)
    by_customer = {r["customer"]: [] for r in results}
    for r in results:
        by_customer[r["customer"]].append(r["cidr"])

    assert "BINSS" in by_customer
    assert "217.61.249.0/28" in by_customer["BINSS"]
    assert "217.61.249.16/28" in by_customer["BINSS"]


def test_parse_handles_dual_stack():
    results = parse(SAMPLE)
    cyter = [r for r in results if r["customer"] == "Cyter/Checkov Kommunikation"]
    cidrs = {r["cidr"] for r in cyter}
    assert "45.151.168.0/30" in cidrs
    assert any(c.startswith("2a05:ed80:100:1613") for c in cidrs)


def test_parse_expands_comma_listed_ips_to_slash32():
    results = parse(SAMPLE)
    clausberg = sorted(r["cidr"] for r in results if r["customer"] == "Clausberg")
    assert clausberg == ["185.91.196.6/32", "185.91.196.7/32", "185.91.196.8/32"]


def test_parse_captures_inline_note():
    results = parse(SAMPLE)
    swe = [r for r in results if r["customer"] == "SWE" and r["cidr"] == "217.61.249.192/30"]
    assert len(swe) == 1
    assert "MT Router" in swe[0]["notes"]


def test_parse_single_ip_without_prefix_becomes_slash32():
    results = parse(SAMPLE)
    varia = [r for r in results if r["cidr"] == "217.61.249.218/32"]
    assert len(varia) == 1
    assert varia[0]["customer"] == "SWE"
    assert "Varia" in varia[0]["notes"]


def test_parse_falcon_extracts_both_v4_and_v6_networks():
    results = parse(SAMPLE)
    falcon = sorted(r["cidr"] for r in results if r["customer"] == "Falcon")
    assert "217.61.249.32/29" in falcon
    assert "217.61.249.64/28" in falcon
    assert any(c.startswith("2a05:ed80:100:400") for c in falcon)


def test_parse_does_not_double_count_host_ip_lines():
    # "Host-IPs: 217.61.249.1 - 217.61.249.14" must NOT produce 14 /32 entries
    # because the /28 above already covers them.
    results = parse(SAMPLE)
    binss_v4 = [r["cidr"] for r in results if r["customer"] == "BINSS"]
    # Just the two /28 nets, no /32 expansions
    assert all("/28" in c for c in binss_v4)
```

- [ ] **Step 2: Run to verify failure**

```bash
docker compose exec web pytest ipam/tests/test_wiki_parser.py -v
```

Expected: collection error — module missing.

- [ ] **Step 3: Implement parser**

Create `web/ipam/services/wiki_parser.py`:

```python
import re
from typing import List

# Headers like ==== Name ====
_HEADER = re.compile(r"^={2,}\s*(.+?)\s*={2,}\s*$")

# CIDR (IPv4 or IPv6) with explicit prefix length
_CIDR = re.compile(
    r"(?<![\w.:])("
    r"(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}"
    r"|"
    r"[0-9a-fA-F:]+:[0-9a-fA-F:]*/\d{1,3}"
    r")"
)

# Bare IPv4 (no prefix)
_BARE_V4 = re.compile(r"(?<![\w./:])((?:\d{1,3}\.){3}\d{1,3})(?!/\d)(?![\w.:])")

# Lines we should NOT scan for bare IPs (already-covered host enumerations,
# gateways, broadcasts, "nutzbare IPs"). These are descriptive only.
_SKIP_LINE_PATTERNS = (
    re.compile(r"^\s*host-?ips?\s*:", re.IGNORECASE),
    re.compile(r"^\s*nutzbare\s+ips?\s*:", re.IGNORECASE),
    re.compile(r"^\s*broadcast\s*:", re.IGNORECASE),
    re.compile(r"^\s*gateway\s*:", re.IGNORECASE),
)

# Shorthand: "185.91.196.6, 7, 8" → expand to .6, .7, .8
_COMMA_TAIL = re.compile(r"((?:\d{1,3}\.){3})(\d{1,3})\s*,\s*(\d{1,3}(?:\s*,\s*\d{1,3})*)")


def parse(text: str) -> List[dict]:
    """Parse a dokuwiki-style IP allocation text.

    Returns a list of {customer, cidr, notes} dicts.
    """
    results: List[dict] = []
    current = None

    for raw in text.splitlines():
        line = raw.rstrip()
        m = _HEADER.match(line)
        if m:
            current = m.group(1).strip()
            continue
        if current is None:
            continue
        if not line.strip():
            continue
        if any(p.match(line) for p in _SKIP_LINE_PATTERNS):
            continue

        # 1) Comma-tail shorthand: convert "a.b.c.6, 7, 8" → three /32 entries.
        cm = _COMMA_TAIL.search(line)
        if cm:
            prefix = cm.group(1)
            first = cm.group(2)
            rest = [x.strip() for x in cm.group(3).split(",") if x.strip()]
            for octet in [first, *rest]:
                results.append({
                    "customer": current,
                    "cidr": f"{prefix}{octet}/32",
                    "notes": "",
                })
            continue

        # 2) Explicit CIDRs on the line.
        found_any = False
        for cm in _CIDR.finditer(line):
            cidr = cm.group(1)
            # Normalize IPv6 hosts written with /64 etc. — keep as-is, the
            # DB layer will accept; if the address is not the network address
            # netaddr will still parse, and the DB stores the network part.
            note = _extract_note(line, cm.span())
            results.append({"customer": current, "cidr": cidr, "notes": note})
            found_any = True
        if found_any:
            continue

        # 3) Single bare IPv4 → /32.
        for cm in _BARE_V4.finditer(line):
            ip = cm.group(1)
            note = _extract_note(line, cm.span())
            results.append({"customer": current, "cidr": f"{ip}/32", "notes": note})

    return results


def _extract_note(line: str, match_span) -> str:
    """Return text on the line excluding the matched CIDR/IP, trimmed."""
    start, end = match_span
    before = line[:start].strip(" \t:,")
    after = line[end:].strip(" \t:,")
    # Drop boilerplate labels like "Netz", "IP Netz", "IP Netz2"
    before = re.sub(r"^(IP\s*)?Netz\d*\s*$", "", before, flags=re.IGNORECASE).strip()
    parts = [p for p in (before, after) if p]
    return " ".join(parts)
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec web pytest ipam/tests/test_wiki_parser.py -v
```

Expected: 7/7 pass. If a single test still fails, inspect the parser output:

```bash
docker compose exec web python -c "
from ipam.services.wiki_parser import parse
from pathlib import Path
import json
text = Path('ipam/tests/fixtures/wiki_sample.txt').read_text()
print(json.dumps(parse(text), indent=2, ensure_ascii=False))
"
```

Adjust skip-line patterns or note-extraction until the test set passes.

- [ ] **Step 5: Commit**

```bash
git add web/ipam/services/wiki_parser.py web/ipam/tests/test_wiki_parser.py web/ipam/tests/fixtures/wiki_sample.txt
git commit -m "feat(ipam): wiki-text parser with tests covering all dump variants"
```

---

### Task 19: import_wiki management command

**Files:**
- Create: `web/ipam/management/__init__.py`
- Create: `web/ipam/management/commands/__init__.py`
- Create: `web/ipam/management/commands/import_wiki.py`
- Modify: `web/ipam/tests/test_wiki_parser.py` (add command test)

- [ ] **Step 1: Write failing test for the command**

Create `web/ipam/tests/test_import_command.py`:

```python
import pytest
from django.core.management import call_command
from io import StringIO
from pathlib import Path

from ipam.models import Assignment, Customer, Pool


FIXTURE = str(Path(__file__).parent / "fixtures" / "wiki_sample.txt")


@pytest.mark.django_db
def test_import_creates_customers_and_assignments():
    Pool.objects.create(name="Pool-217.61.248/23", cidr="217.61.248.0/23", block_prefix=30)
    Pool.objects.create(name="Pool-45/24", cidr="45.151.168.0/24")
    Pool.objects.create(name="Pool-185/24", cidr="185.91.196.0/24")
    Pool.objects.create(name="Pool-v6", cidr="2a05:ed80:100::/48")

    out = StringIO()
    call_command("import_wiki", FIXTURE, stdout=out)

    assert Customer.objects.filter(name="BINSS").exists()
    assert Assignment.objects.filter(cidr="217.61.249.0/28").exists()
    assert Assignment.objects.filter(cidr="185.91.196.6/32").exists()
    assert "angelegt" in out.getvalue().lower()


@pytest.mark.django_db
def test_import_is_idempotent():
    Pool.objects.create(name="Pool-217.61.248/23", cidr="217.61.248.0/23", block_prefix=30)
    Pool.objects.create(name="Pool-45/24", cidr="45.151.168.0/24")
    Pool.objects.create(name="Pool-185/24", cidr="185.91.196.0/24")
    Pool.objects.create(name="Pool-v6", cidr="2a05:ed80:100::/48")

    call_command("import_wiki", FIXTURE)
    n_first = Assignment.objects.count()
    call_command("import_wiki", FIXTURE)
    n_second = Assignment.objects.count()

    assert n_first == n_second


@pytest.mark.django_db
def test_import_skips_entries_with_no_matching_pool(tmp_path, capsys):
    txt = tmp_path / "wiki.txt"
    txt.write_text("==== Orphan ====\n8.8.8.0/24\n")
    out = StringIO()
    call_command("import_wiki", str(txt), stdout=out)
    assert Assignment.objects.count() == 0
    assert "übersprungen" in out.getvalue().lower() or "skip" in out.getvalue().lower()
```

- [ ] **Step 2: Run to verify failure**

Expected: CommandError "Unknown command: import_wiki".

- [ ] **Step 3: Implement command**

Create empty files:
- `web/ipam/management/__init__.py`
- `web/ipam/management/commands/__init__.py`

Create `web/ipam/management/commands/import_wiki.py`:

```python
import logging
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from netaddr import IPNetwork

from ipam.models import Assignment, Customer, Pool
from ipam.services.wiki_parser import parse


class Command(BaseCommand):
    help = "Parse a wiki dump and import customers + assignments."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the wiki text file")
        parser.add_argument(
            "--log-dir", default=".", help="Directory for the skip-log file"
        )

    def handle(self, *args, **opts):
        path = Path(opts["path"])
        text = path.read_text(encoding="utf-8")
        entries = parse(text)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(opts["log_dir"]) / f"import_wiki_{ts}.log"
        logger = logging.getLogger("import_wiki")
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        pools = list(Pool.objects.all())
        customers_new = 0
        customers_existing = 0
        assignments_new = 0
        assignments_existing = 0
        skipped = 0

        for entry in entries:
            cust_name = entry["customer"]
            cidr_str = entry["cidr"]
            notes = entry["notes"]

            customer, created = Customer.objects.get_or_create(name=cust_name)
            if created:
                customers_new += 1
            else:
                customers_existing += 1

            try:
                ipnet = IPNetwork(cidr_str)
            except Exception as e:
                logger.warning(f"SKIP unparseable CIDR '{cidr_str}' ({cust_name}): {e}")
                skipped += 1
                continue

            pool = _smallest_containing_pool(pools, ipnet)
            if pool is None:
                logger.warning(f"SKIP no matching pool for {cidr_str} ({cust_name})")
                skipped += 1
                continue

            if Assignment.objects.filter(pool=pool, cidr=str(ipnet.cidr)).exists():
                assignments_existing += 1
                continue

            a = Assignment(pool=pool, customer=customer, cidr=str(ipnet.cidr), notes=notes)
            try:
                a.full_clean()
                with transaction.atomic():
                    a.save()
                assignments_new += 1
            except (ValidationError, IntegrityError) as e:
                logger.warning(f"SKIP {cidr_str} ({cust_name}): {e}")
                skipped += 1

        self.stdout.write(
            f"Customers angelegt:   {customers_new}\n"
            f"Customers vorhanden:  {customers_existing}\n"
            f"Assignments angelegt: {assignments_new}\n"
            f"Assignments vorhanden:{assignments_existing}\n"
            f"Übersprungen:         {skipped}  (siehe {log_path})\n"
        )


def _smallest_containing_pool(pools, ipnet):
    candidates = [
        p for p in pools
        if IPNetwork(str(p.cidr)).version == ipnet.version
        and ipnet in IPNetwork(str(p.cidr))
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: IPNetwork(str(p.cidr)).prefixlen, reverse=True)
    return candidates[0]
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec web pytest ipam/tests/test_import_command.py -v
```

Expected: 3/3 pass.

- [ ] **Step 5: Run full test suite**

```bash
docker compose exec web pytest -v
```

Expected: everything green.

- [ ] **Step 6: Commit**

```bash
git add web/ipam/management/ web/ipam/tests/test_import_command.py
git commit -m "feat(ipam): import_wiki management command (idempotent, logs skips)"
```

---

## Phase 7 — Final integration and ops

### Task 20: README + operator notes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README.md with operator-ready content**

```markdown
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
docker compose exec -T db pg_restore -U "${DB_USER}" -d "${DB_NAME}" < dump.sql
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: operator-ready README"
```

---

### Task 21: End-to-end smoke + sign-off

**Files:** none.

- [ ] **Step 1: Full rebuild**

```bash
cd /srv/docker/IP-Planer
docker compose down
docker compose up -d --build
docker compose logs --tail 30 web
```

Expected: web container reaches "starting: gunicorn", no errors.

- [ ] **Step 2: Login flow**

Open `http://localhost:8080/login/` in a browser, sign in as superuser.
Expected: redirect to `/`, pool overview renders.

- [ ] **Step 3: Create pools via admin**

Go to `/admin/ipam/pool/add/`. Create at minimum:
- `217.61.248.0/23` with `block_prefix=30`
- `45.151.168.0/24`
- `185.91.196.0/24`
- `2a05:ed80:100::/48`

(Adjust the IPv4 pool sizes for `45.151.168.0` and `185.91.196.0` per the
actual ranges KNT operates — these are best-guess defaults from the wiki.)

- [ ] **Step 4: Run wiki import**

Put a real wiki dump into `docs/wiki-export.txt` (the conversation's wiki
snippet is a workable starting point), then:

```bash
docker compose exec web python manage.py import_wiki docs/wiki-export.txt
```

Expected: counts printed, log file written, no exceptions.

- [ ] **Step 5: Visual check**

- `/` → cards with utilization bars.
- Sidebar shows each pool with children.
- Click `217.61.248.0/23` → block grid shows assignments + free gaps.
- Click `2a05:ed80:100::/48` → table view.
- Click a free block → assignment_new form pre-populated.
- Try saving an overlapping assignment → friendly error.

- [ ] **Step 6: Tag milestone**

```bash
git tag -a v1.0.0 -m "Subnetly v1.0.0 — initial release"
```
