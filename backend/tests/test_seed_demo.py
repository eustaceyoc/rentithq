"""DEMO workspace seed. Passwords are supplied by the test, not the repo."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from accounts.models import User
from billing.balances import invoice_outstanding
from billing.models import Invoice, Payment
from bookings.models import Booking
from maintenance.models import MaintenanceRequest
from organizations.demo_seed import DEMO_PAYER_EMAIL, DEMO_WORKSPACE_NAME
from organizations.models import Membership, Workspace
from organizations.services import create_workspace
from properties.models import Property, Space
from properties.services import create_property, create_space
from reports.services import occupancy_report
from residents.models import Resident
from residents.services import create_resident
from tenancies.models import Tenancy

EMAIL = "demo.owner@example.com"
PASSWORD = "harbour-ridge-ledger-94"
RESIDENT_PASSWORD = "payer-ledger-harbour-72"


def _use_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_EMAIL", EMAIL)
    monkeypatch.setenv("DEMO_PASSWORD", PASSWORD)
    monkeypatch.delenv("DEMO_RESIDENT_PASSWORD", raising=False)


@pytest.mark.django_db
def test_seed_refuses_to_invent_a_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_EMAIL", raising=False)
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="does not invent a password"):
        call_command("seed_demo")
    assert User.objects.filter(email=EMAIL).count() == 0


@pytest.mark.django_db
def test_seed_tops_up_the_demo_workspace_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_owner(monkeypatch)
    owner = User.objects.create_user(
        email=EMAIL,
        password=PASSWORD,
        first_name="Demo",
        last_name="Owner",
    )
    workspace = create_workspace(
        owner=owner,
        name=DEMO_WORKSPACE_NAME,
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )
    other_owner = User.objects.create_user(
        email="other.owner@example.com",
        password=PASSWORD,
        first_name="Other",
        last_name="Owner",
    )
    other = create_workspace(
        owner=other_owner,
        name="Other House",
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )
    actor = Membership.objects.get(workspace=workspace, user=owner)
    harbour = create_property(
        actor=actor,
        data={"name": "DEMO Harbour House", "address": "14 Harbour Road, Osu, Accra"},
    )
    create_space(
        actor=actor,
        data={"name": "Flat 1", "kind": "unit", "property_id": harbour.id},
    )
    create_resident(
        actor=actor,
        data={
            "first_name": "Ama",
            "last_name": "Mensah",
            "email": "demo.ama@example.com",
            "phone": "0244111001",
        },
    )
    create_resident(
        actor=actor,
        data={
            "first_name": "Kojo",
            "last_name": "Boateng",
            "email": "demo.kojo@example.com",
            "phone": "0202002202",
        },
    )

    call_command("seed_demo")
    call_command("seed_demo")

    assert Workspace.objects.filter(name=DEMO_WORKSPACE_NAME).count() == 1
    assert Property.objects.filter(workspace=workspace).count() == 2
    assert Property.objects.filter(workspace=other).count() == 0
    assert Space.objects.filter(property=harbour, name="Flat 1").count() == 1
    assert Space.objects.filter(workspace=workspace).count() == 8
    assert (
        Resident.objects.filter(
            workspace=workspace, email="demo.ama@example.com"
        ).count()
        == 1
    )
    assert not User.objects.filter(email=DEMO_PAYER_EMAIL).exists()

    paid = Invoice.objects.get(
        workspace=workspace, lines__description="DEMO rent paid in full"
    )
    partial = Invoice.objects.get(
        workspace=workspace, lines__description="DEMO rent partly paid"
    )
    overdue = Invoice.objects.get(
        workspace=workspace, lines__description="DEMO rent overdue"
    )
    open_invoice = Invoice.objects.get(
        workspace=workspace,
        lines__description="DEMO rent open for Paystack",
    )
    today = timezone.now().astimezone(ZoneInfo("Africa/Accra")).date()
    assert invoice_outstanding(paid) == 0
    assert invoice_outstanding(partial) == Decimal("500.0000")
    assert invoice_outstanding(overdue) == Decimal("450.0000")
    assert overdue.due_on < today
    assert invoice_outstanding(open_invoice) == Decimal("750.0000")
    assert open_invoice.due_on > today
    assert Payment.objects.filter(workspace=workspace).count() == 2
    assert Invoice.objects.filter(workspace=workspace).count() == 4

    report = occupancy_report(actor, on=today, within_days=30)
    assert report["upcoming_count"] >= 1
    assert any(
        item["resident_name"] == "Ama Mensah" for item in report["upcoming_move_outs"]
    )
    ama = Tenancy.objects.get(
        workspace=workspace, resident__email="demo.ama@example.com"
    )
    assert ama.end_date is not None
    assert timedelta(0) <= (ama.end_date - today) <= timedelta(days=30)
    yaw = Booking.objects.get(
        workspace=workspace, resident__email="demo.yaw@example.com"
    )
    assert yaw.start_date > today

    statuses = set(
        MaintenanceRequest.objects.filter(workspace=workspace).values_list(
            "status",
            flat=True,
        )
    )
    assert statuses == {"open", "assigned", "in_progress", "completed", "cancelled"}
    assert MaintenanceRequest.objects.filter(workspace=workspace).count() == 5


@pytest.mark.django_db
def test_resident_login_is_optional_and_not_printed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_owner(monkeypatch)
    monkeypatch.setenv("DEMO_RESIDENT_PASSWORD", RESIDENT_PASSWORD)
    call_command("seed_demo")
    call_command("seed_demo")
    user = User.objects.get(email=DEMO_PAYER_EMAIL)
    assert user.check_password(RESIDENT_PASSWORD)
    workspace = Workspace.objects.get(name=DEMO_WORKSPACE_NAME)
    assert Membership.objects.filter(
        workspace=workspace,
        user=user,
        role=Membership.Role.RESIDENT,
        is_active=True,
    ).exists()
    resident = Resident.objects.get(workspace=workspace, email=DEMO_PAYER_EMAIL)
    assert resident.user_id == user.id
    assert (
        Membership.objects.filter(
            workspace=workspace, role=Membership.Role.RESIDENT
        ).count()
        == 1
    )
