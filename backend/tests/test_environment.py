from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.database import postgres_config_from_url
from config.environment import validate_production_environment
from config.storage import file_storage_config

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_postgres_url_parser_rejects_other_engines() -> None:
    with pytest.raises(ImproperlyConfigured):
        postgres_config_from_url("sqlite:///db.sqlite3", conn_max_age=0)
    with pytest.raises(ImproperlyConfigured):
        postgres_config_from_url("postgres:///property_dev", conn_max_age=0)


def test_postgres_url_parser_unquotes_credentials() -> None:
    config = postgres_config_from_url(
        "postgresql://property:p%40ss@127.0.0.1:5432/property_dev?sslmode=require",
        conn_max_age=0,
    )
    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert config["NAME"] == "property_dev"
    assert config["USER"] == "property"
    assert config["PASSWORD"] == "p@ss"
    assert config["HOST"] == "127.0.0.1"
    assert config["PORT"] == "5432"
    assert config["OPTIONS"] == {"sslmode": "require"}


def test_production_validator_rejects_debug_weak_secrets_and_wildcards() -> None:
    secret = "ProductionSecret-Varied-Key-09af-X7" * 2
    base = {
        "DJANGO_SECRET_KEY": secret,
        "DJANGO_ALLOWED_HOSTS": "app.example.com",
        "DATABASE_URL": "postgres://property:property@127.0.0.1:5432/property_dev",
        "DJANGO_DEBUG": "false",
    }
    validate_production_environment(base)

    with pytest.raises(ImproperlyConfigured):
        validate_production_environment({**base, "DJANGO_DEBUG": "true"})
    with pytest.raises(ImproperlyConfigured):
        validate_production_environment({**base, "DJANGO_SECRET_KEY": "short"})
    with pytest.raises(ImproperlyConfigured):
        validate_production_environment({**base, "DJANGO_SECRET_KEY": "p" * 60})
    with pytest.raises(ImproperlyConfigured):
        validate_production_environment(
            {**base, "DJANGO_SECRET_KEY": "dev-" + ("p" * 60)}
        )
    with pytest.raises(ImproperlyConfigured):
        validate_production_environment({**base, "DJANGO_ALLOWED_HOSTS": "*"})
    with pytest.raises(ImproperlyConfigured):
        validate_production_environment(
            {**base, "DATABASE_URL": "sqlite:///db.sqlite3"}
        )
    with pytest.raises(ImproperlyConfigured):
        validate_production_environment(
            {**base, "CSRF_TRUSTED_ORIGINS": "http://app.example.com"}
        )


def test_production_settings_module_rejects_a_weak_secret() -> None:
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
    env["DJANGO_SECRET_KEY"] = "short-secret"
    env["DJANGO_ALLOWED_HOSTS"] = "app.example.com"
    env["DATABASE_URL"] = "postgres://property:property@127.0.0.1:5432/property_dev"
    env["DJANGO_DEBUG"] = "false"
    env.pop("CSRF_TRUSTED_ORIGINS", None)
    result = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "not strong enough" in result.stderr


class _Env(Mapping[str, str]):
    """Mapping that fails if application storage reads backup settings."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def __getitem__(self, key: str) -> str:
        if key.startswith("BACKUP_"):
            raise AssertionError(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def test_file_storage_defaults_to_the_local_filesystem() -> None:
    assert file_storage_config({}) == {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }


def test_file_storage_reads_s3_settings_and_ignores_backup_credentials() -> None:
    config = file_storage_config(
        _Env(
            {
                "FILE_STORAGE_BACKEND": "s3",
                "FILE_STORAGE_S3_ENDPOINT_URL": "https://files.example.test",
                "FILE_STORAGE_S3_BUCKET": "resident-docs",
                "FILE_STORAGE_S3_ACCESS_KEY_ID": "app-key",
                "FILE_STORAGE_S3_SECRET_ACCESS_KEY": "app-secret",
                "BACKUP_S3_ENDPOINT_URL": "https://backups.example.test",
                "BACKUP_S3_BUCKET": "backup-bucket-private",
                "BACKUP_S3_ACCESS_KEY_ID": "backup-key",
                "BACKUP_S3_SECRET_ACCESS_KEY": "backup-secret-should-not-appear",
            }
        )
    )
    text = str(config)
    assert "backup-secret-should-not-appear" not in text
    assert "backup-bucket-private" not in text
    assert "backups.example.test" not in text
    assert "cloudflare" not in text.lower()
    options = config["OPTIONS"]
    assert options["endpoint_url"] == "https://files.example.test"
    assert options["bucket_name"] == "resident-docs"
    assert options["access_key"] == "app-key"
    assert options["secret_key"] == "app-secret"
    assert options["querystring_auth"] is True
    assert options["querystring_expire"] == 300
    assert options["default_acl"] == "private"
    assert "region_name" not in options


def test_file_storage_rejects_incomplete_s3_settings_and_long_lived_urls() -> None:
    with pytest.raises(ImproperlyConfigured):
        file_storage_config({"FILE_STORAGE_BACKEND": "s3"})
    with pytest.raises(ImproperlyConfigured):
        file_storage_config(
            {
                "FILE_STORAGE_BACKEND": "s3",
                "FILE_STORAGE_S3_ENDPOINT_URL": "https://files.example.test",
                "FILE_STORAGE_S3_BUCKET": "resident-docs",
                "FILE_STORAGE_S3_ACCESS_KEY_ID": "app-key",
                "FILE_STORAGE_S3_SECRET_ACCESS_KEY": "app-secret",
                "FILE_STORAGE_QUERYSTRING_EXPIRE": "99999",
            }
        )


def test_storage_code_does_not_hardcode_an_r2_endpoint() -> None:
    storage = (BACKEND_ROOT / "config" / "storage.py").read_text()
    base = (BACKEND_ROOT / "config" / "settings" / "base.py").read_text()
    combined = storage + base
    assert "r2.cloudflarestorage.com" not in combined
    assert "BACKUP_S3" not in combined
    assert "cloudflare" not in combined.lower()


def test_configured_storages_do_not_include_backup_settings() -> None:
    from django.conf import settings

    text = str(settings.STORAGES)
    assert "FileSystemStorage" in text
    assert "BACKUP" not in text
    assert "r2.cloudflarestorage.com" not in text
