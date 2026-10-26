from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.core.cache import cache
from django.test import Client
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import User
from accounts.passwords import INVALID_LINK, PASSWORD_UPDATED, RESET_SENT

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "fresh-stable-lantern"


def make_user(email: str = "ada@example.com") -> User:
    return User.objects.create_user(email=email, password=PASSWORD, first_name="Ada")


def reset_parts() -> tuple[str, str]:
    assert len(mail.outbox) == 1
    body = str(mail.outbox[0].body)
    match = re.search(r"https?://\S+", body)
    assert match is not None
    query = parse_qs(urlsplit(match.group(0)).query)
    return query["uid"][0], query["token"][0]


@pytest.mark.django_db
def test_password_reset_response_does_not_reveal_whether_the_account_exists() -> None:
    make_user()
    api = APIClient()
    known = api.post(
        "/api/v1/auth/password/reset/",
        {"email": "Ada@Example.com"},
        format="json",
    )
    missing = api.post(
        "/api/v1/auth/password/reset/",
        {"email": "missing@example.com"},
        format="json",
    )
    assert known.status_code == 200
    assert known.json() == {"detail": RESET_SENT}
    assert missing.json() == known.json()
    assert "ada@example.com" not in known.content.decode()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ada@example.com"]
    assert "/reset-password?" in mail.outbox[0].body


@pytest.mark.django_db
def test_password_reset_token_works_once_and_drops_other_sessions() -> None:
    user = make_user()
    browser = Client()
    assert browser.login(username=user.email, password=PASSWORD)
    assert browser.get("/api/v1/auth/session/").status_code == 200

    api = APIClient()
    requested = api.post(
        "/api/v1/auth/password/reset/",
        {"email": user.email},
        format="json",
    )
    assert requested.status_code == 200
    uid, token = reset_parts()
    confirmed = api.post(
        "/api/v1/auth/password/reset/confirm/",
        {"uid": uid, "token": token, "password": NEW_PASSWORD},
        format="json",
    )
    assert confirmed.status_code == 200
    assert confirmed.json() == {"detail": PASSWORD_UPDATED}
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert browser.get("/api/v1/auth/session/").status_code == 403

    again = api.post(
        "/api/v1/auth/password/reset/confirm/",
        {"uid": uid, "token": token, "password": "another-stable-lantern"},
        format="json",
    )
    assert again.status_code == 400
    assert again.json()["error"]["details"]["non_field_errors"] == [INVALID_LINK]
    assert user.check_password(NEW_PASSWORD)

    signed_in = api.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": NEW_PASSWORD},
        format="json",
    )
    assert signed_in.status_code == 200
    rejected = api.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert rejected.status_code == 400


@pytest.mark.django_db
def test_password_reset_token_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    user = make_user()
    start = datetime(2026, 10, 26, 12, 0, 0)
    monkeypatch.setattr(PasswordResetTokenGenerator, "_now", lambda self: start)
    api = APIClient()
    api.post(
        "/api/v1/auth/password/reset/",
        {"email": user.email},
        format="json",
    )
    uid, token = reset_parts()
    monkeypatch.setattr(
        PasswordResetTokenGenerator,
        "_now",
        lambda self: start + timedelta(hours=1, seconds=1),
    )
    expired = api.post(
        "/api/v1/auth/password/reset/confirm/",
        {"uid": uid, "token": token, "password": NEW_PASSWORD},
        format="json",
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["details"]["non_field_errors"] == [INVALID_LINK]
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_password_reset_rejects_a_bad_token() -> None:
    user = make_user()
    api = APIClient()
    api.post(
        "/api/v1/auth/password/reset/",
        {"email": user.email},
        format="json",
    )
    uid, _token = reset_parts()
    bad = api.post(
        "/api/v1/auth/password/reset/confirm/",
        {"uid": uid, "token": "not-a-real-token", "password": NEW_PASSWORD},
        format="json",
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["details"]["non_field_errors"] == [INVALID_LINK]
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_password_reset_endpoints_are_throttled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache.clear()
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "password_reset", "2/hour")
    monkeypatch.setitem(
        ScopedRateThrottle.THROTTLE_RATES,
        "password_reset_confirm",
        "2/hour",
    )
    api = APIClient()
    statuses = [
        api.post(
            "/api/v1/auth/password/reset/",
            {"email": "missing@example.com"},
            format="json",
        ).status_code
        for _ in range(3)
    ]
    assert statuses == [200, 200, 429]
    confirm_statuses = [
        api.post(
            "/api/v1/auth/password/reset/confirm/",
            {"uid": "x", "token": "y", "password": NEW_PASSWORD},
            format="json",
        ).status_code
        for _ in range(3)
    ]
    assert confirm_statuses == [400, 400, 429]
