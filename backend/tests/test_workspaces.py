"""Auth, workspace membership, and cross-workspace isolation."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from rest_framework.response import Response
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import AuditEvent, Membership, Workspace
from organizations.services import add_member, create_workspace

PASSWORD = "correct-horse-battery"
OTHER_WORKSPACE_NAME = "North Hostel Private"
OTHER_RESIDENT_EMAIL = "north-resident@example.com"


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


def make_user(email: str, *, first_name: str = "Ada") -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        first_name=first_name,
    )


def make_workspace(owner: User, name: str, *, currency: str = "GHS") -> Workspace:
    return create_workspace(
        owner=owner,
        name=name,
        currency_code=currency,
        timezone_name="Africa/Accra",
    )


def owner_membership(workspace: Workspace, owner: User) -> Membership:
    return Membership.objects.get(workspace=workspace, user=owner)


@pytest.mark.django_db
def test_register_does_not_grant_platform_access() -> None:
    api = APIClient()
    secret = "nonspecific-secret-value"
    response = api.post(
        "/api/v1/auth/register/",
        {
            "email": "New.Owner@Example.com",
            "password": secret,
            "first_name": "New",
            "last_name": "Owner",
            "is_staff": True,
            "is_superuser": True,
        },
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(email="new.owner@example.com")
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.check_password(secret)
    text = rendered(response)
    assert secret not in text
    assert "is_staff" not in text
    assert "is_superuser" not in text
    assert api.get("/api/v1/auth/session/").status_code == 200


@pytest.mark.django_db
def test_duplicate_register_hides_the_password() -> None:
    make_user("ada@example.com")
    api = APIClient()
    secret = "nonspecific-secret-value"
    response = api.post(
        "/api/v1/auth/register/",
        {"email": "Ada@Example.com", "password": secret},
        format="json",
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"
    assert secret not in rendered(response)
    assert User.objects.filter(email="ada@example.com").count() == 1


@pytest.mark.django_db
def test_login_failure_does_not_reveal_which_part_was_wrong() -> None:
    user = make_user("ada@example.com")
    api = APIClient()
    unknown = api.post(
        "/api/v1/auth/login/",
        {"email": "missing@example.com", "password": PASSWORD},
        format="json",
    )
    wrong = api.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "not-the-password"},
        format="json",
    )
    assert unknown.status_code == 400
    assert unknown.data == wrong.data
    assert PASSWORD not in rendered(unknown)
    assert "not-the-password" not in rendered(wrong)


@pytest.mark.django_db
def test_login_requires_csrf_when_the_browser_enforces_it() -> None:
    make_user("ada@example.com")
    client = Client(enforce_csrf_checks=True)
    payload = json.dumps({"email": "ada@example.com", "password": PASSWORD})
    rejected = client.post(
        "/api/v1/auth/login/",
        data=payload,
        content_type="application/json",
    )
    assert rejected.status_code == 403
    assert PASSWORD not in rejected.content.decode()

    csrf = client.get("/api/v1/auth/csrf/")
    assert csrf.status_code == 200
    token = csrf.json()["csrfToken"]
    assert isinstance(token, str)
    accepted = client.post(
        "/api/v1/auth/login/",
        data=payload,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert accepted.status_code == 200
    session = client.get("/api/v1/auth/session/")
    assert session.status_code == 200
    assert session.json()["user"]["email"] == "ada@example.com"


@pytest.mark.django_db
def test_login_rotates_the_csrf_token_used_for_the_next_write() -> None:
    client = Client(enforce_csrf_checks=True)
    issued = client.get("/api/v1/auth/csrf/")
    original = issued.json()["csrfToken"]
    assert isinstance(original, str)
    registered = client.post(
        "/api/v1/auth/register/",
        data=json.dumps(
            {
                "email": "ada@example.com",
                "password": PASSWORD,
            }
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=original,
    )
    assert registered.status_code == 201
    rotated = client.cookies["csrftoken"].value
    assert rotated != original
    stale = client.post(
        "/api/v1/workspaces/",
        data=json.dumps({"name": "Ada House", "currency_code": "GHS"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=original,
    )
    assert stale.status_code == 403
    assert Workspace.objects.count() == 0
    created = client.post(
        "/api/v1/workspaces/",
        data=json.dumps({"name": "Ada House", "currency_code": "GHS"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=rotated,
    )
    assert created.status_code == 201
    assert Workspace.objects.filter(name="Ada House").count() == 1


@pytest.mark.django_db
def test_logout_ends_the_session() -> None:
    user = make_user("ada@example.com")
    api = APIClient()
    api.force_login(user)
    assert api.get("/api/v1/auth/session/").status_code == 200
    assert api.post("/api/v1/auth/logout/").status_code == 204
    logged_out = api.get("/api/v1/auth/session/")
    assert logged_out.status_code == 403
    assert error_code(logged_out) == "not_authenticated"


@pytest.mark.django_db
def test_session_and_workspace_list_hide_other_tenants() -> None:
    owner = make_user("ada@example.com")
    mine = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    add_member(
        actor=owner_membership(other, stranger),
        email=make_user(OTHER_RESIDENT_EMAIL).email,
        role=Membership.Role.RESIDENT,
    )

    api = APIClient()
    api.force_login(owner)
    session = api.get("/api/v1/auth/session/")
    assert session.status_code == 200
    text = rendered(session)
    assert OTHER_WORKSPACE_NAME not in text
    assert OTHER_RESIDENT_EMAIL not in text
    assert "is_staff" not in text
    body = session.data
    assert isinstance(body, dict)
    memberships = body["memberships"]
    assert isinstance(memberships, list)
    assert len(memberships) == 1

    listed = api.get("/api/v1/workspaces/")
    assert listed.status_code == 200
    rows = result_rows(listed)
    assert [row["id"] for row in rows] == [str(mine.id)]
    assert OTHER_WORKSPACE_NAME not in rendered(listed)
    assert str(other.id) not in rendered(listed)


@pytest.mark.django_db
def test_member_cannot_read_update_or_delete_another_workspace() -> None:
    owner = make_user("ada@example.com")
    mine = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    api = APIClient()
    api.force_login(owner)

    retrieved = api.get(f"/api/v1/workspaces/{other.id}/")
    assert retrieved.status_code == 404
    assert error_code(retrieved) == "not_found"
    assert OTHER_WORKSPACE_NAME not in rendered(retrieved)

    updated = api.patch(
        f"/api/v1/workspaces/{other.id}/",
        {"name": "Taken Over"},
        format="json",
    )
    assert updated.status_code == 404
    assert OTHER_WORKSPACE_NAME not in rendered(updated)
    other.refresh_from_db()
    assert other.name == OTHER_WORKSPACE_NAME

    deleted = api.delete(f"/api/v1/workspaces/{other.id}/")
    assert deleted.status_code == 404
    assert Workspace.objects.filter(pk=other.id).exists()
    assert (
        AuditEvent.objects.filter(
            action=AuditEvent.Action.WORKSPACE_DELETED,
            target_id=other.id,
        ).count()
        == 0
    )

    missing = api.get("/api/v1/workspaces/not-a-uuid/")
    assert missing.status_code == 404
    assert missing["Content-Type"].startswith("application/json")
    assert error_code(missing) == "not_found"

    own = api.patch(
        f"/api/v1/workspaces/{mine.id}/",
        {"name": "Ada House Renamed"},
        format="json",
    )
    assert own.status_code == 200
    other.refresh_from_db()
    assert other.name == OTHER_WORKSPACE_NAME


@pytest.mark.django_db
def test_header_selects_among_memberships_and_does_not_grant_access() -> None:
    owner = make_user("ada@example.com")
    first = make_workspace(owner, "First House")
    second = make_workspace(owner, "Second House", currency="USD")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    foreign_member = make_user(OTHER_RESIDENT_EMAIL)
    add_member(
        actor=owner_membership(other, stranger),
        email=foreign_member.email,
        role=Membership.Role.RESIDENT,
    )
    api = APIClient()
    api.force_login(owner)

    missing_header = api.get("/api/v1/memberships/")
    assert missing_header.status_code == 400
    assert error_code(missing_header) == "workspace_required"
    assert OTHER_WORKSPACE_NAME not in rendered(missing_header)

    foreign_header = api.get(
        "/api/v1/memberships/",
        HTTP_X_WORKSPACE_ID=str(other.id),
    )
    assert foreign_header.status_code == 404
    assert error_code(foreign_header) == "not_found"
    assert OTHER_WORKSPACE_NAME not in rendered(foreign_header)
    assert OTHER_RESIDENT_EMAIL not in rendered(foreign_header)

    garbage_header = api.get(
        "/api/v1/memberships/",
        HTTP_X_WORKSPACE_ID="not-a-workspace",
    )
    assert garbage_header.status_code == 404
    assert OTHER_WORKSPACE_NAME not in rendered(garbage_header)

    queried = api.get(
        f"/api/v1/memberships/?workspace_id={other.id}",
        HTTP_X_WORKSPACE_ID=str(first.id),
    )
    assert queried.status_code == 200
    queried_text = rendered(queried)
    assert OTHER_RESIDENT_EMAIL not in queried_text
    assert str(other.id) not in queried_text
    assert result_rows(queried)[0]["workspace_id"] == str(first.id)

    second_rows = result_rows(
        api.get("/api/v1/memberships/", HTTP_X_WORKSPACE_ID=str(second.id))
    )
    assert second_rows[0]["workspace_id"] == str(second.id)
    assert second.id != first.id


@pytest.mark.django_db
def test_single_membership_can_omit_the_header() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Only House")
    api = APIClient()
    api.force_login(owner)
    response = api.get("/api/v1/memberships/")
    assert response.status_code == 200
    assert result_rows(response)[0]["workspace_id"] == str(workspace.id)


@pytest.mark.django_db
def test_member_cannot_attach_another_workspaces_ids() -> None:
    owner = make_user("ada@example.com")
    mine = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    foreign_membership = add_member(
        actor=owner_membership(other, stranger),
        email=make_user(OTHER_RESIDENT_EMAIL).email,
        role=Membership.Role.PROPERTY_MANAGER,
    )
    recruit = make_user("recruit@example.com")
    api = APIClient()
    api.force_login(owner)
    before = Membership.objects.filter(workspace=other).count()

    attached = api.post(
        "/api/v1/memberships/",
        {
            "email": recruit.email,
            "role": Membership.Role.RESIDENT,
            "workspace_id": str(other.id),
            "id": str(foreign_membership.id),
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert attached.status_code == 400
    assert error_code(attached) == "validation_error"
    assert Membership.objects.filter(workspace=other).count() == before
    assert not Membership.objects.filter(workspace=other, user=recruit).exists()
    foreign_membership.refresh_from_db()
    assert foreign_membership.role == Membership.Role.PROPERTY_MANAGER
    assert foreign_membership.workspace_id == other.id
    assert OTHER_WORKSPACE_NAME not in rendered(attached)

    own_membership = owner_membership(mine, owner)
    moved = api.patch(
        f"/api/v1/memberships/{own_membership.id}/",
        {"role": Membership.Role.OWNER, "workspace_id": str(other.id)},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert moved.status_code == 400
    own_membership.refresh_from_db()
    assert own_membership.workspace_id == mine.id
    assert Membership.objects.filter(workspace=other).count() == before

    stolen = api.patch(
        f"/api/v1/memberships/{foreign_membership.id}/",
        {"role": Membership.Role.OWNER},
        format="json",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert stolen.status_code == 404
    assert OTHER_RESIDENT_EMAIL not in rendered(stolen)
    foreign_membership.refresh_from_db()
    assert foreign_membership.role == Membership.Role.PROPERTY_MANAGER

    removed = api.delete(
        f"/api/v1/memberships/{foreign_membership.id}/",
        HTTP_X_WORKSPACE_ID=str(mine.id),
    )
    assert removed.status_code == 404
    foreign_membership.refresh_from_db()
    assert foreign_membership.is_active is True


@pytest.mark.django_db
def test_resident_cannot_manage_the_workspace_or_see_other_members() -> None:
    owner = make_user("ada@example.com", first_name="Ada")
    workspace = make_workspace(owner, "Ada House")
    resident = make_user("resident@example.com", first_name="Bea")
    resident_membership = add_member(
        actor=owner_membership(workspace, owner),
        email=resident.email,
        role=Membership.Role.RESIDENT,
    )
    assert resident.is_staff is False
    api = APIClient()
    api.force_login(resident)

    listed = api.get("/api/v1/memberships/")
    assert listed.status_code == 200
    rows = result_rows(listed)
    assert [row["id"] for row in rows] == [str(resident_membership.id)]
    assert "ada@example.com" not in rendered(listed)

    staff_row = owner_membership(workspace, owner)
    hidden = api.get(f"/api/v1/memberships/{staff_row.id}/")
    assert hidden.status_code == 404
    assert "ada@example.com" not in rendered(hidden)

    promoted = api.patch(
        f"/api/v1/memberships/{resident_membership.id}/",
        {"role": Membership.Role.OWNER},
        format="json",
    )
    assert promoted.status_code == 403
    assert error_code(promoted) == "permission_denied"
    resident_membership.refresh_from_db()
    assert resident_membership.role == Membership.Role.RESIDENT

    created = api.post(
        "/api/v1/memberships/",
        {"email": "extra@example.com", "role": Membership.Role.FINANCE},
        format="json",
    )
    assert created.status_code == 403
    assert not User.objects.filter(email="extra@example.com").exists()

    renamed = api.patch(
        f"/api/v1/workspaces/{workspace.id}/",
        {"name": "Resident takeover"},
        format="json",
    )
    assert renamed.status_code == 403
    workspace.refresh_from_db()
    assert workspace.name == "Ada House"

    deleted = api.delete(f"/api/v1/workspaces/{workspace.id}/")
    assert deleted.status_code == 403
    assert Workspace.objects.filter(pk=workspace.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role",
    [
        Membership.Role.PROPERTY_MANAGER,
        Membership.Role.FINANCE,
        Membership.Role.MAINTENANCE,
    ],
)
def test_staff_roles_can_read_members_but_not_change_the_workspace(role: str) -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    staff = make_user(f"{role}@example.com")
    add_member(
        actor=owner_membership(workspace, owner),
        email=staff.email,
        role=role,
    )
    api = APIClient()
    api.force_login(staff)
    listed = api.get("/api/v1/memberships/")
    assert listed.status_code == 200
    assert len(result_rows(listed)) == 2

    denied = api.post(
        "/api/v1/memberships/",
        {"email": "extra@example.com", "role": Membership.Role.RESIDENT},
        format="json",
    )
    assert denied.status_code == 403
    renamed = api.patch(
        f"/api/v1/workspaces/{workspace.id}/",
        {"name": "Staff takeover", "status": "suspended"},
        format="json",
    )
    assert renamed.status_code == 403
    workspace.refresh_from_db()
    assert workspace.name == "Ada House"
    assert workspace.status == Workspace.Status.ACTIVE
    assert api.delete(f"/api/v1/workspaces/{workspace.id}/").status_code == 403
    assert Workspace.objects.filter(pk=workspace.id).exists()


@pytest.mark.django_db
def test_a_resident_can_own_a_different_workspace() -> None:
    owner = make_user("ada@example.com")
    shared = make_workspace(owner, "Ada House")
    resident = make_user("resident@example.com")
    add_member(
        actor=owner_membership(shared, owner),
        email=resident.email,
        role=Membership.Role.RESIDENT,
    )
    api = APIClient()
    api.force_login(resident)
    created = api.post(
        "/api/v1/workspaces/",
        {"name": "Bea House", "currency_code": "NGN", "timezone": "Africa/Lagos"},
        format="json",
    )
    assert created.status_code == 201
    owned = Workspace.objects.get(name="Bea House")
    assert Membership.objects.get(workspace=owned, user=resident).role == (
        Membership.Role.OWNER
    )
    still_blocked = api.patch(
        f"/api/v1/workspaces/{shared.id}/",
        {"name": "Nope"},
        format="json",
    )
    assert still_blocked.status_code == 403
    shared.refresh_from_db()
    assert shared.name == "Ada House"


@pytest.mark.django_db
def test_owner_can_add_and_remove_members_but_not_the_last_owner() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    manager = make_user("manager@example.com")
    api = APIClient()
    api.force_login(owner)
    created = api.post(
        "/api/v1/memberships/",
        {"email": "Manager@Example.com", "role": Membership.Role.PROPERTY_MANAGER},
        format="json",
    )
    assert created.status_code == 201
    body = created.data
    assert isinstance(body, dict)
    assert body["role"] == Membership.Role.PROPERTY_MANAGER
    assert body["user"]["email"] == manager.email
    membership = Membership.objects.get(workspace=workspace, user=manager)

    owner_row = owner_membership(workspace, owner)
    demoted = api.patch(
        f"/api/v1/memberships/{owner_row.id}/",
        {"role": Membership.Role.FINANCE},
        format="json",
    )
    assert demoted.status_code == 400
    owner_row.refresh_from_db()
    assert owner_row.role == Membership.Role.OWNER

    removed_owner = api.delete(f"/api/v1/memberships/{owner_row.id}/")
    assert removed_owner.status_code == 400
    owner_row.refresh_from_db()
    assert owner_row.is_active is True

    removed = api.delete(f"/api/v1/memberships/{membership.id}/")
    assert removed.status_code == 204
    membership.refresh_from_db()
    assert membership.is_active is False
    listed = rendered(api.get("/api/v1/memberships/"))
    assert manager.email not in listed

    restored = api.post(
        "/api/v1/memberships/",
        {"email": manager.email, "role": Membership.Role.OWNER},
        format="json",
    )
    assert restored.status_code == 201
    membership.refresh_from_db()
    assert membership.is_active is True
    assert membership.role == Membership.Role.OWNER

    stepped_down = api.patch(
        f"/api/v1/memberships/{owner_row.id}/",
        {"role": Membership.Role.FINANCE},
        format="json",
    )
    assert stepped_down.status_code == 200
    owner_row.refresh_from_db()
    assert owner_row.role == Membership.Role.FINANCE


@pytest.mark.django_db
def test_suspended_workspace_is_closed_for_members_and_hidden_from_others() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    make_workspace(stranger, "Other House")
    workspace.status = Workspace.Status.SUSPENDED
    workspace.save()

    owner_api = APIClient()
    owner_api.force_login(owner)
    detail = owner_api.get(f"/api/v1/workspaces/{workspace.id}/")
    assert detail.status_code == 200
    assert detail.data["status"] == Workspace.Status.SUSPENDED
    blocked = owner_api.get("/api/v1/memberships/")
    assert blocked.status_code == 403
    assert error_code(blocked) == "workspace_unavailable"
    unchanged = owner_api.patch(
        f"/api/v1/workspaces/{workspace.id}/",
        {"name": "Reopened"},
        format="json",
    )
    assert unchanged.status_code == 403
    workspace.refresh_from_db()
    assert workspace.name == "Ada House"

    stranger_api = APIClient()
    stranger_api.force_login(stranger)
    hidden = stranger_api.get(
        "/api/v1/memberships/",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert hidden.status_code == 404
    assert error_code(hidden) == "not_found"
    assert "Ada House" not in rendered(hidden)


@pytest.mark.django_db
def test_invalid_workspace_settings_are_rejected() -> None:
    owner = make_user("ada@example.com")
    api = APIClient()
    api.force_login(owner)
    currency = api.post(
        "/api/v1/workspaces/",
        {"name": "Ada House", "currency_code": "ghs", "timezone": "Africa/Accra"},
        format="json",
    )
    assert currency.status_code == 400
    zone = api.post(
        "/api/v1/workspaces/",
        {"name": "Ada House", "currency_code": "GHS", "timezone": "Not/AZone"},
        format="json",
    )
    assert zone.status_code == 400
    assert Workspace.objects.count() == 0
    created = api.post(
        "/api/v1/workspaces/",
        {"name": "Ada House", "currency_code": "GHS"},
        format="json",
    )
    assert created.status_code == 201
    assert created.data["timezone"] == "UTC"
    assert created.data["currency_code"] == "GHS"
    assert created.data["plan_code"] == "placeholder"
    rejected = api.patch(
        f"/api/v1/workspaces/{created.data['id']}/",
        {"plan_code": "starter"},
        format="json",
    )
    assert rejected.status_code == 400
    assert Workspace.objects.get(pk=created.data["id"]).plan_code == "placeholder"


@pytest.mark.django_db
def test_owner_delete_removes_only_that_workspace() -> None:
    owner = make_user("ada@example.com")
    mine = make_workspace(owner, "Ada House")
    stranger = make_user("stranger@example.com")
    other = make_workspace(stranger, OTHER_WORKSPACE_NAME)
    api = APIClient()
    api.force_login(owner)
    deleted = api.delete(f"/api/v1/workspaces/{mine.id}/")
    assert deleted.status_code == 204
    assert not Workspace.objects.filter(pk=mine.id).exists()
    assert not Membership.objects.filter(workspace=mine).exists()
    assert Workspace.objects.filter(pk=other.id).exists()
    assert AuditEvent.objects.filter(
        action=AuditEvent.Action.WORKSPACE_DELETED,
        target_id=mine.id,
        workspace__isnull=True,
    ).exists()


@pytest.mark.django_db
def test_platform_admin_is_superuser_only() -> None:
    owner = make_user("ada@example.com")
    staff = User.objects.create_user(
        email="staff@example.com",
        password=PASSWORD,
        is_staff=True,
        is_superuser=False,
    )
    root = User.objects.create_superuser(
        email="root@example.com",
        password=PASSWORD,
    )
    client = Client()
    client.force_login(owner)
    assert client.get("/admin/").status_code == 302
    client.force_login(staff)
    assert client.get("/admin/").status_code == 302
    client.force_login(root)
    assert client.get("/admin/").status_code == 200


@pytest.mark.django_db
def test_anonymous_workspace_routes_require_a_session() -> None:
    response = APIClient().get("/api/v1/workspaces/")
    assert response.status_code == 403
    assert error_code(response) == "not_authenticated"
    assert "password" not in rendered(response).lower()
