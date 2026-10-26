"""Properties, rentable spaces, and cross-workspace isolation."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Membership, Workspace
from organizations.services import add_member, create_workspace
from properties.models import Bed, Building, Floor, Property, Space

OTHER_WORKSPACE_NAME = "North Hostel Private"


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


def result_rows(response: Response) -> list[dict[str, Any]]:
    body = response.data
    assert isinstance(body, dict)
    rows = body["results"]
    assert isinstance(rows, list)
    typed: list[dict[str, Any]] = []
    for row in rows:
        assert isinstance(row, dict)
        typed.append(row)
    return typed


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password="correct-horse-battery")


def make_workspace(owner: User, name: str) -> Workspace:
    return create_workspace(
        owner=owner,
        name=name,
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )


def owner_membership(workspace: Workspace, owner: User) -> Membership:
    return Membership.objects.get(workspace=workspace, user=owner)


def names(response: Response) -> list[str]:
    return [str(row["name"]) for row in result_rows(response)]


@pytest.mark.django_db
def test_staff_record_properties_units_rooms_and_optional_groups() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    api = APIClient()
    api.force_login(owner)

    created = api.post(
        "/api/v1/properties/",
        {"name": "Harbour House", "address": "1 Dock Street"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert created.status_code == 201
    property_id = created.data["id"]
    assert created.data["workspace_id"] == str(workspace.id)
    assert created.data["address"] == "1 Dock Street"

    building = api.post(
        "/api/v1/buildings/",
        {"property_id": property_id, "name": "Block A"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert building.status_code == 201
    floor = api.post(
        "/api/v1/floors/",
        {
            "property_id": property_id,
            "building_id": building.data["id"],
            "name": "2",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert floor.status_code == 201

    unit = api.post(
        "/api/v1/spaces/",
        {"property_id": property_id, "name": "Apartment 4", "kind": "unit"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert unit.status_code == 201
    assert unit.data["kind"] == "unit"
    assert unit.data["building_id"] is None
    beds_for_unit = api.get(
        "/api/v1/beds/",
        {"space_id": unit.data["id"]},
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert beds_for_unit.status_code == 200
    assert result_rows(beds_for_unit) == []

    room = api.post(
        "/api/v1/spaces/",
        {
            "property_id": property_id,
            "building_id": building.data["id"],
            "floor_id": floor.data["id"],
            "name": "Room 12",
            "kind": "room",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert room.status_code == 201
    empty_beds = api.get(
        "/api/v1/beds/",
        {"space_id": room.data["id"]},
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert result_rows(empty_beds) == []
    bed = api.post(
        "/api/v1/beds/",
        {"space_id": room.data["id"], "name": "Bed A"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert bed.status_code == 201
    assert bed.data["availability"] == "active"
    assert bed.data["block_reason"] == ""

    listed = api.get(
        "/api/v1/spaces/",
        {"property_id": property_id},
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert names(listed) == ["Apartment 4", "Room 12"]


@pytest.mark.django_db
def test_whole_unit_rejects_beds_until_the_room_is_cleared() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    api = APIClient()
    api.force_login(owner)
    prop = api.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    unit = api.post(
        "/api/v1/spaces/",
        {"property_id": prop.data["id"], "name": "Apartment 4", "kind": "unit"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    rejected = api.post(
        "/api/v1/beds/",
        {"space_id": unit.data["id"], "name": "Bed A"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert rejected.status_code == 400
    assert error_code(rejected) == "validation_error"
    assert Bed.objects.count() == 0

    room = api.post(
        "/api/v1/spaces/",
        {"property_id": prop.data["id"], "name": "Room 12", "kind": "room"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    bed = api.post(
        "/api/v1/beds/",
        {"space_id": room.data["id"], "name": "Bed A"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert bed.status_code == 201
    blocked = api.patch(
        f"/api/v1/spaces/{room.data['id']}/",
        {"kind": "unit"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert blocked.status_code == 400
    assert Space.objects.get(pk=room.data["id"]).kind == "room"
    assert Bed.objects.filter(pk=bed.data["id"]).exists()


@pytest.mark.django_db
def test_maintenance_block_is_unavailable_with_a_reason() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    api = APIClient()
    api.force_login(owner)
    prop = api.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    ).data
    room = api.post(
        "/api/v1/spaces/",
        {"property_id": prop["id"], "name": "Room 12", "kind": "room"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    ).data
    blocked = api.patch(
        f"/api/v1/spaces/{room['id']}/",
        {"availability": "unavailable", "block_reason": "maintenance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert blocked.status_code == 200
    assert blocked.data["availability"] == "unavailable"
    assert blocked.data["block_reason"] == "maintenance"

    generic = api.patch(
        f"/api/v1/spaces/{room['id']}/",
        {"availability": "unavailable", "block_reason": ""},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert generic.status_code == 200
    assert generic.data["block_reason"] == ""

    invalid = api.patch(
        f"/api/v1/spaces/{room['id']}/",
        {"availability": "active", "block_reason": "maintenance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert invalid.status_code == 400
    stored = Space.objects.get(pk=room["id"])
    assert stored.availability == "unavailable"
    assert stored.block_reason == ""

    cleared = api.patch(
        f"/api/v1/spaces/{room['id']}/",
        {"availability": "active"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert cleared.status_code == 200
    assert cleared.data["block_reason"] == ""


@pytest.mark.django_db
def test_residents_cannot_view_or_manage_properties() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    resident = make_user("resident@example.com")
    add_member(
        actor=owner_membership(workspace, owner),
        email=resident.email,
        role=Membership.Role.RESIDENT,
    )
    other = make_workspace(resident, "Resident Owned House")
    prop = Property.objects.create(workspace=workspace, name="Harbour House")
    owned = Property.objects.create(workspace=other, name="Own House")
    api = APIClient()
    api.force_login(resident)

    listing = api.get("/api/v1/properties/", HTTP_X_WORKSPACE_ID=str(workspace.id))
    assert listing.status_code == 403
    assert error_code(listing) == "permission_denied"
    assert "Harbour House" not in rendered(listing)

    created = api.post(
        "/api/v1/properties/",
        {"name": "Sneaky House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert created.status_code == 403
    assert "Sneaky House" not in rendered(created)
    assert not Property.objects.filter(name="Sneaky House").exists()

    detail = api.get(
        f"/api/v1/properties/{prop.id}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert detail.status_code == 403
    assert "Harbour House" not in rendered(detail)

    own = api.get("/api/v1/properties/", HTTP_X_WORKSPACE_ID=str(other.id))
    assert own.status_code == 200
    assert names(own) == ["Own House"]
    assert "Harbour House" not in rendered(own)
    assert owned.name == "Own House"


@pytest.mark.django_db
def test_finance_and_maintenance_can_read_but_not_change() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    finance = make_user("finance@example.com")
    maintenance = make_user("maintenance@example.com")
    actor = owner_membership(workspace, owner)
    add_member(actor=actor, email=finance.email, role=Membership.Role.FINANCE)
    add_member(
        actor=actor,
        email=maintenance.email,
        role=Membership.Role.MAINTENANCE,
    )
    prop = Property.objects.create(workspace=workspace, name="Harbour House")
    room = Space.objects.create(
        workspace=workspace,
        property=prop,
        name="Room 12",
        kind=Space.Kind.ROOM,
    )

    finance_api = APIClient()
    finance_api.force_login(finance)
    listed = finance_api.get(
        "/api/v1/properties/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert listed.status_code == 200
    assert names(listed) == ["Harbour House"]
    rejected = finance_api.post(
        "/api/v1/properties/",
        {"name": "Finance House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert rejected.status_code == 403
    assert Property.objects.filter(name="Finance House").count() == 0

    maintenance_api = APIClient()
    maintenance_api.force_login(maintenance)
    seen = maintenance_api.get(
        f"/api/v1/spaces/{room.id}/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert seen.status_code == 200
    blocked = maintenance_api.patch(
        f"/api/v1/spaces/{room.id}/",
        {"availability": "unavailable", "block_reason": "maintenance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert blocked.status_code == 403
    room.refresh_from_db()
    assert room.availability == "active"
    assert room.block_reason == ""


@pytest.mark.django_db
def test_property_manager_can_manage_properties() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    manager = make_user("manager@example.com")
    add_member(
        actor=owner_membership(workspace, owner),
        email=manager.email,
        role=Membership.Role.PROPERTY_MANAGER,
    )
    api = APIClient()
    api.force_login(manager)
    created = api.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert created.status_code == 201
    renamed = api.patch(
        f"/api/v1/properties/{created.data['id']}/",
        {"name": "Harbour Annex"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert renamed.status_code == 200
    assert renamed.data["name"] == "Harbour Annex"


@pytest.mark.django_db
def test_cross_workspace_property_records_stay_isolated() -> None:
    owner = make_user("ada@example.com")
    mine = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    foreign_property = Property.objects.create(
        workspace=other,
        name="North Wing",
        address="Hidden address",
    )
    foreign_building = Building.objects.create(
        workspace=other,
        property=foreign_property,
        name="North Block",
    )
    foreign_floor = Floor.objects.create(
        workspace=other,
        property=foreign_property,
        building=foreign_building,
        name="North Floor",
    )
    foreign_room = Space.objects.create(
        workspace=other,
        property=foreign_property,
        building=foreign_building,
        floor=foreign_floor,
        name="North Room",
        kind=Space.Kind.ROOM,
    )
    foreign_bed = Bed.objects.create(
        workspace=other,
        space=foreign_room,
        name="North Bed",
    )
    local_property = Property.objects.create(workspace=mine, name="Harbour House")
    local_building = Building.objects.create(
        workspace=mine,
        property=local_property,
        name="Block A",
    )
    other_local = Property.objects.create(workspace=mine, name="Inland House")
    local_room = Space.objects.create(
        workspace=mine,
        property=local_property,
        name="Room 12",
        kind=Space.Kind.ROOM,
    )
    local_bed = Bed.objects.create(
        workspace=mine,
        space=local_room,
        name="Bed A",
    )

    api = APIClient()
    api.force_login(owner)

    listed = api.get(
        "/api/v1/properties/",
        {"workspace_id": str(other.id)},
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert listed.status_code == 200
    assert names(listed) == ["Harbour House", "Inland House"]
    assert OTHER_WORKSPACE_NAME not in rendered(listed)
    assert "North Wing" not in rendered(listed)
    assert "Hidden address" not in rendered(listed)

    retrieved = api.get(
        f"/api/v1/properties/{foreign_property.id}/",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert retrieved.status_code == 404
    assert error_code(retrieved) == "not_found"
    assert "North Wing" not in rendered(retrieved)

    updated = api.patch(
        f"/api/v1/properties/{foreign_property.id}/",
        {"name": "Taken Over"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert updated.status_code == 404
    foreign_property.refresh_from_db()
    assert foreign_property.name == "North Wing"

    deleted = api.delete(
        f"/api/v1/properties/{foreign_property.id}/",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert deleted.status_code == 404
    assert Property.objects.filter(pk=foreign_property.id).exists()

    missing = api.get(
        "/api/v1/properties/not-a-uuid/",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert missing.status_code == 404
    assert missing["Content-Type"].startswith("application/json")

    spaces = api.get(
        "/api/v1/spaces/",
        {"property_id": str(foreign_property.id)},
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert spaces.status_code == 404
    assert "North Room" not in rendered(spaces)

    beds = api.get(
        "/api/v1/beds/",
        {"space_id": str(foreign_room.id)},
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert beds.status_code == 404
    assert "North Bed" not in rendered(beds)

    attached_space = api.post(
        "/api/v1/spaces/",
        {
            "property_id": str(foreign_property.id),
            "name": "Planted Room",
            "kind": "room",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert attached_space.status_code == 404
    assert "North Wing" not in rendered(attached_space)
    assert not Space.objects.filter(name="Planted Room").exists()

    attached_building = api.post(
        "/api/v1/buildings/",
        {"property_id": str(foreign_property.id), "name": "Planted Block"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert attached_building.status_code == 404
    assert not Building.objects.filter(name="Planted Block").exists()

    attached_floor = api.post(
        "/api/v1/floors/",
        {
            "property_id": str(local_property.id),
            "building_id": str(foreign_building.id),
            "name": "Planted Floor",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert attached_floor.status_code == 404
    assert "North Block" not in rendered(attached_floor)
    assert not Floor.objects.filter(name="Planted Floor").exists()

    attached_bed = api.post(
        "/api/v1/beds/",
        {"space_id": str(foreign_room.id), "name": "Planted Bed"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert attached_bed.status_code == 404
    assert not Bed.objects.filter(name="Planted Bed").exists()

    moved = api.patch(
        f"/api/v1/spaces/{local_room.id}/",
        {"property_id": str(foreign_property.id)},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert moved.status_code == 404
    local_room.refresh_from_db()
    assert local_room.property_id == local_property.id

    mismatched = api.post(
        "/api/v1/buildings/",
        {"property_id": str(other_local.id), "name": "Block B"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert mismatched.status_code == 201
    wrong_parent = api.post(
        "/api/v1/spaces/",
        {
            "property_id": str(local_property.id),
            "building_id": mismatched.data["id"],
            "name": "Wrong Block Room",
            "kind": "room",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert wrong_parent.status_code == 400
    assert error_code(wrong_parent) == "validation_error"
    assert "Inland House" not in rendered(wrong_parent)
    assert not Space.objects.filter(name="Wrong Block Room").exists()

    removed = api.delete(
        f"/api/v1/properties/{local_property.id}/",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert removed.status_code == 204
    assert not Space.objects.filter(pk=local_room.id).exists()
    assert not Bed.objects.filter(pk=local_bed.id).exists()
    assert not Building.objects.filter(pk=local_building.id).exists()
    assert Property.objects.filter(pk=foreign_property.id).exists()
    assert Bed.objects.filter(pk=foreign_bed.id).exists()
    assert Property.objects.filter(pk=other_local.id).exists()


@pytest.mark.django_db
def test_several_memberships_require_a_workspace_header() -> None:
    owner = make_user("ada@example.com")
    first = make_workspace(owner, "Ada House")
    second = make_workspace(owner, "Second House")
    Property.objects.create(workspace=first, name="Harbour House")
    api = APIClient()
    api.force_login(owner)
    missing = api.get("/api/v1/properties/")
    assert missing.status_code == 400
    assert error_code(missing) == "workspace_required"
    chosen = api.get("/api/v1/properties/", HTTP_X_WORKSPACE_ID=str(second.id))
    assert chosen.status_code == 200
    assert result_rows(chosen) == []
    assert "Harbour House" not in rendered(chosen)


@pytest.mark.django_db
def test_client_cannot_choose_ids_or_another_workspace() -> None:
    owner = make_user("ada@example.com")
    mine = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    api = APIClient()
    api.force_login(owner)
    chosen = uuid.uuid4()
    rejected = api.post(
        "/api/v1/properties/",
        {"id": str(chosen), "name": "Harbour House", "workspace_id": str(other.id)},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert rejected.status_code == 400
    assert not Property.objects.filter(pk=chosen).exists()
    assert not Property.objects.filter(name="Harbour House").exists()
    assert OTHER_WORKSPACE_NAME not in rendered(rejected)

    created = api.post(
        "/api/v1/properties/",
        {"name": "Harbour House", "workspace_id": str(mine.id)},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert created.status_code == 201
    assert created.data["id"] != str(chosen)
    assert created.data["workspace_id"] == str(mine.id)


@pytest.mark.django_db
def test_names_are_unique_per_workspace_ignoring_case() -> None:
    owner = make_user("ada@example.com")
    mine = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    api = APIClient()
    api.force_login(owner)
    first = api.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert first.status_code == 201
    duplicate = api.post(
        "/api/v1/properties/",
        {"name": " harbour house "},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert duplicate.status_code == 400
    assert Property.objects.filter(workspace=mine).count() == 1
    Property.objects.create(workspace=other, name="Harbour House")
    assert Property.objects.filter(name="Harbour House").count() == 2


@pytest.mark.django_db
def test_suspended_workspace_rejects_property_calls() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    Property.objects.create(workspace=workspace, name="Harbour House")
    workspace.status = Workspace.Status.SUSPENDED
    workspace.save()
    api = APIClient()
    api.force_login(owner)
    response = api.get("/api/v1/properties/", HTTP_X_WORKSPACE_ID=str(workspace.id))
    assert response.status_code == 403
    assert error_code(response) == "workspace_unavailable"
    assert "Harbour House" not in rendered(response)
