"""Password reset links and session invalidation."""

from __future__ import annotations

import binascii
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.core.exceptions import SuspiciousOperation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from accounts.models import User

logger = logging.getLogger(__name__)

RESET_SENT = "If an account exists for that email, a reset link is on its way."
INVALID_LINK = "This reset link is invalid or has expired."
PASSWORD_UPDATED = "Your password has been updated."


def frontend_base_url() -> str:
    raw = getattr(settings, "FRONTEND_BASE_URL", "http://127.0.0.1:43123")
    if not isinstance(raw, str) or not raw.strip():
        return "http://127.0.0.1:43123"
    return raw.rstrip("/")


def user_from_uid(uid: str) -> User | None:
    try:
        raw = force_str(urlsafe_base64_decode(uid))
        return User.objects.filter(pk=raw, is_active=True).first()
    except (
        ValueError,
        TypeError,
        binascii.Error,
        UnicodeDecodeError,
        DjangoValidationError,
    ):
        return None


def reset_url(user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
    token = default_token_generator.make_token(user)
    return f"{frontend_base_url()}/reset-password?uid={uid}&token={token}"


def send_password_reset(user: User) -> None:
    url = reset_url(user)
    send_mail(
        subject="Reset your Rent It HQ password",
        message=(
            "Use this link to set a new password. "
            "It expires in one hour and works once.\n\n"
            f"{url}\n\n"
            "If you did not ask for this, you can ignore this email.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def try_send_password_reset(user: User) -> None:
    try:
        send_password_reset(user)
    except (OSError, ValueError):
        logger.exception("Password reset email could not be sent.")


def invalidate_user_sessions(user: User, *, keep: str | None = None) -> None:
    user_id = str(user.pk)
    keys: list[str] = []
    for session in Session.objects.iterator():
        if session.session_key == keep:
            continue
        try:
            data = session.get_decoded()
        except (SuspiciousOperation, ValueError):
            continue
        auth_id = data.get("_auth_user_id")
        if isinstance(auth_id, str) and auth_id == user_id:
            keys.append(session.session_key)
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
