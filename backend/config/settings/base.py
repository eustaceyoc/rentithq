"""Shared Django settings. Environment-specific modules must load dotenv first."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.database import postgres_config_from_url
from config.environment import read_bool, read_log_level, split_csv
from config.storage import file_storage_config

BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BASE_DIR.parent

database_url = os.environ.get("DATABASE_URL", "").strip()
if not database_url:
    raise ImproperlyConfigured(
        "DATABASE_URL is required and must be a PostgreSQL URL. "
        "SQLite is not a supported database for this product."
    )

secret_key = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not secret_key:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required.")

DEBUG = read_bool(os.environ, "DJANGO_DEBUG", default=False)
SECRET_KEY = secret_key
ALLOWED_HOSTS = split_csv(os.environ.get("DJANGO_ALLOWED_HOSTS", ""))
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list at least one host.")

DATABASES = {
    "default": postgres_config_from_url(
        database_url,
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "0")),
    )
}

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "accounts.apps.AccountsConfig",
    "organizations.apps.OrganizationsConfig",
    "properties.apps.PropertiesConfig",
    "residents.apps.ResidentsConfig",
    "bookings.apps.BookingsConfig",
    "tenancies.apps.TenanciesConfig",
    "billing.apps.BillingConfig",
    "maintenance.apps.MaintenanceConfig",
    "reports.apps.ReportsConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "common.apps.CommonConfig",
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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# en-us is the interface language default, not a country or legal regime.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# File storage is selected from the environment. Backup credentials are not read.
STORAGES = {
    "default": file_storage_config(os.environ),
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = split_csv(os.environ.get("CSRF_TRUSTED_ORIGINS", ""))

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

DEFAULT_FROM_EMAIL = (
    os.environ.get("DEFAULT_FROM_EMAIL", "Rent It HQ <noreply@rentithq.local>").strip()
    or "Rent It HQ <noreply@rentithq.local>"
)
FRONTEND_BASE_URL = (
    os.environ.get("FRONTEND_BASE_URL", "http://127.0.0.1:43123").strip().rstrip("/")
    or "http://127.0.0.1:43123"
)
# PasswordResetTokenGenerator treats a token as expired after this many seconds.
PASSWORD_RESET_TIMEOUT = 60 * 60

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "common.api.renderers.DecimalJSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.api.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "common.api.errors.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "password_reset": "5/hour",
        "password_reset_confirm": "10/hour",
    },
}

LOG_LEVEL = read_log_level(os.environ)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
