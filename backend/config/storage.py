"""File storage configuration.

Endpoints and credentials come from the environment. Backup credentials are a
different bucket and are not read here. See ADR-011 and ADR-012.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ImproperlyConfigured

_FILESYSTEM_BACKEND = "django.core.files.storage.FileSystemStorage"
_S3_BACKEND = "storages.backends.s3.S3Storage"
_DEFAULT_EXPIRE_SECONDS = 300
_MAX_EXPIRE_SECONDS = 3600


def _text(environ: Mapping[str, str], key: str) -> str:
    if key.startswith("BACKUP_"):
        raise ImproperlyConfigured(
            "Backup storage settings are not part of application file storage."
        )
    raw = environ.get(key, "")
    if not isinstance(raw, str):
        raise ImproperlyConfigured(f"{key} must be a string.")
    return raw.strip()


def file_storage_config(environ: Mapping[str, str]) -> dict[str, Any]:
    """Build Django's default STORAGES entry. No host or key is hardcoded."""
    backend = _text(environ, "FILE_STORAGE_BACKEND").lower() or "filesystem"
    if backend == "filesystem":
        return {"BACKEND": _FILESYSTEM_BACKEND}
    if backend != "s3":
        raise ImproperlyConfigured("FILE_STORAGE_BACKEND must be filesystem or s3.")

    required = {
        "endpoint_url": "FILE_STORAGE_S3_ENDPOINT_URL",
        "bucket_name": "FILE_STORAGE_S3_BUCKET",
        "access_key": "FILE_STORAGE_S3_ACCESS_KEY_ID",
        "secret_key": "FILE_STORAGE_S3_SECRET_ACCESS_KEY",
    }
    options: dict[str, Any] = {}
    missing: list[str] = []
    for option, key in required.items():
        value = _text(environ, key)
        if not value:
            missing.append(key)
        else:
            options[option] = value
    if missing:
        raise ImproperlyConfigured(
            "S3 file storage is incomplete: " + ", ".join(missing) + "."
        )

    region = _text(environ, "FILE_STORAGE_S3_REGION")
    if region:
        options["region_name"] = region

    expire_raw = _text(environ, "FILE_STORAGE_QUERYSTRING_EXPIRE")
    if expire_raw:
        try:
            expire = int(expire_raw)
        except ValueError as exc:
            raise ImproperlyConfigured(
                "FILE_STORAGE_QUERYSTRING_EXPIRE must be an integer."
            ) from exc
    else:
        expire = _DEFAULT_EXPIRE_SECONDS
    if expire < 1 or expire > _MAX_EXPIRE_SECONDS:
        raise ImproperlyConfigured(
            "FILE_STORAGE_QUERYSTRING_EXPIRE must be between 1 and 3600 seconds."
        )

    options["querystring_auth"] = True
    options["querystring_expire"] = expire
    options["default_acl"] = "private"
    options["file_overwrite"] = False
    options["signature_version"] = "s3v4"
    options["addressing_style"] = "path"
    return {"BACKEND": _S3_BACKEND, "OPTIONS": options}
