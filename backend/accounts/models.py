"""Email-identified user. Workspace roles live on memberships, not here."""

from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    @classmethod
    def normalize_user_email(cls, email: str) -> str:
        if not isinstance(email, str):
            raise ValueError("An email address is required.")
        normalized = cls.normalize_email(email).strip().lower()
        if not normalized:
            raise ValueError("An email address is required.")
        try:
            validate_email(normalized)
        except ValidationError as exc:
            raise ValueError("Enter a valid email address.") from exc
        return normalized

    def get_by_natural_key(self, username: str | None) -> User:
        if not username:
            raise self.model.DoesNotExist("User matching query does not exist.")
        try:
            email = self.normalize_user_email(username)
        except ValueError as exc:
            raise self.model.DoesNotExist(
                "User matching query does not exist."
            ) from exc
        return self.get(email=email)

    async def aget_by_natural_key(self, username: str | None) -> User:
        if not username:
            raise self.model.DoesNotExist("User matching query does not exist.")
        try:
            email = self.normalize_user_email(username)
        except ValueError as exc:
            raise self.model.DoesNotExist(
                "User matching query does not exist."
            ) from exc
        return await self.aget(email=email)

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        normalized = self.normalize_user_email(email)
        user = self.model(email=normalized, **extra_fields)
        if password is None:
            user.set_unusable_password()
        else:
            validate_password(password, user)
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if not password:
            raise ValueError("Superuser must have a password.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Platform account. A person may belong to more than one workspace."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(
        "email address",
        unique=True,
        help_text="Sign-in identifier. Stored in lowercase.",
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(
        default=False,
        help_text=(
            "Platform operator access to Django admin. This is not a workspace role."
        ),
    )
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    EMAIL_FIELD = "email"

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
            ),
        ]

    def save(self, **kwargs: Any) -> None:
        if self.email:
            self.email = self.__class__.objects.normalize_user_email(self.email)
        super().save(**kwargs)

    def get_full_name(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email

    def get_short_name(self) -> str:
        return self.first_name or self.email
