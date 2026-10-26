"""Session login for the web app. Platform admin remains a separate sign-in."""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
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
from rest_framework.views import APIView

from accounts.models import User
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
