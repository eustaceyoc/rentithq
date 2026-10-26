"""Who may file, read, and triage maintenance requests."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from organizations.models import Membership

FILE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
        Membership.Role.MAINTENANCE,
        Membership.Role.RESIDENT,
    }
)
READ_ROLES = FILE_ROLES
TRIAGE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
    }
)
UPDATE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.MAINTENANCE,
    }
)
ASSIGNABLE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.MAINTENANCE,
    }
)


def ensure_can_file(actor: Membership) -> None:
    if actor.role not in FILE_ROLES:
        raise PermissionDenied()


def ensure_can_read(actor: Membership) -> None:
    if actor.role not in READ_ROLES:
        raise PermissionDenied()


def ensure_can_update(actor: Membership) -> None:
    """Finance can file and read. They cannot assign or change a request."""
    if actor.role not in UPDATE_ROLES:
        raise PermissionDenied()
