"""Who may read or change resident charges. Maintenance is refused."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from organizations.models import Membership

MONEY_WRITE_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.FINANCE,
    }
)
MONEY_READ_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.FINANCE,
        Membership.Role.PROPERTY_MANAGER,
    }
)


def ensure_can_read_billing(actor: Membership) -> None:
    """Staff who run the property may read. A resident may read only their own."""
    if actor.role in MONEY_READ_ROLES or actor.role == Membership.Role.RESIDENT:
        return
    raise PermissionDenied()


def ensure_can_write_billing(actor: Membership) -> None:
    if actor.role not in MONEY_WRITE_ROLES:
        raise PermissionDenied()


def ensure_staff_billing(actor: Membership) -> None:
    """Arrears names every resident, so residents are refused."""
    if actor.role not in MONEY_READ_ROLES:
        raise PermissionDenied()
