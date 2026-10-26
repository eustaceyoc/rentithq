"""Residents, bookings, tenancies, and inclusive occupancy."""

from __future__ import annotations

import threading
import uuid
from datetime import date
from typing import Any

import pytest
from django.db import IntegrityError, connection
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.test import APIClient

from accounts.models import User
from bookings.models import Booking
from bookings.services import create_booking
from organizations.models import AuditEvent, Membership, Workspace
from organizations.services import add_member, create_workspace
from properties.models import Property, Space
from residents.models import Resident
from tenancies.models import Assignment, OccupancyBlock, Tenancy

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
    for key in ("detail", "end_date", "space_id", "bed_id", "non_field_errors"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            return str(value[0])
    return rendered(response)


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
    client: APIClient,
    workspace: Workspace,
    property_id: str,
    name: str,
    kind: str,
) -> str:
    response = client.post(
        "/api/v1/spaces/",
        {"property_id": property_id, "name": name, "kind": kind},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 201
    return str(response.data["id"])


def add_bed(
    client: APIClient,
    workspace: Workspace,
    space_id: str,
    name: str,
) -> str:
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
    first_name: str,
    *,
    account_email: str = "",
) -> str:
    response = client.post(
        "/api/v1/residents/",
        {
            "first_name": first_name,
            "last_name": "Mensah",
            "phone": "0244000000",
            "email": "",
            "account_email": account_email,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 201, response.content
    return str(response.data["id"])


def book(
    client: APIClient,
    workspace: Workspace,
    resident_id: str,
    space_id: str,
    start: str,
    end: str | None,
    bed_id: str | None = None,
) -> Response:
    body: dict[str, Any] = {
        "resident_id": resident_id,
        "space_id": space_id,
        "start_date": start,
        "end_date": end,
    }
    if bed_id is not None:
        body["bed_id"] = bed_id
    return client.post(
        "/api/v1/bookings/",
        body,
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )


@pytest.mark.django_db
def test_booking_tenancy_and_stay_keep_inclusive_history() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    unit_id = add_space(client, workspace, property_id, "Apartment 4", "unit")
    room_id = add_space(client, workspace, property_id, "Room 12", "room")
    bed_a = add_bed(client, workspace, room_id, "Bed A")
    bed_b = add_bed(client, workspace, room_id, "Bed B")
    resident_id = add_resident(client, workspace, "Ama")

    one_night = book(
        client, workspace, resident_id, unit_id, "2026-01-01", "2026-01-01"
    )
    assert one_night.status_code == 201
    assert one_night.data["end_date"] == "2026-01-01"
    next_day = book(client, workspace, resident_id, unit_id, "2026-01-02", "2026-01-02")
    assert next_day.status_code == 201
    overlap = book(client, workspace, resident_id, unit_id, "2026-01-02", "2026-01-03")
    assert overlap.status_code == 400
    assert detail_text(overlap) == "Those dates overlap another stay."
    assert "Ama" not in detail_text(overlap)

    open_ended = book(
        client, workspace, resident_id, room_id, "2026-02-01", None, bed_a
    )
    assert open_ended.status_code == 201
    later = book(
        client, workspace, resident_id, room_id, "2026-03-01", "2026-03-02", bed_a
    )
    assert later.status_code == 400
    released = client.post(
        f"/api/v1/bookings/{open_ended.data['id']}/cancel/",
        {},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert released.status_code == 200
    other_bed = book(
        client,
        workspace,
        resident_id,
        room_id,
        "2026-02-01",
        "2026-02-02",
        bed_b,
    )
    assert other_bed.status_code == 201

    whole_room = book(
        client, workspace, resident_id, room_id, "2026-04-01", "2026-04-04"
    )
    assert whole_room.status_code == 201
    bed_during_room = book(
        client, workspace, resident_id, room_id, "2026-04-04", "2026-04-04", bed_a
    )
    assert bed_during_room.status_code == 400
    cancelled = client.post(
        f"/api/v1/bookings/{whole_room.data['id']}/cancel/",
        {},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert cancelled.status_code == 200
    assert cancelled.data["status"] == "cancelled"
    assert Assignment.objects.filter(
        booking_id=whole_room.data["id"],
        status="cancelled",
    ).exists()
    assert Assignment.objects.filter(
        booking_id=open_ended.data["id"],
        status="cancelled",
    ).exists()
    freed = book(
        client, workspace, resident_id, room_id, "2026-04-04", "2026-04-04", bed_a
    )
    assert freed.status_code == 201

    room_hold = book(
        client, workspace, resident_id, room_id, "2026-05-01", "2026-05-10"
    )
    assert room_hold.status_code == 201
    bed_c = add_bed(client, workspace, room_id, "Bed C")
    inherited = book(
        client, workspace, resident_id, room_id, "2026-05-02", "2026-05-02", bed_c
    )
    assert inherited.status_code == 400

    converted = client.post(
        f"/api/v1/bookings/{freed.data['id']}/convert/",
        {
            "fee_amount": "350.0000",
            "fee_period": "month",
            "deposit_amount": "100.0000",
            "check_in": True,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert converted.status_code == 201
    assert converted.data["currency_code"] == "GHS"
    assert converted.data["fee_amount"] == "350.0000"
    assert converted.data["deposit_amount"] == "100.0000"
    stay = Assignment.objects.get(booking_id=freed.data["id"], status="active")
    checked_out = client.post(
        f"/api/v1/assignments/{stay.id}/check-out/",
        {"end_date": "2026-04-04"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert checked_out.status_code == 200
    assert checked_out.data["status"] == "checked_out"
    assert Assignment.objects.filter(id=stay.id).exists()

    moving = book(
        client, workspace, resident_id, room_id, "2026-06-01", "2026-06-10", bed_b
    )
    assert moving.status_code == 201
    moving_stay = Assignment.objects.get(booking_id=moving.data["id"])
    checked_in = client.post(
        f"/api/v1/assignments/{moving_stay.id}/check-in/",
        {},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert checked_in.status_code == 200
    transferred = client.post(
        f"/api/v1/assignments/{moving_stay.id}/transfer/",
        {"space_id": room_id, "bed_id": bed_a, "start_date": "2026-06-05"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert transferred.status_code == 201
    assert transferred.data["status"] == "active"
    assert transferred.data["start_date"] == "2026-06-05"
    old = Assignment.objects.get(id=moving_stay.id)
    assert old.status == "transferred"
    assert str(old.end_date) == "2026-06-04"
    back = book(
        client, workspace, resident_id, room_id, "2026-06-05", "2026-06-05", bed_b
    )
    assert back.status_code == 201
    still_there = book(
        client, workspace, resident_id, room_id, "2026-06-04", "2026-06-04", bed_b
    )
    assert still_there.status_code == 201
    taken = book(
        client, workspace, resident_id, room_id, "2026-06-05", "2026-06-05", bed_a
    )
    assert taken.status_code == 400

    ended = client.post(
        f"/api/v1/tenancies/{converted.data['id']}/end/",
        {"ended_on": "2026-04-04"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert ended.status_code == 200
    assert ended.data["status"] == "ended"
    assert Tenancy.objects.get(id=converted.data["id"]).status == "ended"


@pytest.mark.django_db
def test_maintenance_blocks_new_stays_and_check_in() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    room_id = add_space(client, workspace, property_id, "Room 3", "room")
    bed_id = add_bed(client, workspace, room_id, "Bed A")
    resident_id = add_resident(client, workspace, "Kojo")
    blocked = client.patch(
        f"/api/v1/spaces/{room_id}/",
        {"availability": "unavailable", "block_reason": "maintenance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert blocked.status_code == 200
    refused = book(client, workspace, resident_id, room_id, "2026-07-01", "2026-07-02")
    assert refused.status_code == 400
    assert detail_text(refused) == "This space is unavailable for maintenance."

    client.patch(
        f"/api/v1/spaces/{room_id}/",
        {"availability": "active", "block_reason": ""},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    client.patch(
        f"/api/v1/beds/{bed_id}/",
        {"availability": "unavailable", "block_reason": "maintenance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    bed_refused = book(
        client, workspace, resident_id, room_id, "2026-07-01", "2026-07-02", bed_id
    )
    assert bed_refused.status_code == 400
    assert "unavailable for maintenance" in detail_text(bed_refused)

    client.patch(
        f"/api/v1/beds/{bed_id}/",
        {"availability": "active", "block_reason": ""},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    created = book(
        client, workspace, resident_id, room_id, "2026-08-01", "2026-08-03", bed_id
    )
    assert created.status_code == 201
    client.patch(
        f"/api/v1/beds/{bed_id}/",
        {"availability": "unavailable", "block_reason": "maintenance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    stay = Assignment.objects.get(booking_id=created.data["id"])
    check_in = client.post(
        f"/api/v1/assignments/{stay.id}/check-in/",
        {},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert check_in.status_code == 400
    stay.refresh_from_db()
    assert stay.status == "confirmed"


@pytest.mark.django_db
def test_room_and_bed_conflict_in_both_directions() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    room_id = add_space(client, workspace, property_id, "Room 12", "room")
    bed_id = add_bed(client, workspace, room_id, "Bed A")
    resident_id = add_resident(client, workspace, "Ama")
    bed_stay = book(
        client, workspace, resident_id, room_id, "2026-09-01", "2026-09-03", bed_id
    )
    assert bed_stay.status_code == 201
    whole = book(client, workspace, resident_id, room_id, "2026-09-03", "2026-09-04")
    assert whole.status_code == 400
    unit_id = add_space(client, workspace, property_id, "Apartment 4", "unit")
    with_bed = book(
        client, workspace, resident_id, unit_id, "2026-09-01", "2026-09-01", bed_id
    )
    assert with_bed.status_code == 400
    assert "whole unit" in detail_text(with_bed).lower()


@pytest.mark.django_db
def test_exclusion_constraint_rejects_a_direct_overlapping_hold() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    room_id = add_space(client, workspace, property_id, "Room 12", "room")
    bed_id = add_bed(client, workspace, room_id, "Bed A")
    resident_id = add_resident(client, workspace, "Ama")
    created = book(
        client, workspace, resident_id, room_id, "2026-01-01", "2026-01-02", bed_id
    )
    assert created.status_code == 201
    stay = Assignment.objects.get(booking_id=created.data["id"])
    hold = OccupancyBlock.objects.get(assignment=stay, bed_id=bed_id)
    with pytest.raises(IntegrityError):
        OccupancyBlock.objects.create(
            assignment=stay,
            workspace=workspace,
            space_id=room_id,
            bed_id=bed_id,
            period=hold.period,
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_bookings_cannot_both_take_the_same_bed(
    django_db_blocker: Any,
) -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    actor = Membership.objects.get(workspace=workspace, user=owner)
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    room_id = add_space(client, workspace, property_id, "Room 12", "room")
    bed_id = add_bed(client, workspace, room_id, "Bed A")
    resident_id = add_resident(client, workspace, "Ama")
    resident = Resident.objects.get(id=resident_id)
    barrier = threading.Barrier(2)
    results: list[str] = []

    def attempt() -> None:
        barrier.wait(timeout=5)
        with django_db_blocker.unblock():
            connection.close()
            try:
                create_booking(
                    actor=actor,
                    data={
                        "resident_id": resident.id,
                        "space_id": uuid.UUID(room_id),
                        "bed_id": uuid.UUID(bed_id),
                        "start_date": date(2026, 10, 1),
                        "end_date": date(2026, 10, 3),
                    },
                )
                results.append("ok")
            except ValidationError:
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
    assert Booking.objects.filter(status="confirmed").count() == 1
    assert Assignment.objects.filter(status="confirmed").count() == 1


@pytest.mark.django_db
def test_resident_sees_only_their_profile_and_tenancy() -> None:
    owner = make_user("ada@example.com")
    resident_user = make_user("ama@example.com")
    other_user = make_user("kojo@example.com")
    workspace = make_workspace(owner, "Ada House")
    owner_api = api_for(owner)
    owner_membership = Membership.objects.get(user=owner)
    add_member(actor=owner_membership, email=resident_user.email, role="resident")
    add_member(actor=owner_membership, email=other_user.email, role="resident")
    property_id = add_property(owner_api, workspace, "Harbour House")
    unit_id = add_space(owner_api, workspace, property_id, "Apartment 4", "unit")
    ama_id = add_resident(
        owner_api, workspace, "Ama", account_email=resident_user.email
    )
    kojo_id = add_resident(owner_api, workspace, "Kojo", account_email=other_user.email)
    tenancy = owner_api.post(
        "/api/v1/tenancies/",
        {
            "resident_id": ama_id,
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
            "fee_amount": "1200.0000",
            "fee_period": "month",
            "deposit_amount": "0.0000",
            "space_id": unit_id,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert tenancy.status_code == 201

    resident_api = api_for(resident_user)
    own = resident_api.get("/api/v1/residents/", HTTP_X_WORKSPACE_ID=str(workspace.id))
    assert own.status_code == 200
    names = [row["first_name"] for row in result_rows(own)]
    assert names == ["Ama"]
    assert "Kojo" not in rendered(own)
    hidden = resident_api.get(
        f"/api/v1/residents/{kojo_id}/", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert hidden.status_code == 404
    assert "Kojo" not in rendered(hidden)
    stays = resident_api.get(
        "/api/v1/tenancies/", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert [row["id"] for row in result_rows(stays)] == [tenancy.data["id"]]
    other_stay = owner_api.post(
        "/api/v1/tenancies/",
        {
            "resident_id": kojo_id,
            "start_date": "2026-02-01",
            "fee_amount": "80.0000",
            "fee_period": "night",
            "space_id": unit_id,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert other_stay.status_code == 400
    visible = resident_api.get(
        "/api/v1/assignments/", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert len(result_rows(visible)) == 1
    assert result_rows(visible)[0]["resident_name"] == "Ama Mensah"
    denied = resident_api.post(
        "/api/v1/bookings/",
        {
            "resident_id": ama_id,
            "space_id": unit_id,
            "start_date": "2027-01-01",
            "end_date": "2027-01-02",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert denied.status_code == 403
    assert error_code(denied) == "permission_denied"
    properties = resident_api.get(
        "/api/v1/properties/", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert properties.status_code == 403
    assert "Harbour House" not in rendered(properties)
    board = resident_api.get(
        "/api/v1/availability/?on=2026-01-02", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert board.status_code == 403


@pytest.mark.django_db
def test_cross_workspace_ids_do_not_attach() -> None:
    owner = make_user("ada@example.com")
    stranger = make_user("stranger@example.com")
    mine = make_workspace(owner, "Ada House")
    other = make_workspace(stranger, OTHER)
    ada = api_for(owner)
    other_api = api_for(stranger)
    my_property = add_property(ada, mine, "Harbour House")
    my_space = add_space(ada, mine, my_property, "Apartment 4", "unit")
    my_resident = add_resident(ada, mine, "Ama")
    their_property = add_property(other_api, other, "Private Annex")
    their_space = add_space(other_api, other, their_property, "Room 9", "room")
    their_resident = add_resident(other_api, other, "Private")

    stolen_space = book(ada, mine, my_resident, their_space, "2026-01-01", "2026-01-05")
    assert stolen_space.status_code == 404
    assert OTHER not in rendered(stolen_space)
    assert "Private Annex" not in rendered(stolen_space)
    assert Booking.objects.filter(workspace=mine).count() == 0

    stolen_resident = book(
        ada, mine, their_resident, my_space, "2026-01-01", "2026-01-05"
    )
    assert stolen_resident.status_code == 404
    assert "Private" not in rendered(stolen_resident)
    assert Booking.objects.count() == 0

    stolen_tenancy = ada.post(
        "/api/v1/tenancies/",
        {
            "resident_id": my_resident,
            "start_date": "2026-03-01",
            "fee_amount": "10.0000",
            "fee_period": "week",
            "space_id": their_space,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert stolen_tenancy.status_code == 404
    assert Tenancy.objects.count() == 0

    chosen = uuid.uuid4()
    injected = ada.post(
        "/api/v1/residents/",
        {
            "id": str(chosen),
            "workspace_id": str(other.id),
            "first_name": "Injected",
            "last_name": "Person",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert injected.status_code == 400
    assert not Resident.objects.filter(first_name="Injected").exists()
    assert OTHER not in rendered(injected)


@pytest.mark.django_db
def test_finance_can_read_occupancy_and_cannot_change_it() -> None:
    owner = make_user("ada@example.com")
    finance = make_user("finance@example.com")
    workspace = make_workspace(owner, "Ada House")
    add_member(
        actor=Membership.objects.get(user=owner),
        email=finance.email,
        role="finance",
    )
    owner_api = api_for(owner)
    property_id = add_property(owner_api, workspace, "Harbour House")
    unit_id = add_space(owner_api, workspace, property_id, "Apartment 4", "unit")
    resident_id = add_resident(owner_api, workspace, "Ama")
    created = book(
        owner_api, workspace, resident_id, unit_id, "2026-01-01", "2026-01-08"
    )
    assert created.status_code == 201
    finance_api = api_for(finance)
    listed = finance_api.get("/api/v1/bookings/", HTTP_X_WORKSPACE_ID=str(workspace.id))
    assert listed.status_code == 200
    assert len(result_rows(listed)) == 1
    board = finance_api.get(
        "/api/v1/availability/?on=2026-01-01", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert board.status_code == 200
    states = {row["space_name"]: row["state"] for row in result_rows(board)}
    assert states["Apartment 4"] == "occupied"
    refused = finance_api.post(
        "/api/v1/residents/",
        {"first_name": "Eve", "last_name": "Mensah"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert refused.status_code == 403
    assert not Resident.objects.filter(first_name="Eve").exists()


@pytest.mark.django_db
def test_property_delete_keeps_occupancy_history() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    unit_id = add_space(client, workspace, property_id, "Apartment 4", "unit")
    resident_id = add_resident(client, workspace, "Ama")
    created = book(client, workspace, resident_id, unit_id, "2026-01-01", "2026-01-02")
    assert created.status_code == 201
    removed = client.delete(
        f"/api/v1/properties/{property_id}/", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert removed.status_code == 400
    assert "occupancy history" in detail_text(removed)
    assert Property.objects.filter(id=property_id).exists()
    assert Space.objects.filter(id=unit_id).exists()
    assert Assignment.objects.count() == 1


@pytest.mark.django_db
def test_money_rejects_floats_and_availability_marks_a_partial_room() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    client = api_for(owner)
    property_id = add_property(client, workspace, "Harbour House")
    room_id = add_space(client, workspace, property_id, "Room 12", "room")
    bed_id = add_bed(client, workspace, room_id, "Bed A")
    resident_id = add_resident(client, workspace, "Ama")
    floated = client.post(
        "/api/v1/tenancies/",
        {
            "resident_id": resident_id,
            "start_date": "2026-01-01",
            "fee_amount": 10.5,
            "fee_period": "night",
            "space_id": room_id,
            "bed_id": bed_id,
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert floated.status_code == 400
    assert Tenancy.objects.count() == 0
    created = book(
        client, workspace, resident_id, room_id, "2026-01-10", "2026-01-12", bed_id
    )
    assert created.status_code == 201
    board = client.get(
        "/api/v1/availability/?on=2026-01-11", HTTP_X_WORKSPACE_ID=str(workspace.id)
    )
    assert board.status_code == 200
    rows = result_rows(board)
    room = next(row for row in rows if row["bed_id"] is None)
    bed = next(row for row in rows if row["bed_id"] == bed_id)
    assert room["state"] == "partly_occupied"
    assert bed["state"] == "occupied"
    assert bed["resident_name"] == "Ama Mensah"


@pytest.mark.django_db
def test_resident_can_change_only_their_own_phone_and_email() -> None:
    owner = make_user("ada@example.com")
    resident_user = make_user("ama@example.com")
    other_user = make_user("kojo@example.com")
    workspace = make_workspace(owner, "Ada House")
    owner_api = api_for(owner)
    owner_membership = Membership.objects.get(user=owner)
    add_member(actor=owner_membership, email=resident_user.email, role="resident")
    add_member(actor=owner_membership, email=other_user.email, role="resident")
    ama_id = add_resident(
        owner_api,
        workspace,
        "Ama",
        account_email=resident_user.email,
    )
    kojo_id = add_resident(
        owner_api,
        workspace,
        "Kojo",
        account_email=other_user.email,
    )
    resident_api = api_for(resident_user)

    updated = resident_api.patch(
        f"/api/v1/residents/{ama_id}/",
        {"phone": "0201111111", "email": "Ama@Example.com"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert updated.status_code == 200
    assert updated.data["phone"] == "0201111111"
    assert updated.data["email"] == "ama@example.com"
    assert updated.data["first_name"] == "Ama"
    actions = list(
        AuditEvent.objects.filter(target_id=ama_id).values_list("action", flat=True)
    )
    assert sorted(actions) == [
        "resident.email_updated",
        "resident.phone_updated",
    ]

    same = resident_api.patch(
        f"/api/v1/residents/{ama_id}/",
        {"phone": "0201111111"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert same.status_code == 200
    assert AuditEvent.objects.filter(target_id=ama_id).count() == 2

    for field, value in (
        ("first_name", "New"),
        ("last_name", "Name"),
        ("account_email", resident_user.email),
    ):
        rejected = resident_api.patch(
            f"/api/v1/residents/{ama_id}/",
            {field: value, "phone": "0202222222"},
            format="json",
            HTTP_X_WORKSPACE_ID=str(workspace.id),
        )
        assert rejected.status_code == 400
        assert "phone and email" in rendered(rejected)
    ama = Resident.objects.get(id=ama_id)
    assert ama.first_name == "Ama"
    assert ama.last_name == "Mensah"
    assert ama.phone == "0201111111"
    assert AuditEvent.objects.filter(target_id=ama_id).count() == 2

    stolen = resident_api.patch(
        f"/api/v1/residents/{kojo_id}/",
        {"phone": "0203333333"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert stolen.status_code == 404
    assert "Kojo" not in rendered(stolen)
    assert Resident.objects.get(id=kojo_id).phone == "0244000000"
    assert AuditEvent.objects.filter(target_id=kojo_id).count() == 0
