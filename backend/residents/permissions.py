"""Staff and resident access for people, bookings, and stays."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from organizations.models import Membership

STAFF_READ_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
        Membership.Role.MAINTENANCE,
    }
)
STAFF_WRITE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
    }
)


def ensure_can_read_occupancy(actor: Membership) -> None:
    """Staff read every record. A resident may read only their own."""
    if actor.role in STAFF_READ_ROLES or actor.role == Membership.Role.RESIDENT:
        return
    raise PermissionDenied()


def ensure_can_write_occupancy(actor: Membership) -> None:
    if actor.role not in STAFF_WRITE_ROLES:
        raise PermissionDenied()


def ensure_staff_read(actor: Membership) -> None:
    """Availability lists other people, so residents are refused."""
    if actor.role not in STAFF_READ_ROLES:
        raise PermissionDenied()
