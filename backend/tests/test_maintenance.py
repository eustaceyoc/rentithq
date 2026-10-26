"""Maintenance requests, status history, and workspace scope."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from accounts.models import User
from maintenance.models import MaintenanceRequest, MaintenanceUpdate
from organizations.models import AuditEvent, Membership, Workspace
from organizations.services import add_member, create_workspace
from properties.models import Space

OTHER = "North Hostel Private"


def rendered(response: Response) -> str:
    text = response.content.decode()
    assert isinstance(text, str)
    return text


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


def add_property(client: APIClient, workspace: Workspace, name: str) -> str:
    response = client.post(
        "/api/v1/properties/",
        {"name": name, "address": "1 Dock Street"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 201
    return str(response.data["id"])


def add_space(
    client: APIClient, workspace: Workspace, property_id: str, name: str
) -> str:
    response = client.post(
        "/api/v1/spaces/",
        {"property_id": property_id, "name": name, "kind": "room"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 201
    return str(response.data["id"])


def add_bed(client: APIClient, workspace: Workspace, space_id: str, name: str) -> str:
    response = client.post(
        "/api/v1/beds/",
        {"space_id": space_id, "name": name},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 201
    return str(response.data["id"])


def add_resident(
    client: APIClient,
    workspace: Workspace,
    first: str,
    *,
    account_email: str = "",
) -> str:
    response = client.post(
        "/api/v1/residents/",
        {
            "first_name": first,
            "last_name": "Mensah",
            "account_email": account_email,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 201, response.content
    return str(response.data["id"])


def file_request(
    client: APIClient,
    workspace: Workspace,
    property_id: str,
    *,
    description: str = "The tap drips.",
    space_id: str | None = None,
    bed_id: str | None = None,
    resident_id: str | None = None,
    assignee_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Response:
    body: dict[str, Any] = {
        "property_id": property_id,
        "description": description,
        "priority": "high",
    }
    if space_id is not None:
        body["space_id"] = space_id
    if bed_id is not None:
        body["bed_id"] = bed_id
    if resident_id is not None:
        body["resident_id"] = resident_id
    if assignee_id is not None:
        body["assignee_id"] = assignee_id
    if extra:
        body.update(extra)
    return client.post(
        "/api/v1/maintenance-requests/",
        body,
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )


@pytest.mark.django_db
def test_owner_files_assigns_and_keeps_status_history() -> None:
    owner = make_user("ada@example.com")
    worker = make_user("kwa@example.com")
    workspace = make_workspace(owner, "Ada House")
    owner_membership = Membership.objects.get(user=owner)
    add_member(actor=owner_membership, email=worker.email, role="maintenance")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    space_id = add_space(client, workspace, property_id, "Room 2")
    bed_id = add_bed(client, workspace, space_id, "Bed A")
    resident_id = add_resident(client, workspace, "Ama")

    created = file_request(
        client,
        workspace,
        property_id,
        space_id=space_id,
        bed_id=bed_id,
        resident_id=resident_id,
    )
    assert created.status_code == 201, created.content
    assert created.data["reference"] == "MNT-0001"
    assert created.data["status"] == "open"
    assert created.data["assignee_id"] is None
    assert created.data["location_blocked"] is False
    assert created.data["cost_amount"] is None
    assert created.data["updates"][0]["status_before"] == ""
    assert created.data["updates"][0]["status_after"] == "open"
    assert Space.objects.get(id=space_id).availability == "active"

    assigned = client.patch(
        f"/api/v1/maintenance-requests/{created.data['id']}/",
        {"assignee_id": str(worker.id), "note": "Kwa will take this."},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert assigned.status_code == 200
    assert assigned.data["status"] == "assigned"
    assert assigned.data["assignee_email"] == worker.email
    assert len(assigned.data["updates"]) == 2

    started = api_for(worker).patch(
        f"/api/v1/maintenance-requests/{created.data['id']}/",
        {"status": "in_progress"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert started.status_code == 200
    finished = api_for(worker).patch(
        f"/api/v1/maintenance-requests/{created.data['id']}/",
        {
            "status": "completed",
            "completion_note": "Washer replaced.",
            "cost_amount": "25.5000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert finished.status_code == 200
    assert finished.data["status"] == "completed"
    assert finished.data["cost_amount"] == "25.5000"
    assert finished.data["currency_code"] == "GHS"
    assert [row["status_after"] for row in finished.data["updates"]] == [
        "open",
        "assigned",
        "in_progress",
        "completed",
    ]
    actions = set(
        AuditEvent.objects.filter(target_id=created.data["id"]).values_list(
            "action",
            flat=True,
        )
    )
    assert actions == {
        "maintenance.created",
        "maintenance.assigned",
        "maintenance.status_changed",
        "maintenance.cost_recorded",
    }
    assert MaintenanceUpdate.objects.filter(request_id=created.data["id"]).count() == 4
    assert Space.objects.get(id=space_id).availability == "active"


@pytest.mark.django_db
def test_maintenance_staff_see_only_their_queue() -> None:
    owner = make_user("ada@example.com")
    worker = make_user("kwa@example.com")
    other = make_user("yaw@example.com")
    workspace = make_workspace(owner, "Ada House")
    owner_membership = Membership.objects.get(user=owner)
    add_member(actor=owner_membership, email=worker.email, role="maintenance")
    add_member(actor=owner_membership, email=other.email, role="maintenance")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    own = file_request(client, workspace, property_id, description="Owner queue.")
    assert own.status_code == 201
    filed = file_request(
        api_for(worker),
        workspace,
        property_id,
        description="Filed by Kwa.",
    )
    assert filed.status_code == 201

    hidden = api_for(worker).get(
        "/api/v1/maintenance-requests/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert hidden.status_code == 200
    assert hidden.data["count"] == 1
    assert hidden.data["results"][0]["description"] == "Filed by Kwa."
    stolen = api_for(worker).get(
        f"/api/v1/maintenance-requests/{own.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert stolen.status_code == 404
    assert "Owner queue" not in rendered(stolen)

    reassigned = client.patch(
        f"/api/v1/maintenance-requests/{own.data['id']}/",
        {"assignee_id": str(other.id)},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert reassigned.status_code == 200
    yaw = api_for(other)
    visible = yaw.get(
        "/api/v1/maintenance-requests/", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert visible.data["count"] == 1
    assert visible.data["results"][0]["id"] == own.data["id"]
    refused = yaw.patch(
        f"/api/v1/maintenance-requests/{own.data['id']}/",
        {"assignee_id": str(worker.id)},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert refused.status_code == 400
    assert "status, note" in rendered(refused)
    assert MaintenanceRequest.objects.get(id=own.data["id"]).assignee_id == other.id


@pytest.mark.django_db
def test_resident_can_file_and_view_only_their_request() -> None:
    owner = make_user("ada@example.com")
    ama = make_user("ama@example.com")
    kojo = make_user("kojo@example.com")
    workspace = make_workspace(owner, "Ada House")
    owner_membership = Membership.objects.get(user=owner)
    add_member(actor=owner_membership, email=ama.email, role="resident")
    add_member(actor=owner_membership, email=kojo.email, role="resident")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    space_id = add_space(client, workspace, property_id, "Room 2")
    ama_id = add_resident(client, workspace, "Ama", account_email=ama.email)
    kojo_id = add_resident(client, workspace, "Kojo", account_email=kojo.email)
    stay = client.post(
        "/api/v1/bookings/",
        {
            "resident_id": ama_id,
            "space_id": space_id,
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert stay.status_code == 201

    filed = api_for(ama).post(
        "/api/v1/maintenance-requests/",
        {
            "space_id": space_id,
            "description": "Light switch sticks.",
            "priority": "normal",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert filed.status_code == 201
    assert filed.data["resident_id"] == ama_id
    assert filed.data["property_id"] == property_id
    assert filed.data["space_id"] == space_id

    on_behalf = file_request(
        client,
        workspace,
        property_id,
        description="Filed for Kojo.",
        resident_id=kojo_id,
    )
    assert on_behalf.status_code == 201

    listing = api_for(ama).get(
        "/api/v1/maintenance-requests/", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert listing.status_code == 200
    assert listing.data["count"] == 1
    assert "Kojo" not in rendered(listing)

    other = api_for(ama).patch(
        f"/api/v1/maintenance-requests/{on_behalf.data['id']}/",
        {"note": "Not mine."},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert other.status_code == 404
    assert "Kojo" not in rendered(other)

    controls = api_for(ama).patch(
        f"/api/v1/maintenance-requests/{filed.data['id']}/",
        {"status": "completed", "completion_note": "Done.", "cost_amount": "1.0000"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert controls.status_code == 403
    stored = MaintenanceRequest.objects.get(id=filed.data["id"])
    assert stored.status == "open"
    assert stored.cost_amount is None

    stranger_space = api_for(kojo).post(
        "/api/v1/maintenance-requests/",
        {
            "space_id": space_id,
            "description": "I do not stay here.",
            "priority": "low",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert stranger_space.status_code == 404
    assert (
        MaintenanceRequest.objects.filter(description="I do not stay here.").count()
        == 0
    )

    elsewhere = api_for(ama).post(
        "/api/v1/maintenance-requests/",
        {"resident_id": kojo_id, "description": "Wrong person.", "priority": "low"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert elsewhere.status_code == 404
    assert "Kojo" not in rendered(elsewhere)


@pytest.mark.django_db
def test_request_cannot_cross_workspaces_or_skip_status() -> None:
    owner = make_user("ada@example.com")
    other_owner = make_user("bea@example.com")
    finance = make_user("finance@example.com")
    workspace = make_workspace(owner, "Ada House")
    other = make_workspace(other_owner, OTHER)
    owner_membership = Membership.objects.get(user=owner)
    add_member(actor=owner_membership, email=finance.email, role="finance")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    space_id = add_space(client, workspace, property_id, "Room 2")
    other_property = add_property(api_for(other_owner), other, "Other House")
    created = file_request(client, workspace, property_id, space_id=space_id)
    assert created.status_code == 201

    crossed = file_request(client, workspace, other_property, description="Crossed.")
    assert crossed.status_code == 404
    assert "Other House" not in rendered(crossed)
    assert MaintenanceRequest.objects.filter(workspace=workspace).count() == 1

    foreign = api_for(other_owner).get(
        f"/api/v1/maintenance-requests/{created.data['id']}/",
        HTTP_X_WORKSPACE_ID=str(other.id),
    )
    assert foreign.status_code == 404
    assert "tap drips" not in rendered(foreign).lower()

    skipped = client.patch(
        f"/api/v1/maintenance-requests/{created.data['id']}/",
        {"status": "completed", "completion_note": "Too soon."},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert skipped.status_code == 400
    assert MaintenanceRequest.objects.get(id=created.data["id"]).status == "open"

    bare = client.patch(
        f"/api/v1/maintenance-requests/{created.data['id']}/",
        {"status": "completed"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert bare.status_code == 400

    photo = file_request(
        client,
        workspace,
        property_id,
        extra={"photo": "leak.jpg"},
    )
    assert photo.status_code == 400
    assert "not available" in rendered(photo).lower()

    floated = client.patch(
        f"/api/v1/maintenance-requests/{created.data['id']}/",
        {"cost_amount": 12.5},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert floated.status_code == 400
    assert MaintenanceRequest.objects.get(id=created.data["id"]).cost_amount is None

    finance_api = api_for(finance)
    filed = file_request(
        finance_api,
        workspace,
        property_id,
        description="Finance noticed a leak.",
    )
    assert filed.status_code == 201
    blocked = finance_api.patch(
        f"/api/v1/maintenance-requests/{filed.data['id']}/",
        {"status": "cancelled"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert blocked.status_code == 403
    assert MaintenanceRequest.objects.get(id=filed.data["id"]).status == "open"

    blocked_space = client.patch(
        f"/api/v1/spaces/{space_id}/",
        {"availability": "unavailable", "block_reason": "maintenance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert blocked_space.status_code == 200
    linked = file_request(client, workspace, property_id, space_id=space_id)
    assert linked.status_code == 201
    assert linked.data["location_blocked"] is True
    assert Space.objects.get(id=space_id).block_reason == "maintenance"
