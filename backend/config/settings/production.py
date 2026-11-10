"""Production settings. Missing required configuration fails closed."""

from __future__ import annotations

import os

from config.environment import (
    mailers_from_environ,
    production_allowed_hosts,
    production_csrf_origins,
    read_non_negative_int,
    validate_production_environment,
)

validate_production_environment(os.environ)

from config.settings.base import *  # noqa: E402,F403

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"].strip()
ALLOWED_HOSTS = production_allowed_hosts(os.environ)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = read_non_negative_int(
    os.environ, "DJANGO_SECURE_HSTS_SECONDS", default=0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
CSRF_TRUSTED_ORIGINS = production_csrf_origins(os.environ)
# The Vercel site proxies this API, so the cookie must not be pinned to Render.
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None

MAILERS = mailers_from_environ(os.environ)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
}
