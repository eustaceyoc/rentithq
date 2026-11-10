"""Queue and send resident notices. Failures keep the exception class only."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from billing.balances import invoice_outstanding
from billing.models import Invoice, Payment
from billing.phase02_models import BillingJobRun
from notifications.models import Delivery
from organizations.models import Workspace

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def _send(delivery: Delivery) -> None:
    send_mail(
        delivery.subject,
        delivery.body,
        settings.DEFAULT_FROM_EMAIL,
        [delivery.recipient],
    )


def _enqueue(
    *,
    workspace: Workspace,
    kind: str,
    dedupe_key: str,
    recipient: str,
    subject: str,
    body: str,
) -> Delivery | None:
    if not recipient:
        return None
    try:
        with transaction.atomic():
            return Delivery.objects.create(
                workspace=workspace,
                kind=kind,
                dedupe_key=dedupe_key[:80],
                recipient=recipient,
                subject=subject[:120],
                body=body,
            )
    except IntegrityError:
        return Delivery.objects.filter(
            workspace=workspace,
            dedupe_key=dedupe_key[:80],
        ).first()


def dispatch(delivery: Delivery) -> None:
    if delivery.status == Delivery.Status.SENT:
        return
    if delivery.attempts >= MAX_ATTEMPTS:
        return
    delivery.attempts += 1
    try:
        _send(delivery)
    except Exception as exc:
        delivery.status = Delivery.Status.FAILED
        delivery.last_error = type(exc).__name__[:80]
        delivery.save(update_fields=["status", "attempts", "last_error"])
        logger.info(
            "notification failed workspace=%s kind=%s error=%s",
            delivery.workspace_id,
            delivery.kind,
            delivery.last_error,
        )
        return
    delivery.status = Delivery.Status.SENT
    delivery.last_error = ""
    delivery.save(update_fields=["status", "attempts", "last_error"])


def enqueue_invoice_issued(invoice: Invoice) -> None:
    resident = invoice.resident
    amount = sum((line.line_total for line in invoice.lines.all()), Decimal("0"))
    delivery = _enqueue(
        workspace=invoice.workspace,
        kind="invoice_issued",
        dedupe_key=f"invoice_issued:{invoice.id}",
        recipient=resident.email,
        subject=f"Invoice {invoice.reference}",
        body=(
            f"Invoice {invoice.reference} for {amount} {invoice.currency_code} "
            f"is due on {invoice.due_on.isoformat()}."
        ),
    )
    if delivery is not None and delivery.status == Delivery.Status.PENDING:
        dispatch(delivery)


def enqueue_payment_receipt(payment: Payment) -> None:
    delivery = _enqueue(
        workspace=payment.workspace,
        kind="payment_receipt",
        dedupe_key=f"payment_receipt:{payment.id}",
        recipient=payment.resident.email,
        subject=f"Receipt {payment.reference}",
        body=(
            f"Receipt {payment.reference} records {payment.amount} "
            f"{payment.currency_code} paid on {payment.paid_on.isoformat()}."
        ),
    )
    if delivery is not None and delivery.status == Delivery.Status.PENDING:
        dispatch(delivery)


def send_reminders(workspace: Workspace, as_of: date) -> BillingJobRun:
    due_soon = as_of + timedelta(days=7)
    created = 0
    invoices = Invoice.objects.filter(
        workspace=workspace,
        status=Invoice.Status.ISSUED,
    ).select_related("resident")
    for invoice in invoices:
        if invoice_outstanding(invoice) <= 0:
            continue
        if invoice.due_on == due_soon:
            kind = "invoice_due_soon"
            subject = f"Invoice {invoice.reference} is due soon"
        elif invoice.due_on < as_of:
            kind = "invoice_overdue"
            subject = f"Invoice {invoice.reference} is overdue"
        else:
            continue
        delivery = _enqueue(
            workspace=workspace,
            kind=kind,
            dedupe_key=f"{kind}:{invoice.id}",
            recipient=invoice.resident.email,
            subject=subject,
            body=(
                f"{subject}. The due date is {invoice.due_on.isoformat()}. "
                "This note goes only to the email on your resident profile."
            ),
        )
        if delivery is None:
            continue
        if delivery.status == Delivery.Status.PENDING:
            dispatch(delivery)
            created += 1
    run = BillingJobRun.objects.create(
        workspace=workspace,
        kind=BillingJobRun.Kind.REMINDERS,
        as_of=as_of,
        dry_run=False,
        status=BillingJobRun.Status.COMPLETED,
        created_count=created,
        finished_at=timezone.now(),
    )
    logger.info("billing reminders workspace=%s sent=%s", workspace.id, created)
    return run


def retry_failed() -> int:
    """Retry failed deliveries up to MAX_ATTEMPTS. Returns how many were sent."""
    sent = 0
    rows = Delivery.objects.filter(
        status=Delivery.Status.FAILED,
        attempts__lt=MAX_ATTEMPTS,
    )
    for delivery in rows:
        dispatch(delivery)
        delivery.refresh_from_db()
        if delivery.status == Delivery.Status.SENT:
            sent += 1
    return sent


@transaction.atomic
def deliver_now(delivery: Delivery) -> None:
    dispatch(delivery)
