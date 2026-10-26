# Local development

These steps were run on this environment on 2026-10-23 except where a command is marked as not run.

## What you need

- Python 3.12
- Node.js 22
- PostgreSQL 16

This machine used Python 3.12.3, Node.js 22.23.4, and PostgreSQL 16.15 from Ubuntu packages. Docker was not installed, so `docker compose up -d` was not executed. The compose file is still the supported way to start PostgreSQL elsewhere. CI uses the `postgres:16` image.

## Database

Create a role that can create databases (pytest creates a throwaway test database):

```sql
CREATE ROLE property LOGIN PASSWORD 'property' CREATEDB;
CREATE DATABASE property_dev OWNER property;
```

The password in `.env.example` is a local placeholder.

## First-time setup

From the repository root:

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
make migrate
```

`make migrate` applies migrations to the database in `DATABASE_URL`. It was run successfully against `property_dev`.

## Day-to-day processes

API:

```bash
cd backend && ../.venv/bin/python manage.py runserver 127.0.0.1:43124
```

Web app, which proxies `/api` to that API:

```bash
npm run dev --prefix frontend
```

Open http://127.0.0.1:43123. The page has account sign-in, workspace creation, and the API status card. After you create a workspace, the same page has properties, residents and stays, billing, maintenance, reports, and settings. Platform admin is separate: `createsuperuser`, then http://127.0.0.1:43124/admin/. Django admin is where `plan_code` is changed.

`DJANGO_SETTINGS_MODULE` defaults to `config.settings.local` for `manage.py`. Do not point Gunicorn at local settings.

## Checks

`make check` runs backend lint, format check, mypy, migration check, pytest, frontend lint, typecheck, Vitest, and the production web build.

Individual commands:

```bash
cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../.venv/bin/python -m ruff check .
cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../.venv/bin/python -m ruff format --check .
cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../.venv/bin/python -m mypy
cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../.venv/bin/python manage.py makemigrations --check --dry-run
cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../.venv/bin/python -m pytest
npm run lint --prefix frontend
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

`DATABASE_URL` must be a PostgreSQL URL. The Makefile defaults it to `postgres://property:property@127.0.0.1:5432/property_dev`. There is no SQLite fallback.

Production configuration, with a real secret substituted:

```bash
cd backend
DJANGO_SETTINGS_MODULE=config.settings.production \
DJANGO_SECRET_KEY='replace-with-a-long-random-secret' \
DJANGO_ALLOWED_HOSTS=app.example.com \
DJANGO_DEBUG=false \
DATABASE_URL='postgres://property:property@127.0.0.1:5432/property_dev' \
../.venv/bin/python manage.py check --deploy
```

Expect warning `security.W004` until `DJANGO_SECURE_HSTS_SECONDS` is set. A weak or missing secret fails the import before the check runs.

## Platform operator

```bash
cd backend && ../.venv/bin/python manage.py createsuperuser
```

This prompts for an email and password. It was not run here, and no superuser is seeded.

## Dependency locks

- Runtime: `backend/requirements.txt`
- Development, including runtime: `backend/requirements-dev.txt`
- Direct dependency lists: `backend/requirements.in` and `backend/requirements-dev.in`
- Web: `frontend/package-lock.json`

CI installs the lock files. After changing a direct dependency, reinstall and refresh the lock.

## Files and backups

Private files are configured, not uploaded. `FILE_STORAGE_BACKEND` defaults to `filesystem` for local development. An S3-compatible backend, intended for a private Cloudflare R2 bucket, is selected only when `FILE_STORAGE_BACKEND=s3` and the `FILE_STORAGE_S3_*` variables in `.env.example` are set. Do not put a real endpoint or key in the example file or in Python.

Backup uploads are still not automated. The operator procedure is in `docs/SECURITY.md` and ADR-011: nightly encrypted `pg_dump` to a separate R2 bucket, with separate credentials the application does not read, about 30 days of retention, one restore before launch, then periodic drills. `BACKUP_S3_*` variables are documented for the operator and are not Django settings. Nothing in `make check` uploads a dump.

## Not run here

- `docker compose up -d`
- GitHub Actions (the workflow is `.github/workflows/ci.yml`)
- A Gunicorn deployment or nginx install
- `createsuperuser`
- A backup restore drill
