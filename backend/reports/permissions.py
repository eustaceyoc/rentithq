"""Report readers. A resident never receives a workspace total."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from organizations.models import Membership

OCCUPANCY_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
        Membership.Role.MAINTENANCE,
    }
)
MONEY_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
    }
)
MAINTENANCE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
        Membership.Role.MAINTENANCE,
    }
)


def ensure_occupancy_report(actor: Membership) -> None:
    if actor.role not in OCCUPANCY_ROLES:
        raise PermissionDenied()


def ensure_money_report(actor: Membership) -> None:
    if actor.role not in MONEY_ROLES:
        raise PermissionDenied()


def ensure_maintenance_report(actor: Membership) -> None:
    if actor.role not in MAINTENANCE_ROLES:
        raise PermissionDenied()
