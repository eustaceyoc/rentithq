"""Workspace reports do not leak another workspace's totals."""

from __future__ import annotations

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Membership, Workspace
from organizations.services import add_member, create_workspace

OTHER = "North Hostel Private"


def rendered(response: Response) -> str:
    text = response.content.decode()
    assert isinstance(text, str)
    return text


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password="correct-horse-battery")


def make_workspace(owner: User, name: str, currency: str = "GHS") -> Workspace:
    return create_workspace(
        owner=owner,
        name=name,
        currency_code=currency,
        timezone_name="Africa/Accra",
    )


def api_for(user: User) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def seed(
    owner: User,
    name: str,
    *,
    currency: str = "GHS",
    charge: str = "80.0000",
    paid: str = "30.0000",
) -> tuple[APIClient, Workspace, str]:
    workspace = make_workspace(owner, name, currency)
    client = api_for(owner)
    property_response = client.post(
        "/api/v1/properties/",
        {"name": f"{name} Block", "address": "1 Dock Street"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert property_response.status_code == 201
    property_id = str(property_response.data["id"])
    space = client.post(
        "/api/v1/spaces/",
        {"property_id": property_id, "name": "Room 1", "kind": "room"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert space.status_code == 201
    resident = client.post(
        "/api/v1/residents/",
        {"first_name": name.split()[0], "last_name": "Mensah"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert resident.status_code == 201
    booking = client.post(
        "/api/v1/bookings/",
        {
            "resident_id": resident.data["id"],
            "space_id": space.data["id"],
            "start_date": "2026-06-01",
            "end_date": "2026-06-20",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert booking.status_code == 201
    invoice = client.post(
        "/api/v1/invoices/",
        {
            "resident_id": resident.data["id"],
            "issued_on": "2026-06-01",
            "due_on": "2026-06-07",
            "lines": [{"description": "June", "quantity": "1", "unit_amount": charge}],
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert invoice.status_code == 201
    payment = client.post(
        "/api/v1/payments/",
        {
            "resident_id": resident.data["id"],
            "amount": paid,
            "paid_on": "2026-06-02",
            "method": "cash",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert payment.status_code == 201
    request = client.post(
        "/api/v1/maintenance-requests/",
        {
            "property_id": property_id,
            "description": f"Leak at {name}",
            "priority": "urgent",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert request.status_code == 201
    return client, workspace, property_id


@pytest.mark.django_db
def test_reports_are_scoped_and_export_the_same_rows() -> None:
    ada = make_user("ada@example.com")
    bea = make_user("bea@example.com")
    ada_api, ada_house, _ada_property = seed(ada, "Ada House")
    _bea_api, bea_house, _bea_property = seed(
        bea,
        OTHER,
        currency="NGN",
        charge="15.0000",
        paid="5.0000",
    )

    occupancy = ada_api.get(
        "/api/v1/reports/occupancy/?on=2026-06-10",
        HTTP_X_WORKSPACE_ID=str(ada_house.id),
    )
    assert occupancy.status_code == 200
    assert occupancy.data["spaces"]["room"]["occupied"] == 1
    names = [row["property_name"] for row in occupancy.data["properties"]]
    assert names == ["Ada House Block"]
    assert OTHER not in rendered(occupancy)
    assert occupancy.data["upcoming_count"] == 1
    assert occupancy.data["upcoming_move_outs"][0]["end_date"] == "2026-06-20"

    arrears = ada_api.get(
        "/api/v1/reports/arrears/?on=2026-06-08",
        HTTP_X_WORKSPACE_ID=str(ada_house.id),
    )
    assert arrears.status_code == 200
    assert arrears.data["invoice_count"] == 1
    assert arrears.data["outstanding_amount"] == "80.0000"
    assert arrears.data["currency_code"] == "GHS"
    assert "NGN" not in rendered(arrears)

    collected = ada_api.get(
        "/api/v1/reports/collections/?from=2026-06-01&to=2026-06-30",
        HTTP_X_WORKSPACE_ID=str(ada_house.id),
    )
    assert collected.status_code == 200
    assert collected.data["payment_count"] == 1
    assert collected.data["collected_amount"] == "30.0000"
    assert collected.data["by_method"] == [
        {"method": "cash", "count": 1, "amount": "30.0000"}
    ]
    assert collected.data["net_amount"] == "30.0000"

    maintenance = ada_api.get(
        "/api/v1/reports/maintenance/", HTTP_X_WORKSPACE_ID=str(ada_house.id)
    )
    assert maintenance.status_code == 200
    assert maintenance.data["scope"] == "workspace"
    assert maintenance.data["counts"]["open"] == 1
    assert maintenance.data["open_count"] == 1
    assert "Leak at North" not in rendered(maintenance)

    exported = ada_api.get(
        "/api/v1/reports/occupancy/?on=2026-06-10&export=csv",
        HTTP_X_WORKSPACE_ID=str(ada_house.id),
    )
    assert exported.status_code == 200
    assert "text/csv" in exported["Content-Type"]
    body = exported.content.decode()
    assert "Ada House Block" in body
    assert OTHER not in body
    assert "NGN" not in body

    bea_arrears = api_for(bea).get(
        "/api/v1/reports/arrears/?on=2026-06-08&export=csv",
        HTTP_X_WORKSPACE_ID=str(bea_house.id),
    )
    assert "80.0000" not in bea_arrears.content.decode()
    assert "Ada House" not in bea_arrears.content.decode()


@pytest.mark.django_db
def test_report_roles_do_not_leak_counts() -> None:
    owner = make_user("ada@example.com")
    resident = make_user("ama@example.com")
    worker = make_user("kwa@example.com")
    finance = make_user("finance@example.com")
    client, house, _property_id = seed(owner, "Ada House")
    membership = Membership.objects.get(user=owner, workspace=house)
    add_member(actor=membership, email=resident.email, role="resident")
    add_member(actor=membership, email=worker.email, role="maintenance")
    add_member(actor=membership, email=finance.email, role="finance")

    secret = "Ada House Block"
    for role_user in (resident, worker):
        denied = api_for(role_user).get(
            "/api/v1/reports/arrears/?on=2026-06-08",
            HTTP_X_WORKSPACE_ID=str(house.id),
        )
        assert denied.status_code == 403
        assert "80.0000" not in rendered(denied)
        assert secret not in rendered(denied)
        denied_csv = api_for(role_user).get(
            "/api/v1/reports/collections/?from=2026-06-01&to=2026-06-30&export=csv",
            HTTP_X_WORKSPACE_ID=str(house.id),
        )
        assert denied_csv.status_code == 403
        assert b"30.0000" not in denied_csv.content

    resident_board = api_for(resident).get(
        "/api/v1/reports/occupancy/?on=2026-06-10",
        HTTP_X_WORKSPACE_ID=str(house.id),
    )
    assert resident_board.status_code == 403
    assert secret not in rendered(resident_board)

    worker_board = api_for(worker).get(
        "/api/v1/reports/maintenance/",
        HTTP_X_WORKSPACE_ID=str(house.id),
    )
    assert worker_board.status_code == 200
    assert worker_board.data["scope"] == "assigned"
    assert worker_board.data["open_count"] == 0
    assert "Leak at Ada" not in rendered(worker_board)

    finance_board = api_for(finance).get(
        "/api/v1/reports/maintenance/?export=csv",
        HTTP_X_WORKSPACE_ID=str(house.id),
    )
    assert finance_board.status_code == 200
    assert "open,1" in finance_board.content.decode().replace(" ", "")

    assert (
        client.get(
            "/api/v1/reports/collections/?from=2026-06-30&to=2026-06-01",
            HTTP_X_WORKSPACE_ID=str(house.id),
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_csv_escapes_formula_text() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    created = client.post(
        "/api/v1/properties/",
        {"name": "=1+1", "address": "1 Dock Street"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert created.status_code == 201
    exported = client.get(
        "/api/v1/reports/occupancy/?on=2026-06-10&export=csv",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert exported.status_code == 200
    assert "'=1+1" in exported.content.decode()
