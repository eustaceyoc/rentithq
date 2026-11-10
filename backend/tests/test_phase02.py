"""Recurring rent, Paystack webhooks, and resident notices."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, date, datetime
from typing import Any

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import User
from billing.models import Invoice, Payment
from billing.paystack import signature_ok
from billing.phase02_models import PaymentAttempt, ProviderEvent, RecurringCharge
from billing.recurrence import generate_for_workspace, workspace_today
from notifications.models import Delivery
from notifications.services import retry_failed
from organizations.models import Workspace
from organizations.services import create_workspace
from residents.models import Resident
from tenancies.models import Tenancy

SECRET = "sk_test_phase02_not_a_live_key"


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password="correct-horse-battery")


def make_workspace(owner: User, name: str = "Ada House") -> Workspace:
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


def tenancy(
    client: APIClient,
    workspace: Workspace,
    *,
    start: str = "2026-06-01",
) -> str:
    resident = client.post(
        "/api/v1/residents/",
        {"first_name": "Ama", "last_name": "Mensah", "email": "ama@example.com"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert resident.status_code == 201
    property_row = client.post(
        "/api/v1/properties/",
        {"name": "Harbour House"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    space = client.post(
        "/api/v1/spaces/",
        {
            "property_id": property_row.data["id"],
            "name": "Apartment 1",
            "kind": "unit",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    created = client.post(
        "/api/v1/tenancies/",
        {
            "resident_id": resident.data["id"],
            "space_id": space.data["id"],
            "start_date": start,
            "fee_amount": "800.0000",
            "fee_period": "month",
            "deposit_amount": "0.0000",
        },
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert created.status_code == 201
    Resident.objects.filter(id=resident.data["id"]).update(email="ama@example.com")
    return str(created.data["id"])


@pytest.mark.django_db
def test_recurring_run_is_idempotent_and_skips_a_dry_run() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner)
    client = api_for(owner)
    tenancy(client, workspace)
    preview = client.post(
        "/api/v1/billing/recurring/",
        {"as_of": "2026-07-01", "dry_run": True},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert preview.status_code == 200
    assert preview.data["created_count"] == 2
    assert Invoice.objects.count() == 0
    first = client.post(
        "/api/v1/billing/recurring/",
        {"as_of": "2026-07-01", "dry_run": False},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    second = client.post(
        "/api/v1/billing/recurring/",
        {"as_of": "2026-07-01", "dry_run": False},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert first.data["created_count"] == 2
    assert second.data["created_count"] == 0
    assert second.data["skipped_count"] == 2
    assert Invoice.objects.count() == 2
    assert RecurringCharge.objects.count() == 2
    assert len(mail.outbox) == 2


@pytest.mark.django_db
def test_ended_tenancy_is_not_billed_after_its_last_day() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner)
    client = api_for(owner)
    tenancy_id = tenancy(client, workspace, start="2026-06-01")
    row = Tenancy.objects.get(id=tenancy_id)
    row.status = Tenancy.Status.ENDED
    row.ended_on = date(2026, 6, 15)
    row.save()
    generate_for_workspace(workspace, date(2026, 8, 1), dry_run=False)
    assert list(
        Invoice.objects.order_by("issued_on").values_list("issued_on", flat=True)
    ) == [date(2026, 6, 1)]


@pytest.mark.django_db
def test_cancelled_tenancy_is_not_billed() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner)
    client = api_for(owner)
    tenancy_id = tenancy(client, workspace)
    row = Tenancy.objects.get(id=tenancy_id)
    row.status = Tenancy.Status.CANCELLED
    row.save()
    generate_for_workspace(workspace, date(2026, 8, 1), dry_run=False)
    assert Invoice.objects.count() == 0


@pytest.mark.django_db
def test_workspace_timezone_decides_today() -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner)
    moment = datetime(2026, 6, 1, 6, 0, tzinfo=UTC)
    workspace.timezone = "America/Los_Angeles"
    assert workspace_today(workspace, moment) == date(2026, 5, 31)
    workspace.timezone = "Africa/Accra"
    assert workspace_today(workspace, moment) == date(2026, 6, 1)


def signed(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()


def webhook(
    client: APIClient,
    payload: dict[str, Any],
    *,
    signature: str | None = None,
) -> Any:
    raw = json.dumps(payload).encode()
    return client.post(
        "/api/v1/billing/paystack/webhook/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=signed(raw) if signature is None else signature,
    )


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
@pytest.mark.django_db
def test_webhook_rejects_a_bad_signature_and_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner)
    client = api_for(owner)
    tenancy(client, workspace, start="2026-06-01")
    generate_for_workspace(workspace, date(2026, 6, 1), dry_run=False)
    invoice = Invoice.objects.get()
    resident = Resident.objects.get()

    def fake_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"data": {"authorization_url": "https://checkout.paystack.test/ok"}}

    monkeypatch.setattr("billing.paystack.post_json", fake_post)
    started = client.post(
        "/api/v1/billing/paystack/initialize/",
        {"invoice_id": str(invoice.id), "channel": "card"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert started.status_code == 201
    attempt = PaymentAttempt.objects.get()
    payload = {
        "event": "charge.success",
        "data": {
            "id": 9001,
            "reference": attempt.reference,
            "amount": attempt.amount_minor,
            "currency": "GHS",
            "status": "success",
            "metadata": {
                "workspace_id": str(workspace.id),
                "invoice_id": str(invoice.id),
                "resident_id": str(resident.id),
            },
        },
    }
    anonymous = APIClient()
    bad = webhook(anonymous, payload, signature="not-the-signature")
    assert bad.status_code == 400
    assert Payment.objects.count() == 0
    good = webhook(anonymous, payload)
    assert good.status_code == 200
    assert good.data["status"] == "applied"
    assert Payment.objects.filter(provider="paystack").count() == 1
    again = webhook(anonymous, payload)
    assert again.status_code == 200
    assert again.data["status"] == "duplicate"
    assert Payment.objects.filter(provider="paystack").count() == 1
    assert ProviderEvent.objects.count() == 1


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
@pytest.mark.django_db
def test_webhook_rejects_the_wrong_amount_and_another_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user("ada@example.com")
    other = make_user("bea@example.com")
    workspace = make_workspace(owner)
    elsewhere = make_workspace(other, "Bea House")
    client = api_for(owner)
    tenancy(client, workspace)
    generate_for_workspace(workspace, date(2026, 6, 1), dry_run=False)
    invoice = Invoice.objects.get()
    monkeypatch.setattr(
        "billing.paystack.post_json",
        lambda path, payload: {
            "data": {"authorization_url": "https://checkout.paystack.test/ok"}
        },
    )
    client.post(
        "/api/v1/billing/paystack/initialize/",
        {"invoice_id": str(invoice.id), "channel": "mobile_money"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    attempt = PaymentAttempt.objects.get()
    anonymous = APIClient()
    wrong = webhook(
        anonymous,
        {
            "event": "charge.success",
            "data": {
                "id": 42,
                "reference": attempt.reference,
                "amount": attempt.amount_minor + 1,
                "currency": "GHS",
                "status": "success",
                "metadata": {"workspace_id": str(workspace.id)},
            },
        },
    )
    assert wrong.data["status"] == "rejected"
    assert Payment.objects.count() == 0
    crossed = webhook(
        anonymous,
        {
            "event": "charge.success",
            "data": {
                "id": 43,
                "reference": attempt.reference,
                "amount": attempt.amount_minor,
                "currency": "USD",
                "status": "success",
                "metadata": {"workspace_id": str(elsewhere.id)},
            },
        },
    )
    assert crossed.data["status"] == "rejected"
    assert Payment.objects.filter(workspace=elsewhere).count() == 0


@override_settings(PAYSTACK_SECRET_KEY="")
@pytest.mark.django_db
def test_initialize_without_a_key_does_not_call_paystack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("Paystack was called")

    monkeypatch.setattr("urllib.request.urlopen", fail_open)
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner)
    client = api_for(owner)
    tenancy(client, workspace)
    generate_for_workspace(workspace, date(2026, 6, 1), dry_run=False)
    invoice = Invoice.objects.get()
    response = client.post(
        "/api/v1/billing/paystack/initialize/",
        {"invoice_id": str(invoice.id), "channel": "card"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(workspace.id),
    )
    assert response.status_code == 503
    assert signature_ok(b"{}", "abc") is False


@pytest.mark.django_db
def test_failed_notice_retries_then_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = make_user("ada@example.com")
    workspace = make_workspace(owner)
    client = api_for(owner)
    tenancy(client, workspace)
    calls = {"n": 0}

    def boom(*args: object, **kwargs: object) -> None:
        calls["n"] += 1
        raise OSError("mailbox down")

    monkeypatch.setattr("notifications.services.send_mail", boom)
    generate_for_workspace(workspace, date(2026, 6, 1), dry_run=False)
    delivery = Delivery.objects.get()
    assert delivery.status == Delivery.Status.FAILED
    assert delivery.attempts == 1
    assert delivery.last_error == "OSError"
    assert "mailbox" not in delivery.last_error
    retry_failed()
    retry_failed()
    delivery.refresh_from_db()
    assert delivery.attempts == 3
    retry_failed()
    delivery.refresh_from_db()
    assert delivery.attempts == 3
    assert calls["n"] == 3


@pytest.mark.django_db
def test_overdue_notice_goes_only_to_that_resident() -> None:
    owner = make_user("ada@example.com")
    other = make_user("bea@example.com")
    workspace = make_workspace(owner)
    elsewhere = make_workspace(other, "Bea House")
    client = api_for(owner)
    tenancy(client, workspace, start="2026-06-01")
    generate_for_workspace(workspace, date(2026, 6, 1), dry_run=False)
    mail.outbox.clear()
    from notifications.services import send_reminders

    send_reminders(workspace, date(2026, 6, 10))
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ama@example.com"]
    assert Delivery.objects.filter(workspace=elsewhere).count() == 0
    send_reminders(workspace, date(2026, 6, 11))
    assert len(mail.outbox) == 1
