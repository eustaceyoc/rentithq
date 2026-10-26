"""Invoices, payments, allocations, receipts, and arrears."""

from __future__ import annotations

import threading
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from rest_framework.response import Response
from rest_framework.test import APIClient

from accounts.models import User
from billing.models import Allocation, Invoice, Payment, Refund
from billing.services import allocate_payment
from organizations.models import AuditEvent, Membership, Workspace
from organizations.services import add_member, create_workspace
from residents.models import Resident

OTHER = "North Hostel Private"


def rendered(response: Response) -> str:
    text = response.content.decode()
    assert isinstance(text, str)
    return text


def error_code(response: Response) -> str:
    body = response.data
    assert isinstance(body, dict)
    error = body["error"]
    assert isinstance(error, dict)
    code = error["code"]
    assert isinstance(code, str)
    return code


def details(response: Response) -> dict[str, Any]:
    body = response.data
    assert isinstance(body, dict)
    error = body["error"]
    assert isinstance(error, dict)
    payload = error["details"]
    assert isinstance(payload, dict)
    return payload


def detail_text(response: Response) -> str:
    payload = details(response)
    for key in ("detail", "amount", "lines", "non_field_errors"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            return str(value[0])
    return rendered(response)


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password="correct-horse-battery")


def make_workspace(owner: User, name: str) -> Workspace:
    return create_workspace(
        owner=owner,
        name=name,
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )


def api_for(user: User) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def add_resident(client: APIClient, workspace: Workspace, first: str) -> str:
    response = client.post(
        "/api/v1/residents/",
        {"first_name": first, "last_name": "Mensah"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 201
    return str(response.data["id"])


def issue(
    client: APIClient,
    workspace: Workspace,
    resident_id: str,
    *,
    unit: str = "80.0000",
    due: str = "2026-06-07",
) -> Response:
    return client.post(
        "/api/v1/invoices/",
        {
            "resident_id": resident_id,
            "issued_on": "2026-06-01",
            "due_on": due,
            "lines": [
                {
                    "description": "June rent",
                    "quantity": "1",
                    "unit_amount": unit,
                }
            ],
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )


def pay(
    client: APIClient,
    workspace: Workspace,
    resident_id: str,
    amount: str = "100.0000",
) -> Response:
    return client.post(
        "/api/v1/payments/",
        {
            "resident_id": resident_id,
            "amount": amount,
            "paid_on": "2026-06-02",
            "method": "cash",
            "external_reference": "slip-1",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )


@pytest.mark.django_db
def test_invoice_total_is_derived_and_partial_payment_reduces_it() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    created = issue(client, workspace, resident_id)
    assert created.status_code == 201
    assert created.data["reference"] == "INV-0001"
    assert created.data["currency_code"] == "GHS"
    assert created.data["total_amount"] == "80.0000"
    assert created.data["allocated_amount"] == "0.0000"
    assert created.data["outstanding_amount"] == "80.0000"
    assert created.data["lines"][0]["line_total"] == "80.0000"
    assert "balance" not in created.data

    payment = pay(client, workspace, resident_id, "30.0000")
    assert payment.status_code == 201
    assert payment.data["reference"] == "PAY-0001"
    assert payment.data["method"] == "cash"
    assert payment.data["external_reference"] == "slip-1"
    assert payment.data["recorded_by_email"] == "ada@example.com"
    assert payment.data["unallocated_amount"] == "30.0000"

    allocated = client.post(
        "/api/v1/allocations/",
        {
            "payment_id": payment.data["id"],
            "invoice_id": created.data["id"],
            "amount": "30.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert allocated.status_code == 201
    invoice = client.get(
        f"/api/v1/invoices/{created.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert invoice.data["outstanding_amount"] == "50.0000"
    assert invoice.data["allocated_amount"] == "30.0000"
    receipt = client.get(
        f"/api/v1/payments/{payment.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert receipt.data["unallocated_amount"] == "0.0000"
    assert receipt.data["allocations"][0]["invoice_reference"] == "INV-0001"
    assert receipt.data["allocations"][0]["reversed"] is False

    too_much = client.post(
        "/api/v1/allocations/",
        {
            "payment_id": payment.data["id"],
            "invoice_id": created.data["id"],
            "amount": "1.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert too_much.status_code == 400
    assert "unallocated" in detail_text(too_much)


@pytest.mark.django_db
def test_overpayment_stays_unallocated_until_a_refund_record() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    invoice = issue(client, workspace, resident_id, unit="40.0000")
    payment = pay(client, workspace, resident_id, "100.0000")
    allocated = client.post(
        "/api/v1/allocations/",
        {
            "payment_id": payment.data["id"],
            "invoice_id": invoice.data["id"],
            "amount": "40.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert allocated.status_code == 201
    receipt = client.get(
        f"/api/v1/payments/{payment.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert receipt.data["unallocated_amount"] == "60.0000"
    assert receipt.data["allocated_amount"] == "40.0000"
    too_big = client.post(
        f"/api/v1/payments/{payment.data['id']}/refunds/",
        {
            "amount": "60.0001",
            "refunded_on": "2026-06-03",
            "reason": "Returned the extra cash",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert too_big.status_code == 400
    assert Refund.objects.count() == 0
    refunded = client.post(
        f"/api/v1/payments/{payment.data['id']}/refunds/",
        {
            "amount": "60.0000",
            "refunded_on": "2026-06-03",
            "reason": "Returned the extra cash",
            "external_reference": "cash-out-1",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert refunded.status_code == 201
    after = client.get(
        f"/api/v1/payments/{payment.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert after.data["unallocated_amount"] == "0.0000"
    assert after.data["refunded_amount"] == "60.0000"
    assert after.data["refunds"][0]["reason"] == "Returned the extra cash"
    cannot_void = client.post(
        f"/api/v1/payments/{payment.data['id']}/void/",
        {"reason": "Mistake", "voided_on": "2026-06-04"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert cannot_void.status_code == 400
    assert Payment.objects.get(id=payment.data["id"]).status == "recorded"


@pytest.mark.django_db
def test_reversal_and_void_are_explicit_records() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    invoice = issue(client, workspace, resident_id)
    payment = pay(client, workspace, resident_id, "80.0000")
    allocated = client.post(
        "/api/v1/allocations/",
        {
            "payment_id": payment.data["id"],
            "invoice_id": invoice.data["id"],
            "amount": "80.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    blocked = client.post(
        f"/api/v1/invoices/{invoice.data['id']}/void/",
        {"reason": "Wrong amount", "voided_on": "2026-06-04"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert blocked.status_code == 400
    assert Invoice.objects.get(id=invoice.data["id"]).status == "issued"
    reversed_row = client.post(
        f"/api/v1/allocations/{allocated.data['id']}/reverse/",
        {"reason": "Applied to the wrong month", "reversed_on": "2026-06-04"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert reversed_row.status_code == 200
    assert reversed_row.data["reversed"] is True
    again = client.post(
        f"/api/v1/allocations/{allocated.data['id']}/reverse/",
        {"reason": "Again", "reversed_on": "2026-06-04"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert again.status_code == 400
    open_invoice = client.get(
        f"/api/v1/invoices/{invoice.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert open_invoice.data["outstanding_amount"] == "80.0000"
    voided = client.post(
        f"/api/v1/invoices/{invoice.data['id']}/void/",
        {"reason": "Wrong amount", "voided_on": "2026-06-05"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert voided.status_code == 200
    assert voided.data["status"] == "void"
    assert voided.data["void_reason"] == "Wrong amount"
    assert voided.data["outstanding_amount"] == "0.0000"
    assert voided.data["lines"][0]["description"] == "June rent"
    payment_void = client.post(
        f"/api/v1/payments/{payment.data['id']}/void/",
        {"reason": "Cash was not received", "voided_on": "2026-06-05"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert payment_void.status_code == 200
    assert payment_void.data["status"] == "void"
    assert payment_void.data["unallocated_amount"] == "0.0000"
    assert Allocation.objects.filter(id=allocated.data["id"]).exists()


@pytest.mark.django_db
def test_tenancy_fee_can_become_an_invoice() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    property_id = client.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    space_id = client.post(
        "/api/v1/spaces/",
        {
            "property_id": property_id.data["id"],
            "name": "Apartment 1",
            "kind": "unit",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    tenancy = client.post(
        "/api/v1/tenancies/",
        {
            "resident_id": resident_id,
            "space_id": space_id.data["id"],
            "start_date": "2026-06-01",
            "fee_amount": "800.0000",
            "fee_period": "month",
            "deposit_amount": "200.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert tenancy.status_code == 201
    copied = client.post(
        "/api/v1/invoices/",
        {
            "resident_id": resident_id,
            "tenancy_id": tenancy.data["id"],
            "issued_on": "2026-06-01",
            "due_on": "2026-06-07",
            "from_tenancy": True,
            "include_deposit": True,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert copied.status_code == 201
    descriptions = [line["description"] for line in copied.data["lines"]]
    assert descriptions == ["Agreed fee", "Deposit"]
    assert copied.data["total_amount"] == "1000.0000"
    other_space = client.post(
        "/api/v1/spaces/",
        {
            "property_id": property_id.data["id"],
            "name": "Room 9",
            "kind": "room",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    booking = client.post(
        "/api/v1/bookings/",
        {
            "resident_id": resident_id,
            "space_id": other_space.data["id"],
            "start_date": "2026-07-01",
            "end_date": "2026-07-03",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert booking.status_code == 201
    early = client.post(
        "/api/v1/invoices/",
        {
            "resident_id": resident_id,
            "booking_id": booking.data["id"],
            "issued_on": "2026-07-01",
            "due_on": "2026-07-03",
            "from_tenancy": True,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert early.status_code == 400
    assert "Convert the reservation" in detail_text(early)


@pytest.mark.django_db
def test_cross_workspace_payment_cannot_settle_an_invoice() -> None:
    owner = make_user("ada@example.com")
    stranger = make_user("stranger@example.com")
    mine = make_workspace(owner, "Ada House")
    other = make_workspace(stranger, OTHER)
    ada = api_for(owner)
    other_api = api_for(stranger)
    my_resident = add_resident(ada, mine, "Ama")
    their_resident = add_resident(other_api, other, "Private")
    invoice = issue(ada, mine, my_resident)
    their_payment = pay(other_api, other, their_resident, "80.0000")
    stolen = ada.post(
        "/api/v1/allocations/",
        {
            "payment_id": their_payment.data["id"],
            "invoice_id": invoice.data["id"],
            "amount": "80.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert stolen.status_code == 404
    assert OTHER not in rendered(stolen)
    assert "Private" not in rendered(stolen)
    assert Allocation.objects.count() == 0
    foreign_resident = ada.post(
        "/api/v1/invoices/",
        {
            "resident_id": their_resident,
            "issued_on": "2026-06-01",
            "due_on": "2026-06-07",
            "lines": [
                {
                    "description": "Stolen",
                    "quantity": "1",
                    "unit_amount": "10.0000",
                }
            ],
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert foreign_resident.status_code == 404
    assert Invoice.objects.filter(workspace=mine).count() == 1


@pytest.mark.django_db
def test_roles_limit_who_can_read_and_change_money() -> None:
    owner = make_user("ada@example.com")
    finance = make_user("finance@example.com")
    manager = make_user("manager@example.com")
    maintenance = make_user("fix@example.com")
    resident_user = make_user("ama@example.com")
    other_user = make_user("kojo@example.com")
    workspace = make_workspace(owner, "Ada House")
    owner_membership = Membership.objects.get(user=owner)
    add_member(actor=owner_membership, email=finance.email, role="finance")
    add_member(actor=owner_membership, email=manager.email, role="property_manager")
    add_member(actor=owner_membership, email=maintenance.email, role="maintenance")
    add_member(actor=owner_membership, email=resident_user.email, role="resident")
    add_member(actor=owner_membership, email=other_user.email, role="resident")
    owner_api = api_for(owner)
    ama_id = owner_api.post(
        "/api/v1/residents/",
        {
            "first_name": "Ama",
            "last_name": "Mensah",
            "account_email": resident_user.email,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    kojo_id = add_resident(owner_api, workspace, "Kojo")
    invoice = issue(owner_api, workspace, str(ama_id.data["id"]))
    other_invoice = issue(owner_api, workspace, kojo_id, unit="15.0000")
    payment = pay(owner_api, workspace, str(ama_id.data["id"]), "10.0000")

    finance_api = api_for(finance)
    recorded = finance_api.post(
        "/api/v1/payments/",
        {
            "resident_id": str(ama_id.data["id"]),
            "amount": "5.0000",
            "paid_on": "2026-06-03",
            "method": "mobile_money",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert recorded.status_code == 201
    assert recorded.data["method"] == "mobile_money"

    manager_api = api_for(manager)
    visible = manager_api.get(
        "/api/v1/invoices/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert visible.status_code == 200
    assert visible.data["count"] == 2
    denied = manager_api.post(
        "/api/v1/payments/",
        {
            "resident_id": str(ama_id.data["id"]),
            "amount": "5.0000",
            "paid_on": "2026-06-03",
            "method": "bank_transfer",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert denied.status_code == 403
    assert error_code(denied) == "permission_denied"
    assert Payment.objects.filter(method="bank_transfer").count() == 0

    maintenance_api = api_for(maintenance)
    hidden = maintenance_api.get(
        "/api/v1/invoices/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert hidden.status_code == 403
    assert "INV-0001" not in rendered(hidden)
    assert (
        maintenance_api.get(
            "/api/v1/arrears/?on=2026-06-08",
            HTTP_X_WORKSPACE_ID=str(workspace.id),
        ).status_code
        == 403
    )

    resident_api = api_for(resident_user)
    own = resident_api.get(
        "/api/v1/invoices/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert own.status_code == 200
    assert [row["id"] for row in own.data["results"]] == [invoice.data["id"]]
    assert other_invoice.data["reference"] not in rendered(own)
    missing = resident_api.get(
        f"/api/v1/invoices/{other_invoice.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert missing.status_code == 404
    own_payment = resident_api.get(
        f"/api/v1/payments/{payment.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert own_payment.status_code == 200
    assert (
        resident_api.get(
            "/api/v1/arrears/?on=2026-06-08",
            HTTP_X_WORKSPACE_ID=str(workspace.id),
        ).status_code
        == 403
    )
    assert (
        resident_api.post(
            "/api/v1/payments/",
            {
                "resident_id": str(ama_id.data["id"]),
                "amount": "1.0000",
                "paid_on": "2026-06-04",
                "method": "cash",
            },
            format="json",
            HTTP_X_WORKSPACE_ID=str(workspace.id),
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_arrears_lists_only_issued_invoices_that_are_due_and_unpaid() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    due = issue(client, workspace, resident_id, due="2026-06-07")
    future = issue(client, workspace, resident_id, unit="20.0000", due="2026-06-20")
    paid = issue(client, workspace, resident_id, unit="10.0000", due="2026-06-01")
    payment = pay(client, workspace, resident_id, "10.0000")
    assert (
        client.post(
            "/api/v1/allocations/",
            {
                "payment_id": payment.data["id"],
                "invoice_id": paid.data["id"],
                "amount": "10.0000",
            },
            format="json",
            HTTP_X_WORKSPACE_ID=str(workspace.id),
        ).status_code
        == 201
    )
    voided = issue(client, workspace, resident_id, unit="5.0000", due="2026-06-02")
    assert (
        client.post(
            f"/api/v1/invoices/{voided.data['id']}/void/",
            {"reason": "Duplicate", "voided_on": "2026-06-02"},
            format="json",
            HTTP_X_WORKSPACE_ID=str(workspace.id),
        ).status_code
        == 200
    )
    board = client.get(
        "/api/v1/arrears/?on=2026-06-08",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert board.status_code == 200
    references = [row["reference"] for row in board.data["results"]]
    assert references == [due.data["reference"]]
    assert future.data["reference"] not in references
    assert board.data["results"][0]["outstanding_amount"] == "80.0000"
    assert "balance" not in board.data["results"][0]


@pytest.mark.django_db
def test_floats_and_typed_balances_are_rejected() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    floated = client.post(
        "/api/v1/payments/",
        {
            "resident_id": resident_id,
            "amount": 10.5,
            "paid_on": "2026-06-02",
            "method": "other",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert floated.status_code == 400
    assert Payment.objects.count() == 0
    invented = client.post(
        "/api/v1/invoices/",
        {
            "resident_id": resident_id,
            "issued_on": "2026-06-01",
            "due_on": "2026-06-07",
            "total_amount": "1.0000",
            "lines": [
                {
                    "description": "June rent",
                    "quantity": "1",
                    "unit_amount": "10.0000",
                }
            ],
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert invented.status_code == 400
    assert Invoice.objects.count() == 0


@pytest.mark.django_db
def test_money_actions_are_audited_and_history_blocks_deletion() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    invoice = issue(client, workspace, resident_id)
    payment = pay(client, workspace, resident_id, "80.0000")
    allocated = client.post(
        "/api/v1/allocations/",
        {
            "payment_id": payment.data["id"],
            "invoice_id": invoice.data["id"],
            "amount": "20.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert allocated.status_code == 201
    actions = set(
        AuditEvent.objects.filter(workspace=workspace).values_list("action", flat=True)
    )
    assert "invoice.issued" in actions
    assert "payment.recorded" in actions
    assert "allocation.created" in actions
    currency = client.patch(
        f"/api/v1/workspaces/{workspace.id}/",
        {"currency_code": "USD"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert currency.status_code == 400
    workspace.refresh_from_db()
    assert workspace.currency_code == "GHS"
    removed = client.delete(
        f"/api/v1/workspaces/{workspace.id}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert removed.status_code == 400
    assert "billing history" in detail_text(removed)
    assert Workspace.objects.filter(id=workspace.id).exists()
    resident = client.delete(
        f"/api/v1/residents/{resident_id}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert resident.status_code == 400
    assert Resident.objects.filter(id=resident_id).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_allocations_cannot_both_spend_the_outstanding(
    django_db_blocker: Any,
) -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    actor = Membership.objects.get(workspace=workspace, user=owner)
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    invoice = issue(client, workspace, resident_id, unit="80.0000")
    payment = pay(client, workspace, resident_id, "200.0000")
    barrier = threading.Barrier(2)
    results: list[str] = []

    def attempt() -> None:
        barrier.wait(timeout=5)
        with django_db_blocker.unblock():
            connection.close()
            try:
                allocate_payment(
                    actor=actor,
                    data={
                        "payment_id": uuid.UUID(str(payment.data["id"])),
                        "invoice_id": uuid.UUID(str(invoice.data["id"])),
                        "amount": Decimal("80.0000"),
                    },
                )
                results.append("ok")
            except Exception:
                results.append("rejected")
            finally:
                connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert sorted(results) == ["ok", "rejected"]
    assert Allocation.objects.filter(invoice_id=invoice.data["id"]).count() == 1


@pytest.mark.django_db
def test_card_is_manual_and_provider_fields_are_server_owned() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    resident_id = add_resident(client, workspace, "Ama")
    recorded = client.post(
        "/api/v1/payments/",
        {
            "resident_id": resident_id,
            "amount": "12.0000",
            "paid_on": "2026-06-02",
            "method": "card",
            "external_reference": "till-4",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert recorded.status_code == 201
    assert recorded.data["method"] == "card"
    assert recorded.data["provider"] is None
    assert recorded.data["provider_reference"] is None
    assert recorded.data["provider_status"] is None

    for field, value in (
        ("provider", "paystack"),
        ("provider_reference", "psk_123"),
        ("provider_status", "success"),
    ):
        rejected = client.post(
            "/api/v1/payments/",
            {
                "resident_id": resident_id,
                "amount": "12.0000",
                "paid_on": "2026-06-02",
                "method": "card",
                field: value,
            },
            format="json",
            HTTP_X_WORKSPACE_ID=str(workspace.id),
        )
        assert rejected.status_code == 400
        assert "Do not send it." in rendered(rejected)
    assert Payment.objects.filter(workspace=workspace).count() == 1


@pytest.mark.django_db
def test_provider_reference_is_unique_per_workspace() -> None:
    owner = make_user("ada@example.com")
    other_owner = make_user("bea@example.com")
    workspace = make_workspace(owner, "Ada House")
    other = make_workspace(other_owner, "Bea House")
    client = api_for(owner)
    resident = Resident.objects.get(id=add_resident(client, workspace, "Ama"))
    other_resident = Resident.objects.create(
        workspace=other,
        first_name="Kojo",
        last_name="Mensah",
    )

    def store(home: Workspace, person: Resident, reference: str, **extra: str) -> None:
        Payment(
            workspace=home,
            resident=person,
            reference=reference,
            amount=Decimal("10.0000"),
            currency_code="GHS",
            paid_on=date(2026, 6, 2),
            method=Payment.Method.CARD,
            **extra,
        ).save()

    store(workspace, resident, "PAY-9001")
    store(workspace, resident, "PAY-9002")
    store(
        workspace,
        resident,
        "PAY-9003",
        provider="Paystack",
        provider_reference="psk_1",
        provider_status="success",
    )
    saved = Payment.objects.get(reference="PAY-9003")
    assert saved.provider == "paystack"
    assert saved.provider_status == "success"
    store(
        other,
        other_resident,
        "PAY-9003",
        provider="paystack",
        provider_reference="psk_1",
    )
    with pytest.raises(ValidationError, match="pay_provider_reference_unique"):
        store(
            workspace,
            resident,
            "PAY-9004",
            provider="paystack",
            provider_reference="psk_1",
        )
    duplicate = Payment(
        workspace=workspace,
        resident=resident,
        reference="PAY-9004",
        amount=Decimal("10.0000"),
        currency_code="GHS",
        paid_on=date(2026, 6, 2),
        method=Payment.Method.CARD,
        provider="paystack",
        provider_reference="psk_1",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        models.Model.save(duplicate)
    with pytest.raises(ValidationError):
        store(
            workspace,
            resident,
            "PAY-9005",
            provider="paystack",
        )
