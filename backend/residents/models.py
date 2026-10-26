"""Resident contact profiles. A profile is not a login and not a stay."""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Resident(models.Model):
    """Contact profile for one person in one workspace.

    The fields are the ones a booking or tenancy needs: a name, an optional
    phone, and an optional email. Emergency contacts, identity numbers, and
    dates of birth are not collected. `user` is the optional sign-in, and it
    has to be a resident member of this workspace.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="residents",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resident_profiles",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                condition=models.Q(user__isnull=False),
                name="resident_one_login",
            ),
        ]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self) -> None:
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.email = self.email.strip().lower()
        self.phone = self.phone.strip()
        if not self.first_name:
            raise ValidationError({"first_name": "Enter a first name."})
        if not self.last_name:
            raise ValidationError({"last_name": "Enter a last name."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)
