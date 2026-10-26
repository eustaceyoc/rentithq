"""Local development settings. Do not use this module in production."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from config.environment import split_csv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

os.environ.setdefault(
    "DJANGO_SECRET_KEY",
    "dev-insecure-local-key-not-for-production",
)
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
os.environ.setdefault("DB_CONN_MAX_AGE", "0")
os.environ.setdefault(
    "CSRF_TRUSTED_ORIGINS",
    "http://127.0.0.1:43123,http://localhost:43123",
)

from config.settings.base import *  # noqa: E402,F403

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "common.api.renderers.DecimalJSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

CSRF_TRUSTED_ORIGINS = split_csv(os.environ.get("CSRF_TRUSTED_ORIGINS", ""))
