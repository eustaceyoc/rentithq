"""Environment parsing that does not import Django settings."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_WEAK_SECRET_PREFIXES = ("dev-", "test-", "changeme")


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def read_bool(environ: Mapping[str, str], key: str, *, default: bool) -> bool:
    raw = environ.get(key)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in _TRUE_VALUES


def read_log_level(environ: Mapping[str, str]) -> str:
    level = environ.get("LOG_LEVEL", "INFO").strip().upper()
    if level not in LOG_LEVELS:
        raise ImproperlyConfigured(
            "LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL."
        )
    return level


def read_non_negative_int(environ: Mapping[str, str], key: str, *, default: int) -> int:
    raw = environ.get(key, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{key} must be an integer.") from exc
    if value < 0:
        raise ImproperlyConfigured(f"{key} must be zero or greater.")
    return value


def production_allowed_hosts(environ: Mapping[str, str]) -> list[str]:
    """Hosts from the environment, plus the Render service host when present."""
    hosts = split_csv(environ.get("DJANGO_ALLOWED_HOSTS", ""))
    render_host = environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host and render_host not in hosts:
        hosts.append(render_host)
    return hosts


def production_csrf_origins(environ: Mapping[str, str]) -> list[str]:
    """HTTPS origins from the environment, plus the Render service origin."""
    origins = split_csv(environ.get("CSRF_TRUSTED_ORIGINS", ""))
    render_host = environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host:
        origin = f"https://{render_host}"
        if origin not in origins:
            origins.append(origin)
    return origins


def mailers_from_environ(environ: Mapping[str, str]) -> dict[str, dict[str, object]]:
    """Console mail unless EMAIL_HOST is set. The password stays in the environment."""
    host = environ.get("EMAIL_HOST", "").strip()
    if not host:
        return {
            "default": {
                "BACKEND": "django.core.mail.backends.console.EmailBackend",
            }
        }
    return {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": host,
                "port": read_non_negative_int(environ, "EMAIL_PORT", default=587),
                "username": environ.get("EMAIL_HOST_USER", "").strip(),
                "password": environ.get("EMAIL_HOST_PASSWORD", ""),
                "use_tls": read_bool(environ, "EMAIL_USE_TLS", default=True),
            },
        }
    }


def validate_production_environment(environ: Mapping[str, str]) -> None:
    """Fail closed when production is missing a secret or would run in debug."""
    required = ("DJANGO_SECRET_KEY", "DATABASE_URL")
    missing = [key for key in required if not environ.get(key, "").strip()]
    if missing:
        raise ImproperlyConfigured(
            "Production configuration is incomplete: " + ", ".join(missing) + "."
        )
    if read_bool(environ, "DJANGO_DEBUG", default=False):
        raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")

    secret = environ["DJANGO_SECRET_KEY"].strip()
    lowered = secret.lower()
    if (
        len(secret) < 40
        or len(set(secret)) < 5
        or lowered.startswith(_WEAK_SECRET_PREFIXES)
        or "insecure" in lowered
    ):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not strong enough for production."
        )

    hosts = production_allowed_hosts(environ)
    if not hosts or any(host == "*" for host in hosts):
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must list explicit host names."
        )

    scheme = urlsplit(environ["DATABASE_URL"].strip()).scheme
    if scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured(
            "DATABASE_URL must be a PostgreSQL URL in production."
        )

    for origin in production_csrf_origins(environ):
        if not origin.startswith("https://"):
            raise ImproperlyConfigured(
                "CSRF_TRUSTED_ORIGINS entries must use https in production."
            )

    read_non_negative_int(environ, "DJANGO_SECURE_HSTS_SECONDS", default=0)
    read_log_level(environ)
