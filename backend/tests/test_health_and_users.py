from __future__ import annotations

import uuid

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.utils import OperationalError
from django.test import Client
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from accounts.models import User
from common.health import HealthView, ReadyView


def test_database_engine_is_postgresql() -> None:
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
    assert settings.AUTH_USER_MODEL == "accounts.User"


@pytest.mark.django_db
def test_health_is_public_and_does_not_leak_configuration(client: Client) -> None:
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "rentithq-api"}
    assert response["Cache-Control"] == "no-store"
    rendered = response.content.decode()
    assert settings.SECRET_KEY not in rendered
    assert "DATABASE_URL" not in rendered
    assert "password" not in rendered.lower()


@pytest.mark.django_db
def test_health_does_not_query_the_database(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_cursor() -> None:
        raise OperationalError("password=property host=db.internal")

    monkeypatch.setattr("common.health.connection.cursor", broken_cursor)
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert "password" not in response.content.decode()
    assert "db.internal" not in response.content.decode()


@pytest.mark.django_db
def test_ready_reports_database_without_details(client: Client) -> None:
    response = client.get("/api/v1/health/ready/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert "password" not in response.content.decode().lower()


@pytest.mark.django_db
def test_ready_hides_database_errors(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_cursor() -> None:
        raise OperationalError("password=property host=db.internal")

    monkeypatch.setattr("common.health.connection.cursor", broken_cursor)
    response = client.get("/api/v1/health/ready/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    rendered = response.content.decode()
    assert "password" not in rendered
    assert "db.internal" not in rendered
    assert "OperationalError" not in rendered


@pytest.mark.django_db
def test_health_post_uses_the_error_shape(client: Client) -> None:
    response = client.post("/api/v1/health/")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_default_permission_denies_anonymous_users() -> None:
    class ProbeView(APIView):
        def get(self, request: Request) -> Response:
            return Response({"ok": True})

    assert IsAuthenticated in ProbeView.permission_classes
    request = APIRequestFactory().get("/probe")
    response = ProbeView.as_view()(request)
    assert response.status_code == 403
    assert response.data["error"]["code"] == "not_authenticated"


def test_health_views_are_explicitly_public() -> None:
    assert AllowAny in HealthView.permission_classes
    assert AllowAny in ReadyView.permission_classes


@pytest.mark.django_db
def test_user_email_is_the_login_identifier_and_is_stored_lowercase() -> None:
    user = User.objects.create_user(
        email="Owner@Example.com",
        password="correct-horse-battery",
        first_name="Ada",
    )
    assert user.email == "owner@example.com"
    assert User.USERNAME_FIELD == "email"
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.check_password("correct-horse-battery")
    assert user.password != "correct-horse-battery"
    found = User.objects.get_by_natural_key("OWNER@example.com")
    assert found.pk == user.pk


@pytest.mark.django_db
def test_common_and_short_passwords_are_rejected() -> None:
    with pytest.raises(ValidationError):
        User.objects.create_user(email="owner@example.com", password="password")


@pytest.mark.django_db(transaction=True)
def test_email_uniqueness_is_case_insensitive() -> None:
    User.objects.create_user(
        email="owner@example.com",
        password="correct-horse-battery",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.bulk_create(
            [
                User(
                    id=uuid.uuid4(),
                    email="OWNER@example.com",
                    password="unused-hash",
                )
            ]
        )


@pytest.mark.django_db
def test_superuser_flag_is_explicit() -> None:
    admin = User.objects.create_superuser(
        email="platform@example.com",
        password="correct-horse-battery",
    )
    assert admin.is_staff is True
    assert admin.is_superuser is True
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="other@example.com",
            password="correct-horse-battery",
            is_staff=False,
        )
