"""Plan caps for properties and staff seats."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Plan
from organizations.services import create_workspace
from properties.models import Property


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password="correct-horse-battery")


def api_for(user: User) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_missing_plan_row_does_not_cap_properties() -> None:
    owner = make_user("ada@example.com")
    workspace = create_workspace(
        owner=owner,
        name="Ada House",
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )
    client = api_for(owner)
    created = client.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert created.status_code == 201
    usage = client.get("/api/v1/plan/", HTTP_X_WORKSPACE_ID=str(workspace.id))
    assert usage.status_code == 200
    assert usage.data["property_limit"] is None
    assert usage.data["property_count"] == 1


@pytest.mark.django_db
def test_property_cap_blocks_the_next_create_and_keeps_the_first() -> None:
    owner = make_user("ada@example.com")
    workspace = create_workspace(
        owner=owner,
        name="Ada House",
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )
    Plan.objects.create(plan_code=workspace.plan_code, property_limit=1)
    client = api_for(owner)
    first = client.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/properties/",
        {"name": "Second House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert second.status_code == 400
    assert "allows 1 property" in second.content.decode()
    assert Property.objects.filter(workspace=workspace).count() == 1
    other_owner = make_user("bea@example.com")
    other = create_workspace(
        owner=other_owner,
        name="Bea House",
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )
    other.plan_code = "open"
    other.save(update_fields=["plan_code"])
    other_api = api_for(other_owner)
    opened = other_api.post(
        "/api/v1/properties/",
        {"name": "Bea House Building"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(other.id),
    )
    assert opened.status_code == 201


@pytest.mark.django_db
def test_staff_cap_allows_a_resident_and_blocks_another_staff_seat() -> None:
    owner = make_user("ada@example.com")
    finance = make_user("fin@example.com")
    resident = make_user("res@example.com")
    workspace = create_workspace(
        owner=owner,
        name="Ada House",
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )
    Plan.objects.create(
        plan_code=workspace.plan_code,
        property_limit=None,
        staff_seat_limit=1,
    )
    client = api_for(owner)
    staff = client.post(
        "/api/v1/memberships/",
        {"email": finance.email, "role": "finance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert staff.status_code == 400
    assert "staff seat" in staff.content.decode()
    added = client.post(
        "/api/v1/memberships/",
        {"email": resident.email, "role": "resident"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert added.status_code == 201
    usage = client.get("/api/v1/plan/", HTTP_X_WORKSPACE_ID=str(workspace.id))
    assert usage.data["staff_seat_count"] == 1
    assert usage.data["staff_seat_limit"] == 1
    promoted = client.patch(
        f"/api/v1/memberships/{added.data['id']}/",
        {"role": "finance"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert promoted.status_code == 400
    assert "staff seat" in promoted.content.decode()


@pytest.mark.django_db
def test_blank_limits_mean_unlimited() -> None:
    owner = make_user("ada@example.com")
    workspace = create_workspace(
        owner=owner,
        name="Ada House",
        currency_code="GHS",
        timezone_name="Africa/Accra",
    )
    Plan.objects.create(
        plan_code=workspace.plan_code,
        property_limit=None,
        staff_seat_limit=None,
    )
    client = api_for(owner)
    created = client.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert created.status_code == 201
    usage = client.get("/api/v1/plan/", HTTP_X_WORKSPACE_ID=str(workspace.id))
    assert usage.data["property_limit"] is None
    assert usage.data["staff_seat_limit"] is None
