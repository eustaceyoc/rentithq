"""Paystack test-mode charges. A browser return is not a payment.

The secret is read from PAYSTACK_SECRET_KEY. A live key (sk_live_) is refused.
The webhook signature is HMAC-SHA512 of the raw body. Each provider event id is
stored once. A matching success creates one ledger payment and one allocation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from billing.balances import invoice_outstanding
from billing.models import Allocation, DocumentCounter, Invoice, Payment, Refund
from billing.phase02_models import PaymentAttempt, ProviderEvent
from billing.services import get_invoice
from notifications.services import enqueue_payment_receipt
from organizations.models import AuditEvent, Membership, Workspace
from residents.models import Resident

logger = logging.getLogger(__name__)
MINOR = Decimal("0.01")


class PaystackError(Exception):
    """A charge could not be started. The message is safe to show."""


def configured_secret() -> str:
    secret = str(getattr(settings, "PAYSTACK_SECRET_KEY", "") or "").strip()
    if not secret:
        raise PaystackError("Paystack is not configured.")
    if secret.startswith("sk_live_"):
        raise PaystackError("Paystack live keys are refused. Use a test secret.")
    return secret


def to_minor(amount: Decimal) -> int:
    rounded = amount.quantize(MINOR)
    if abs(amount - rounded) > Decimal("0.00005"):
        raise PaystackError("The amount does not fit Paystack's minor units.")
    return int(rounded * 100)


def signature_ok(body: bytes, header: str) -> bool:
    try:
        secret = configured_secret()
    except PaystackError:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, header or "")


def post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST to Paystack. Tests replace this function."""
    secret = configured_secret()
    base = str(getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co"))
    request = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            parsed = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.info("paystack initialize failed %s", type(exc).__name__)
        raise PaystackError("Paystack did not accept the charge.") from exc
    if not isinstance(parsed, dict):
        raise PaystackError("Paystack did not accept the charge.")
    return parsed


def _owner(workspace: Workspace) -> Membership | None:
    return (
        Membership.objects.filter(
            workspace=workspace,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        .order_by("created_at")
        .first()
    )


@transaction.atomic
def start_attempt(
    *,
    actor: Membership,
    invoice: Invoice,
    resident: Resident,
    channel: str,
) -> PaymentAttempt:
    if actor.role == Membership.Role.RESIDENT:
        if resident.user_id != actor.user_id:
            raise PaystackError("Choose your own invoice.")
    elif actor.role not in {Membership.Role.OWNER, Membership.Role.FINANCE}:
        raise PaystackError("You cannot start this charge.")
    if invoice.resident_id != resident.id or invoice.workspace_id != actor.workspace_id:
        raise PaystackError("Choose your own invoice.")
    if invoice.status != Invoice.Status.ISSUED:
        raise PaystackError("This invoice is not payable.")
    if not resident.email:
        raise PaystackError("Add an email on the resident profile first.")
    loaded = get_invoice(actor, str(invoice.id))
    outstanding = invoice_outstanding(loaded)
    if outstanding <= 0:
        raise PaystackError("This invoice has no outstanding amount.")
    minor = to_minor(outstanding)
    attempt = PaymentAttempt.objects.create(
        workspace_id=actor.workspace_id,
        invoice=invoice,
        resident=resident,
        reference=f"psk_{uuid.uuid4().hex[:24]}",
        amount=outstanding.quantize(Decimal("0.0001")),
        amount_minor=minor,
        currency_code=invoice.currency_code,
        channel=channel,
        status=PaymentAttempt.Status.PENDING,
    )
    body = post_json(
        "/transaction/initialize",
        {
            "email": resident.email,
            "amount": minor,
            "currency": invoice.currency_code,
            "reference": attempt.reference,
            "channels": [channel],
            "metadata": {
                "workspace_id": str(actor.workspace_id),
                "invoice_id": str(invoice.id),
                "resident_id": str(resident.id),
                "attempt_id": str(attempt.id),
            },
        },
    )
    raw_data = body.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    url = str(data.get("authorization_url") or "")
    if not url:
        attempt.status = PaymentAttempt.Status.FAILED
        attempt.save(update_fields=["status"])
        raise PaystackError("Paystack did not return a checkout link.")
    attempt.authorization_url = url[:500]
    attempt.save(update_fields=["authorization_url"])
    return attempt


def _next_payment_reference(workspace: Workspace) -> str:
    counter, _created = DocumentCounter.objects.select_for_update().get_or_create(
        workspace=workspace
    )
    number = counter.next_payment
    counter.next_payment = number + 1
    counter.save(update_fields=["next_invoice", "next_payment"])
    return f"PAY-{number:04d}"


def _record_event(
    event_id: str,
    *,
    workspace: Workspace | None,
    status: str,
    detail: str,
) -> bool:
    try:
        ProviderEvent.objects.create(
            provider="paystack",
            provider_event_id=event_id[:80],
            workspace=workspace,
            status=status,
            safe_detail=detail[:200],
        )
    except IntegrityError:
        return False
    return True


@transaction.atomic
def _apply_success(attempt: PaymentAttempt, data: dict[str, Any], event_id: str) -> str:
    currency = str(data.get("currency") or "").upper()
    amount_minor = data.get("amount")
    status = str(data.get("status") or "")
    if (
        currency != attempt.currency_code
        or amount_minor != attempt.amount_minor
        or status != "success"
    ):
        attempt.status = PaymentAttempt.Status.REJECTED
        attempt.save(update_fields=["status"])
        _record_event(
            event_id,
            workspace=attempt.workspace,
            status=ProviderEvent.Status.REJECTED,
            detail="amount, currency, or status did not match",
        )
        return "rejected"
    if Payment.objects.filter(
        workspace=attempt.workspace,
        provider="paystack",
        provider_reference=attempt.reference,
    ).exists():
        _record_event(
            event_id,
            workspace=attempt.workspace,
            status=ProviderEvent.Status.IGNORED,
            detail="payment already recorded",
        )
        return "duplicate"
    actor = _owner(attempt.workspace)
    if actor is None:
        _record_event(
            event_id,
            workspace=attempt.workspace,
            status=ProviderEvent.Status.REJECTED,
            detail="no owner to record the payment",
        )
        return "rejected"
    workspace = Workspace.objects.select_for_update().get(pk=attempt.workspace_id)
    paid_on = timezone.now().date()
    payment = Payment(
        workspace=workspace,
        resident_id=attempt.resident_id,
        reference=_next_payment_reference(workspace),
        amount=attempt.amount,
        currency_code=attempt.currency_code,
        paid_on=paid_on,
        method=attempt.channel,
        status=Payment.Status.RECORDED,
        provider="paystack",
        provider_reference=attempt.reference,
        provider_status="success",
        recorded_by=actor.user,
    )
    payment.save()
    invoice = Invoice.objects.select_for_update().get(pk=attempt.invoice_id)
    loaded = get_invoice(actor, str(invoice.id))
    outstanding = invoice_outstanding(loaded)
    if outstanding >= attempt.amount:
        Allocation.objects.create(
            workspace=workspace,
            payment=payment,
            invoice=invoice,
            amount=attempt.amount,
            currency_code=payment.currency_code,
            recorded_by=actor.user,
        )
        AuditEvent.objects.create(
            workspace=workspace,
            actor=actor.user,
            action=AuditEvent.Action.ALLOCATION_CREATED,
            target_type="allocation",
            target_id=payment.id,
        )
    AuditEvent.objects.create(
        workspace=workspace,
        actor=actor.user,
        action=AuditEvent.Action.PAYMENT_RECORDED,
        target_type="payment",
        target_id=payment.id,
    )
    attempt.status = PaymentAttempt.Status.SUCCESS
    attempt.save(update_fields=["status"])
    fresh = _record_event(
        event_id,
        workspace=workspace,
        status=ProviderEvent.Status.APPLIED,
        detail=f"charge.success {currency} {amount_minor}",
    )
    if not fresh:
        transaction.set_rollback(True)
        return "duplicate"
    enqueue_payment_receipt(payment)
    logger.info("paystack charge applied workspace=%s", workspace.id)
    return "applied"


def _apply_refund(data: dict[str, Any], event_id: str) -> str:
    reference = str(data.get("transaction_reference") or data.get("reference") or "")
    payment = Payment.objects.filter(
        provider="paystack",
        provider_reference=reference,
    ).first()
    if payment is None:
        _record_event(
            event_id,
            workspace=None,
            status=ProviderEvent.Status.IGNORED,
            detail="refund for an unknown charge",
        )
        return "ignored"
    actor = _owner(payment.workspace)
    if actor is None:
        return "rejected"
    refund_id = str(data.get("id") or event_id)
    if Refund.objects.filter(payment=payment, external_reference=refund_id).exists():
        _record_event(
            event_id,
            workspace=payment.workspace,
            status=ProviderEvent.Status.IGNORED,
            detail="refund already recorded",
        )
        return "duplicate"
    from billing.services import record_refund

    minor = data.get("amount")
    if not isinstance(minor, int):
        _record_event(
            event_id,
            workspace=payment.workspace,
            status=ProviderEvent.Status.REJECTED,
            detail="refund amount missing",
        )
        return "rejected"
    amount = (Decimal(minor) / Decimal(100)).quantize(Decimal("0.0001"))
    record_refund(
        actor=actor,
        raw_payment_id=str(payment.id),
        data={
            "amount": amount,
            "refunded_on": timezone.now().date(),
            "reason": "Paystack refund",
            "external_reference": refund_id,
        },
    )
    _record_event(
        event_id,
        workspace=payment.workspace,
        status=ProviderEvent.Status.APPLIED,
        detail="refund.processed",
    )
    return "applied"


def handle_webhook(body: bytes, header: str) -> tuple[int, str]:
    if not signature_ok(body, header):
        return 400, "invalid signature"
    try:
        payload = json.loads(body.decode())
    except (UnicodeError, json.JSONDecodeError):
        return 400, "malformed body"
    if not isinstance(payload, dict):
        return 400, "malformed body"
    event = str(payload.get("event") or "")
    raw_data = payload.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    raw_id = data.get("id")
    reference = str(data.get("reference") or "")
    event_id = str(raw_id or f"{event}:{reference}")
    if ProviderEvent.objects.filter(
        provider="paystack",
        provider_event_id=event_id[:80],
    ).exists():
        return 200, "duplicate"
    if event == "charge.success":
        attempt = PaymentAttempt.objects.filter(reference=reference).first()
        if attempt is None:
            _record_event(
                event_id,
                workspace=None,
                status=ProviderEvent.Status.IGNORED,
                detail="unknown reference",
            )
            return 200, "ignored"
        raw_meta = data.get("metadata")
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        if str(meta.get("workspace_id") or "") != str(attempt.workspace_id):
            _record_event(
                event_id,
                workspace=attempt.workspace,
                status=ProviderEvent.Status.REJECTED,
                detail="workspace did not match",
            )
            return 200, "rejected"
        return 200, _apply_success(attempt, data, event_id)
    if event == "charge.failed":
        attempt = PaymentAttempt.objects.filter(reference=reference).first()
        if attempt is not None:
            attempt.status = PaymentAttempt.Status.FAILED
            attempt.save(update_fields=["status"])
        _record_event(
            event_id,
            workspace=attempt.workspace if attempt else None,
            status=ProviderEvent.Status.APPLIED,
            detail="charge.failed",
        )
        return 200, "failed"
    if event in {"refund.processed", "refund.failed"}:
        if event == "refund.failed":
            _record_event(
                event_id,
                workspace=None,
                status=ProviderEvent.Status.IGNORED,
                detail="refund.failed",
            )
            return 200, "ignored"
        return 200, _apply_refund(data, event_id)
    _record_event(
        event_id,
        workspace=None,
        status=ProviderEvent.Status.IGNORED,
        detail=event[:40] or "unknown event",
    )
    return 200, "ignored"
