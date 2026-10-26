"""Workspace tenant, membership, and security-relevant audit rows."""

from __future__ import annotations

import re
import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from organizations.validation import currency_code_or_error, timezone_name_or_error


class Workspace(models.Model):
    """One SaaS tenant. Currency is fixed for the workspace, not a global default."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    currency_code = models.CharField(
        max_length=3,
        help_text="ISO 4217 code stored uppercase. Not a catalog lookup.",
    )
    timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text="IANA timezone used later for property-local dates.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Platform operators change this. Workspace owners do not.",
    )
    plan_code = models.CharField(
        max_length=32,
        default="placeholder",
        help_text=(
            "Platform label only. The API does not enforce a feature limit from it."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(currency_code__regex=r"^[A-Z]{3}$"),
                name="organizations_workspace_currency_shape",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "suspended"]),
                name="organizations_workspace_status_known",
            ),
            models.CheckConstraint(
                condition=models.Q(plan_code__regex=r"^[a-z][a-z0-9_]{0,31}$"),
                name="organizations_workspace_plan_shape",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a workspace name."})
        try:
            self.currency_code = currency_code_or_error(self.currency_code)
        except ValidationError as exc:
            raise ValidationError({"currency_code": exc.messages}) from exc
        try:
            self.timezone = timezone_name_or_error(self.timezone)
        except ValidationError as exc:
            raise ValidationError({"timezone": exc.messages}) from exc
        if self.status not in self.Status.values:
            raise ValidationError({"status": "Choose a valid workspace status."})
        self.plan_code = self.plan_code.strip().lower()
        if re.fullmatch(r"[a-z][a-z0-9_]{0,31}", self.plan_code) is None:
            raise ValidationError({"plan_code": "Use a short plan code."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Membership(models.Model):
    """One user, one workspace, one role. Roles never grant another workspace."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        PROPERTY_MANAGER = "property_manager", "Property manager"
        FINANCE = "finance", "Finance"
        MAINTENANCE = "maintenance", "Maintenance"
        RESIDENT = "resident", "Resident"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                name="organizations_membership_workspace_user_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    role__in=[
                        "owner",
                        "property_manager",
                        "finance",
                        "maintenance",
                        "resident",
                    ]
                ),
                name="organizations_membership_role_known",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="org_membership_user_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.workspace_id} ({self.role})"

    def clean(self) -> None:
        if self.role not in self.Role.values:
            raise ValidationError({"role": "Choose a valid role."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class AuditEvent(models.Model):
    """Security-relevant workspace changes. Not exposed on the product API."""

    class Action(models.TextChoices):
        WORKSPACE_CREATED = "workspace.created", "Workspace created"
        WORKSPACE_UPDATED = "workspace.updated", "Workspace updated"
        WORKSPACE_DELETED = "workspace.deleted", "Workspace deleted"
        MEMBERSHIP_CREATED = "membership.created", "Membership created"
        MEMBERSHIP_UPDATED = "membership.updated", "Membership updated"
        MEMBERSHIP_DEACTIVATED = "membership.deactivated", "Membership deactivated"
        INVOICE_ISSUED = "invoice.issued", "Invoice issued"
        INVOICE_VOIDED = "invoice.voided", "Invoice voided"
        PAYMENT_RECORDED = "payment.recorded", "Payment recorded"
        PAYMENT_VOIDED = "payment.voided", "Payment voided"
        ALLOCATION_CREATED = "allocation.created", "Allocation created"
        ALLOCATION_REVERSED = "allocation.reversed", "Allocation reversed"
        REFUND_RECORDED = "refund.recorded", "Refund recorded"
        RESIDENT_PHONE_UPDATED = "resident.phone_updated", "Resident phone updated"
        RESIDENT_EMAIL_UPDATED = "resident.email_updated", "Resident email updated"
        MAINTENANCE_CREATED = "maintenance.created", "Maintenance request created"
        MAINTENANCE_ASSIGNED = "maintenance.assigned", "Maintenance request assigned"
        MAINTENANCE_STATUS_CHANGED = (
            "maintenance.status_changed",
            "Maintenance status changed",
        )
        MAINTENANCE_COST_RECORDED = (
            "maintenance.cost_recorded",
            "Maintenance cost recorded",
        )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=64, choices=Action.choices)
    target_type = models.CharField(max_length=64)
    target_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["workspace", "created_at"],
                name="org_audit_ws_created",
            ),
        ]

    def __str__(self) -> str:
        return self.action
