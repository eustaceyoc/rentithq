"""Plan caps. Null means unlimited. Missing Plan rows are unlimited."""

from __future__ import annotations

from rest_framework.exceptions import ValidationError

from organizations.models import Membership, Plan, Workspace

STAFF_ROLES = frozenset(
    {
        Membership.Role.OWNER,
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
        Membership.Role.MAINTENANCE,
    }
)


def plan_for(workspace: Workspace) -> Plan | None:
    return Plan.objects.filter(plan_code=workspace.plan_code).first()


def property_count(workspace: Workspace) -> int:
    from properties.models import Property

    return Property.objects.filter(workspace=workspace).count()


def staff_seat_count(workspace: Workspace) -> int:
    return Membership.objects.filter(
        workspace=workspace,
        is_active=True,
        role__in=STAFF_ROLES,
    ).count()


def usage(workspace: Workspace) -> dict[str, int | None | str]:
    plan = plan_for(workspace)
    return {
        "plan_code": workspace.plan_code,
        "property_count": property_count(workspace),
        "property_limit": None if plan is None else plan.property_limit,
        "staff_seat_count": staff_seat_count(workspace),
        "staff_seat_limit": None if plan is None else plan.staff_seat_limit,
    }


def ensure_property_capacity(workspace: Workspace) -> None:
    plan = plan_for(workspace)
    if plan is None or plan.property_limit is None:
        return
    count = property_count(workspace)
    if count >= plan.property_limit:
        raise ValidationError(
            {
                "detail": (
                    f"This plan allows {plan.property_limit} "
                    f"{'property' if plan.property_limit == 1 else 'properties'}. "
                    f"This workspace already has {count}."
                )
            }
        )


def ensure_staff_seat(workspace: Workspace, role: str) -> None:
    if role not in STAFF_ROLES:
        return
    plan = plan_for(workspace)
    if plan is None or plan.staff_seat_limit is None:
        return
    count = staff_seat_count(workspace)
    if count >= plan.staff_seat_limit:
        raise ValidationError(
            {
                "detail": (
                    f"This plan allows {plan.staff_seat_limit} "
                    f"{'staff seat' if plan.staff_seat_limit == 1 else 'staff seats'}. "
                    f"This workspace already has {count}."
                )
            }
        )
