PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
export DATABASE_URL ?= postgres://property:property@127.0.0.1:5432/property_dev

.PHONY: install backend-install frontend-install migrate check-migrations test lint typecheck build check

install: backend-install frontend-install

backend-install:
	python3 -m venv .venv
	$(PIP) install -r backend/requirements-dev.txt

frontend-install:
	npm ci --prefix frontend

migrate:
	cd backend && ../$(PYTHON) manage.py migrate

check-migrations:
	cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../$(PYTHON) manage.py makemigrations --check --dry-run

test:
	cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../$(PYTHON) -m pytest
	npm test --prefix frontend

lint:
	cd backend && ../$(PYTHON) -m ruff check .
	cd backend && ../$(PYTHON) -m ruff format --check .
	npm run lint --prefix frontend

typecheck:
	cd backend && DJANGO_SETTINGS_MODULE=config.settings.test ../$(PYTHON) -m mypy
	npm run typecheck --prefix frontend

build:
	npm run build --prefix frontend

check: lint typecheck check-migrations test build
