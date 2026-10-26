"""Session login for the web app. Platform admin remains a separate sign-in."""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.exceptions import (
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User
from accounts.passwords import (
    INVALID_LINK,
    PASSWORD_UPDATED,
    RESET_SENT,
    invalidate_user_sessions,
    try_send_password_reset,
    user_from_uid,
)
from organizations.serializers import session_payload


class RegisterSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    password = serializers.CharField(
        trim_whitespace=False, min_length=8, max_length=256
    )
    first_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    last_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )

    def validate_email(self, value: str) -> str:
        try:
            normalized = User.objects.normalize_user_email(value)
        except ValueError as exc:
            raise serializers.ValidationError("Enter a valid email address.") from exc
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return normalized

    def validate_first_name(self, value: str) -> str:
        return value.strip()

    def validate_last_name(self, value: str) -> str:
        return value.strip()


class LoginSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, max_length=256)

    def validate_email(self, value: str) -> str:
        try:
            return User.objects.normalize_user_email(value)
        except ValueError as exc:
            raise serializers.ValidationError("Enter a valid email address.") from exc


def enforce_browser_csrf(request: Request) -> None:
    """Reject unsafe anonymous requests that skipped session authentication.

    SessionAuthentication only checks CSRF after a user is already signed in.
    Login and registration are anonymous, and DRF marks API views CSRF-exempt,
    so those two views have to run the check themselves.
    """
    django_request = request._request
    if not isinstance(django_request, HttpRequest):
        raise PermissionDenied()
    checker = CsrfViewMiddleware(lambda _incoming: HttpResponse())

    def guarded(_incoming: HttpRequest) -> HttpResponse:
        return HttpResponse()

    checker.process_request(django_request)
    failure = checker.process_view(django_request, guarded, (), {})
    if failure is not None:
        raise PermissionDenied()


def _active_user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User) or not user.is_active:
        raise NotAuthenticated()
    return user


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request)})


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        enforce_browser_csrf(request)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=data["email"],
                    password=data["password"],
                    first_name=data.get("first_name", ""),
                    last_name=data.get("last_name", ""),
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"email": "An account with this email already exists."}
            ) from exc
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)}) from exc
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(session_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        enforce_browser_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if not isinstance(user, User):
            raise ValidationError(
                {"non_field_errors": ["Email or password is incorrect."]}
            )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(session_payload(user))


class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        _active_user(request)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionView(APIView):
    def get(self, request: Request) -> Response:
        return Response(session_payload(_active_user(request)))


class PasswordResetRequestSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        try:
            return User.objects.normalize_user_email(value)
        except ValueError as exc:
            raise serializers.ValidationError("Enter a valid email address.") from exc


class PasswordResetConfirmSerializer(serializers.Serializer[dict[str, str]]):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, max_length=256)


class PasswordChangeSerializer(serializers.Serializer[dict[str, str]]):
    current_password = serializers.CharField(trim_whitespace=False, max_length=256)
    password = serializers.CharField(trim_whitespace=False, max_length=256)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request: Request) -> Response:
        enforce_browser_csrf(request)
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email=serializer.validated_data["email"],
            is_active=True,
        ).first()
        if user is not None:
            try_send_password_reset(user)
        return Response({"detail": RESET_SENT})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_confirm"

    def post(self, request: Request) -> Response:
        enforce_browser_csrf(request)
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = user_from_uid(serializer.validated_data["uid"])
        token = serializer.validated_data["token"]
        if user is None or not default_token_generator.check_token(user, token):
            raise ValidationError({"non_field_errors": [INVALID_LINK]})
        password = serializer.validated_data["password"]
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)}) from exc
        user.set_password(password)
        user.save(update_fields=["password"])
        invalidate_user_sessions(user)
        return Response({"detail": PASSWORD_UPDATED})


class PasswordChangeView(APIView):
    def post(self, request: Request) -> Response:
        user = _active_user(request)
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not user.check_password(serializer.validated_data["current_password"]):
            raise ValidationError(
                {"current_password": ["The current password is incorrect."]}
            )
        password = serializer.validated_data["password"]
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)}) from exc
        user.set_password(password)
        user.save(update_fields=["password"])
        current = request.session.session_key
        keep = current if isinstance(current, str) else None
        invalidate_user_sessions(user, keep=keep)
        update_session_auth_hash(request, user)
        return Response({"detail": "Your password has been changed."})
