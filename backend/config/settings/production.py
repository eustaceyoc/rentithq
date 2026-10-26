"""Production settings. Missing required configuration fails closed."""

from __future__ import annotations

import os

from config.environment import (
    read_bool,
    read_non_negative_int,
    split_csv,
    validate_production_environment,
)

validate_production_environment(os.environ)

from config.settings.base import *  # noqa: E402,F403

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"].strip()
ALLOWED_HOSTS = split_csv(os.environ["DJANGO_ALLOWED_HOSTS"])
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = read_non_negative_int(
    os.environ, "DJANGO_SECURE_HSTS_SECONDS", default=0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
CSRF_TRUSTED_ORIGINS = split_csv(os.environ.get("CSRF_TRUSTED_ORIGINS", ""))

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": os.environ.get("EMAIL_HOST", "").strip(),
            "port": read_non_negative_int(os.environ, "EMAIL_PORT", default=587),
            "username": os.environ.get("EMAIL_HOST_USER", "").strip(),
            "password": os.environ.get("EMAIL_HOST_PASSWORD", ""),
            "use_tls": read_bool(os.environ, "EMAIL_USE_TLS", default=True),
        },
    },
}
