"""DEMO workspace seed. The password is supplied by the test, not the repo."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User
from organizations.demo_seed import DEMO_WORKSPACE_NAME
from organizations.models import Workspace
from properties.models import Property, Space
from residents.models import Resident

EMAIL = "demo.owner@example.com"
PASSWORD = "harbour-ridge-ledger-94"


@pytest.mark.django_db
def test_seed_refuses_to_invent_a_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_EMAIL", raising=False)
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="does not invent a password"):
        call_command("seed_demo")
    assert User.objects.filter(email=EMAIL).count() == 0


@pytest.mark.django_db
def test_seed_is_idempotent_and_labels_the_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_EMAIL", EMAIL)
    monkeypatch.setenv("DEMO_PASSWORD", PASSWORD)
    call_command("seed_demo")
    call_command("seed_demo")
    user = User.objects.get(email=EMAIL)
    assert user.check_password(PASSWORD)
    workspace = Workspace.objects.get(name=DEMO_WORKSPACE_NAME)
    assert workspace.plan_code == "demo"
    assert workspace.currency_code == "GHS"
    assert workspace.timezone == "Africa/Accra"
    assert Property.objects.filter(workspace=workspace).count() == 2
    assert Space.objects.filter(workspace=workspace).count() == 2
    assert Resident.objects.filter(workspace=workspace).count() == 2
    assert set(
        Resident.objects.filter(workspace=workspace).values_list("email", flat=True)
    ) == {"demo.ama@example.com", "demo.kojo@example.com"}
