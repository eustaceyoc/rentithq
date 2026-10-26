"""PostgreSQL configuration parsed from a URL. No other database is accepted."""

from __future__ import annotations

from typing import TypedDict
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


class PostgresDatabaseConfig(TypedDict):
    ENGINE: str
    NAME: str
    USER: str
    PASSWORD: str
    HOST: str
    PORT: str
    CONN_MAX_AGE: int
    OPTIONS: dict[str, str]


def postgres_config_from_url(url: str, *, conn_max_age: int) -> PostgresDatabaseConfig:
    """Build a Django DATABASES entry from a postgres:// or postgresql:// URL."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured(
            "DATABASE_URL must use the postgres or postgresql scheme."
        )
    name = unquote(parsed.path.lstrip("/"))
    if not name:
        raise ImproperlyConfigured("DATABASE_URL must include a database name.")
    if not parsed.hostname:
        raise ImproperlyConfigured("DATABASE_URL must include a host.")
    options = {
        key: value
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key == "sslmode"
    }
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": unquote(parsed.username) if parsed.username else "",
        "PASSWORD": unquote(parsed.password) if parsed.password else "",
        "HOST": parsed.hostname,
        "PORT": str(parsed.port or 5432),
        "CONN_MAX_AGE": conn_max_age,
        "OPTIONS": options,
    }
