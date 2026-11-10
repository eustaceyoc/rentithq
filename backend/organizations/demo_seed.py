"""Sample DEMO workspace. The sign-in password comes from the environment."""

from __future__ import annotations

import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError

from accounts.models import User
from organizations.models import Membership, Workspace
from organizations.services import create_workspace
from properties.models import Property, Space
from properties.services import create_property, create_space
from residents.models import Resident
from residents.services import create_resident

DEMO_WORKSPACE_NAME = "DEMO workspace"

_PROPERTIES: tuple[tuple[str, str, str, str], ...] = (
    (
        "DEMO Harbour House",
        "14 Harbour Road, Osu, Accra",
        "Flat 1",
        "unit",
    ),
    (
        "DEMO Ridge Court",
        "8 Ridge Road, Accra",
        "Room A",
        "room",
    ),
)

_RESIDENTS: tuple[tuple[str, str, str, str], ...] = (
    ("Ama", "Mensah", "demo.ama@example.com", "0244111001"),
    ("Kojo", "Boateng", "demo.kojo@example.com", "0202002202"),
)


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


def _samples(actor: Membership) -> None:
    workspace = actor.workspace
    for name, address, space_name, kind in _PROPERTIES:
        prop = Property.objects.filter(workspace=workspace, name__iexact=name).first()
        if prop is None:
            prop = create_property(
                actor=actor,
                data={"name": name, "address": address},
            )
        if not Space.objects.filter(property=prop, name__iexact=space_name).exists():
            create_space(
                actor=actor,
                data={
                    "name": space_name,
                    "kind": kind,
                    "property_id": prop.id,
                },
            )
    for first_name, last_name, email, phone in _RESIDENTS:
        if Resident.objects.filter(workspace=workspace, email__iexact=email).exists():
            continue
        create_resident(
            actor=actor,
            data={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
            },
        )


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
    _samples(actor)
    return (
        f"{workspace.id} {DEMO_WORKSPACE_NAME} is ready. "
        "Sign in with the DEMO_EMAIL address. The password was not printed."
    )
