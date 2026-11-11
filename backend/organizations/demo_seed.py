"""Sample DEMO workspace. Sign-in passwords come from the environment."""

from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.utils import timezone

from accounts.models import User
from billing.models import Allocation, Invoice, Payment
from billing.services import allocate_payment, issue_invoice, record_payment
from bookings.models import Booking
from bookings.services import create_booking, update_booking
from maintenance.models import MaintenanceRequest
from maintenance.services import create_request, update_request
from organizations.models import Membership, Workspace
from organizations.services import add_member, create_workspace
from properties.models import Building, Floor, Property, Space
from properties.services import (
    create_building,
    create_floor,
    create_property,
    create_space,
)
from residents.models import Resident
from residents.services import create_resident, update_resident
from tenancies.models import Assignment, Tenancy
from tenancies.services import create_tenancy, update_assignment, update_tenancy

DEMO_WORKSPACE_NAME = "DEMO workspace"
DEMO_PAYER_EMAIL = "demo.payer@example.com"

_ONE = Decimal("1")


def _credentials() -> tuple[str, str]:
    email = os.environ.get("DEMO_EMAIL", "").strip()
    password = os.environ.get("DEMO_PASSWORD", "")
    if not email or not password.strip():
        raise CommandError(
            "Set DEMO_EMAIL and DEMO_PASSWORD in the environment. "
            "This command does not invent a password."
        )
    try:
        normalized = User.objects.normalize_user_email(email)
    except ValueError as exc:
        raise CommandError("DEMO_EMAIL is not a valid email address.") from exc
    return normalized, password


def _owner(email: str, password: str) -> User:
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User(email=email, first_name="Demo", last_name="Owner")
    try:
        validate_password(password, user)
    except ValidationError as exc:
        raise CommandError(
            "DEMO_PASSWORD was rejected. " + " ".join(exc.messages)
        ) from exc
    user.email = email
    user.first_name = user.first_name or "Demo"
    user.last_name = user.last_name or "Owner"
    user.is_active = True
    user.set_password(password)
    user.save()
    return user


def _workspace(owner: User) -> Workspace:
    membership = (
        Membership.objects.filter(
            user=owner,
            role=Membership.Role.OWNER,
            is_active=True,
            workspace__name=DEMO_WORKSPACE_NAME,
        )
        .select_related("workspace")
        .first()
    )
    if membership is not None:
        workspace = membership.workspace
    else:
        workspace = create_workspace(
            owner=owner,
            name=DEMO_WORKSPACE_NAME,
            currency_code="GHS",
            timezone_name="Africa/Accra",
        )
    if workspace.plan_code != "demo":
        workspace.plan_code = "demo"
        workspace.save(update_fields=["plan_code", "updated_at"])
    return workspace


def _today(workspace: Workspace) -> date:
    return timezone.now().astimezone(ZoneInfo(workspace.timezone)).date()


def _property(actor: Membership, name: str, address: str) -> Property:
    row = Property.objects.filter(workspace=actor.workspace, name__iexact=name).first()
    if row is None:
        row = create_property(actor=actor, data={"name": name, "address": address})
    return row


def _building(actor: Membership, prop: Property, name: str) -> Building:
    row = Building.objects.filter(property=prop, name__iexact=name).first()
    if row is None:
        row = create_building(
            actor=actor,
            data={"property_id": prop.id, "name": name},
        )
    return row


def _floor(
    actor: Membership,
    prop: Property,
    building: Building,
    name: str,
) -> Floor:
    row = Floor.objects.filter(building=building, name__iexact=name).first()
    if row is None:
        row = create_floor(
            actor=actor,
            data={
                "property_id": prop.id,
                "building_id": building.id,
                "name": name,
            },
        )
    return row


def _space(
    actor: Membership,
    prop: Property,
    name: str,
    kind: str,
    *,
    building: Building | None = None,
    floor: Floor | None = None,
) -> Space:
    row = Space.objects.filter(
        property=prop,
        name__iexact=name,
        building=building,
        floor=floor,
    ).first()
    if row is not None:
        return row
    data: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "property_id": prop.id,
    }
    if building is not None:
        data["building_id"] = building.id
    if floor is not None:
        data["floor_id"] = floor.id
    return create_space(actor=actor, data=data)


def _resident(
    actor: Membership,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
) -> Resident:
    row = Resident.objects.filter(
        workspace=actor.workspace, email__iexact=email
    ).first()
    if row is not None:
        return row
    return create_resident(
        actor=actor,
        data={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
        },
    )


def _checked_in(
    actor: Membership,
    resident: Resident,
    space: Space,
    start: date,
    end: date,
    fee: Decimal,
) -> None:
    tenancy = Tenancy.objects.filter(
        workspace=actor.workspace,
        resident=resident,
        status=Tenancy.Status.ACTIVE,
    ).first()
    if tenancy is None:
        create_tenancy(
            actor=actor,
            data={
                "resident_id": resident.id,
                "start_date": start,
                "end_date": end,
                "fee_amount": fee,
                "fee_period": Tenancy.FeePeriod.MONTH,
                "space_id": space.id,
                "check_in": True,
            },
        )
        return
    update_tenancy(actor=actor, raw_id=str(tenancy.id), data={"end_date": end})
    stay = Assignment.objects.filter(
        tenancy=tenancy,
        status=Assignment.Status.ACTIVE,
    ).first()
    if stay is not None:
        update_assignment(
            actor=actor,
            raw_id=str(stay.id),
            data={"end_date": end},
        )


def _move_in(
    actor: Membership,
    resident: Resident,
    space: Space,
    start: date,
    end: date,
) -> None:
    booking = Booking.objects.filter(
        workspace=actor.workspace,
        resident=resident,
        status=Booking.Status.CONFIRMED,
    ).first()
    if booking is None:
        create_booking(
            actor=actor,
            data={
                "resident_id": resident.id,
                "space_id": space.id,
                "start_date": start,
                "end_date": end,
            },
        )
        return
    update_booking(
        actor=actor,
        raw_id=str(booking.id),
        data={"start_date": start, "end_date": end},
    )


def _invoice(
    actor: Membership,
    resident: Resident,
    marker: str,
    amount: Decimal,
    issued: date,
    due: date,
) -> Invoice:
    existing = (
        Invoice.objects.filter(
            workspace=actor.workspace,
            lines__description=marker,
        )
        .order_by("id")
        .first()
    )
    if existing is not None:
        existing.issued_on = issued
        existing.due_on = due
        existing.save()
        return existing
    return issue_invoice(
        actor=actor,
        data={
            "resident_id": resident.id,
            "issued_on": issued,
            "due_on": due,
            "lines": [
                {
                    "description": marker,
                    "quantity": _ONE,
                    "unit_amount": amount,
                }
            ],
        },
    )


def _payment(
    actor: Membership,
    resident: Resident,
    reference: str,
    amount: Decimal,
    paid_on: date,
    method: str,
    invoice: Invoice,
) -> None:
    payment = Payment.objects.filter(
        workspace=actor.workspace,
        external_reference=reference,
    ).first()
    if payment is None:
        payment = record_payment(
            actor=actor,
            data={
                "resident_id": resident.id,
                "amount": amount,
                "paid_on": paid_on,
                "method": method,
                "external_reference": reference,
            },
        )
    elif payment.paid_on != paid_on:
        payment.paid_on = paid_on
        payment.save(update_fields=["paid_on", "updated_at"])
    if Allocation.objects.filter(payment=payment, invoice=invoice).exists():
        return
    allocate_payment(
        actor=actor,
        data={
            "payment_id": payment.id,
            "invoice_id": invoice.id,
            "amount": amount,
        },
    )


def _job(
    actor: Membership,
    description: str,
    priority: str,
    prop: Property,
    space: Space,
    resident: Resident | None,
    target: str,
) -> None:
    row = MaintenanceRequest.objects.filter(
        workspace=actor.workspace,
        description=description,
    ).first()
    if row is None:
        payload: dict[str, Any] = {
            "description": description,
            "priority": priority,
            "property_id": prop.id,
            "space_id": space.id,
        }
        if resident is not None:
            payload["resident_id"] = resident.id
        if target == MaintenanceRequest.Status.ASSIGNED:
            payload["assignee_id"] = actor.user_id
        row = create_request(actor=actor, data=payload)
    if row.status == target:
        return
    if target == MaintenanceRequest.Status.CANCELLED and row.status == "open":
        update_request(actor=actor, raw_id=str(row.id), data={"status": "cancelled"})
        return
    if target == MaintenanceRequest.Status.IN_PROGRESS and row.status == "open":
        update_request(
            actor=actor,
            raw_id=str(row.id),
            data={"status": "in_progress", "assignee_id": actor.user_id},
        )
        return
    if target != MaintenanceRequest.Status.COMPLETED:
        return
    if row.status == MaintenanceRequest.Status.OPEN:
        row = update_request(
            actor=actor,
            raw_id=str(row.id),
            data={"status": "in_progress", "assignee_id": actor.user_id},
        )
    if row.status == MaintenanceRequest.Status.IN_PROGRESS:
        update_request(
            actor=actor,
            raw_id=str(row.id),
            data={
                "status": "completed",
                "completion_note": "The repair is finished.",
                "cost_amount": Decimal("85.0000"),
            },
        )


def _samples(actor: Membership, today: date) -> None:
    harbour = _property(actor, "DEMO Harbour House", "14 Harbour Road, Osu, Accra")
    ridge = _property(actor, "DEMO Ridge Court", "8 Ridge Road, Accra")
    flat_1 = _space(actor, harbour, "Flat 1", Space.Kind.UNIT)
    flat_2 = _space(actor, harbour, "Flat 2", Space.Kind.UNIT)
    flat_3 = _space(actor, harbour, "Flat 3", Space.Kind.UNIT)
    block = _building(actor, ridge, "Main block")
    ground = _floor(actor, ridge, block, "Ground")
    first = _floor(actor, ridge, block, "First")
    _space(actor, ridge, "Room A", Space.Kind.ROOM)
    room_1 = _space(
        actor, ridge, "Room 1", Space.Kind.ROOM, building=block, floor=ground
    )
    room_2 = _space(
        actor, ridge, "Room 2", Space.Kind.ROOM, building=block, floor=ground
    )
    room_3 = _space(
        actor, ridge, "Room 3", Space.Kind.ROOM, building=block, floor=first
    )
    room_4 = _space(
        actor, ridge, "Room 4", Space.Kind.ROOM, building=block, floor=first
    )

    ama = _resident(actor, "Ama", "Mensah", "demo.ama@example.com", "0244111001")
    kojo = _resident(actor, "Kojo", "Boateng", "demo.kojo@example.com", "0202002202")
    efua = _resident(actor, "Efua", "Owusu", DEMO_PAYER_EMAIL, "0244550190")
    yaw = _resident(actor, "Yaw", "Darko", "demo.yaw@example.com", "0277004411")
    abena = _resident(actor, "Abena", "Sarpong", "demo.abena@example.com", "0503322188")

    _checked_in(
        actor,
        ama,
        flat_1,
        today - timedelta(days=50),
        today + timedelta(days=12),
        Decimal("1500.0000"),
    )
    _checked_in(
        actor,
        kojo,
        flat_2,
        today - timedelta(days=40),
        today + timedelta(days=200),
        Decimal("900.0000"),
    )
    _checked_in(
        actor,
        efua,
        flat_3,
        today - timedelta(days=20),
        today + timedelta(days=160),
        Decimal("750.0000"),
    )
    _checked_in(
        actor,
        abena,
        room_1,
        today - timedelta(days=15),
        today + timedelta(days=16),
        Decimal("450.0000"),
    )
    _move_in(actor, yaw, room_2, today + timedelta(days=8), today + timedelta(days=70))

    paid = _invoice(
        actor,
        ama,
        "DEMO rent paid in full",
        Decimal("1500.0000"),
        today - timedelta(days=20),
        today - timedelta(days=8),
    )
    partial = _invoice(
        actor,
        kojo,
        "DEMO rent partly paid",
        Decimal("900.0000"),
        today - timedelta(days=18),
        today - timedelta(days=4),
    )
    _invoice(
        actor,
        abena,
        "DEMO rent overdue",
        Decimal("450.0000"),
        today - timedelta(days=14),
        today - timedelta(days=2),
    )
    _invoice(
        actor,
        efua,
        "DEMO rent open for Paystack",
        Decimal("750.0000"),
        today,
        today + timedelta(days=7),
    )
    _payment(
        actor,
        ama,
        "DEMO-PAY-AMA",
        Decimal("1500.0000"),
        today,
        Payment.Method.CASH,
        paid,
    )
    _payment(
        actor,
        kojo,
        "DEMO-PAY-KOJO",
        Decimal("400.0000"),
        today,
        Payment.Method.MOBILE_MONEY,
        partial,
    )

    _job(actor, "DEMO: Leaking tap in Flat 1", "high", harbour, flat_1, ama, "open")
    _job(actor, "DEMO: Corridor light out", "normal", ridge, room_4, None, "assigned")
    _job(
        actor,
        "DEMO: Room 1 lock is stiff",
        "urgent",
        ridge,
        room_1,
        abena,
        "in_progress",
    )
    _job(actor, "DEMO: Repainted Room 3", "low", ridge, room_3, None, "completed")
    _job(
        actor,
        "DEMO: Pest call was not needed",
        "normal",
        harbour,
        flat_2,
        kojo,
        "cancelled",
    )


def _payer_login(actor: Membership) -> str:
    raw = os.environ.get("DEMO_RESIDENT_PASSWORD", "")
    if not raw.strip():
        return (
            f" DEMO_RESIDENT_PASSWORD is not set, so {DEMO_PAYER_EMAIL} has no sign-in."
        )
    user = User.objects.filter(email=DEMO_PAYER_EMAIL).first()
    if user is None:
        user = User(email=DEMO_PAYER_EMAIL, first_name="Efua", last_name="Owusu")
    try:
        validate_password(raw, user)
    except ValidationError as exc:
        raise CommandError(
            "DEMO_RESIDENT_PASSWORD was rejected. " + " ".join(exc.messages)
        ) from exc
    user.email = DEMO_PAYER_EMAIL
    user.first_name = user.first_name or "Efua"
    user.last_name = user.last_name or "Owusu"
    user.is_active = True
    user.set_password(raw)
    user.save()
    member = Membership.objects.filter(workspace=actor.workspace, user=user).first()
    if member is None or not member.is_active:
        add_member(
            actor=actor,
            email=DEMO_PAYER_EMAIL,
            role=Membership.Role.RESIDENT,
        )
    resident = Resident.objects.get(
        workspace=actor.workspace,
        email__iexact=DEMO_PAYER_EMAIL,
    )
    if resident.user_id != user.id:
        update_resident(
            actor=actor,
            raw_id=str(resident.id),
            data={"account_email": DEMO_PAYER_EMAIL},
        )
    return f" Payer sign-in is {DEMO_PAYER_EMAIL}. The password was not printed."


def seed_demo() -> str:
    """Create or refresh the labelled DEMO workspace. Safe to run again."""
    email, password = _credentials()
    owner = _owner(email, password)
    workspace = _workspace(owner)
    actor = Membership.objects.get(
        workspace=workspace,
        user=owner,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    if workspace.status != Workspace.Status.ACTIVE:
        return (
            f"{workspace.id} is named {DEMO_WORKSPACE_NAME} but its status is "
            f"{workspace.status}. Sample rows were not added."
        )
    _samples(actor, _today(workspace))
    login = _payer_login(actor)
    return (
        f"{workspace.id} {DEMO_WORKSPACE_NAME} is ready. "
        "Sign in with the DEMO_EMAIL address. The password was not printed." + login
    )
