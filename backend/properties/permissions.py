"""Server-side property permissions. Hiding a button is not authorization."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from organizations.models import Membership

VIEW_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
        Membership.Role.MAINTENANCE,
    }
)
MANAGE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
    }
)


def ensure_can_view_properties(actor: Membership) -> None:
    if actor.role not in VIEW_ROLES:
        raise PermissionDenied()


def ensure_can_manage_properties(actor: Membership) -> None:
    if actor.role not in MANAGE_ROLES:
        raise PermissionDenied()
