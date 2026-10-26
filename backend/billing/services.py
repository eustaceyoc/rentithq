"""Issue charges and record manual payments. Balances stay derived."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound, ValidationError

from billing.balances import (
    invoice_outstanding,
    payment_unallocated,
)
from billing.models import (
    Allocation,
    AllocationReversal,
    DocumentCounter,
    Invoice,
    InvoiceLine,
    InvoiceVoid,
    Payment,
    PaymentVoid,
    Refund,
)
from billing.permissions import (
    ensure_can_read_billing,
    ensure_can_write_billing,
    ensure_staff_billing,
)
from common.money import MONEY_ABS_LIMIT
from organizations.access import parse_uuid
from organizations.models import AuditEvent, Membership, Workspace
from residents.models import Resident
from tenancies.models import Tenancy

ZERO = Decimal("0.0000")


def _as_drf(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "error_dict"):
        details: dict[str, Any] = {}
        for key, errors in exc.error_dict.items():
            messages: list[str] = []
            for error in errors:
                messages.extend(error.messages)
            details[str(key)] = messages[0] if len(messages) == 1 else messages
        return ValidationError(details)
    return ValidationError(exc.messages)


def _parse_id(raw: str | uuid.UUID) -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    parsed = parse_uuid(raw)
    if parsed is None:
        raise NotFound()
    return parsed


def _audit(
    *,
    actor: Membership,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
) -> None:
    AuditEvent.objects.create(
        workspace=actor.workspace,
        actor=actor.user,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )


def _lock_workspace(actor: Membership) -> Workspace:
    row = Workspace.objects.select_for_update().filter(id=actor.workspace_id).first()
    if row is None:
        raise NotFound()
    return row


def _resident(actor: Membership, raw: uuid.UUID) -> Resident:
    row = Resident.objects.filter(workspace_id=actor.workspace_id, id=raw).first()
    if row is None:
        raise NotFound()
    return row


def _own_resident_ids(actor: Membership) -> list[uuid.UUID]:
    return list(
        Resident.objects.filter(
            workspace_id=actor.workspace_id,
            user_id=actor.user_id,
        ).values_list("id", flat=True)
    )


def _invoice_queryset(actor: Membership) -> QuerySet[Invoice]:
    ensure_can_read_billing(actor)
    rows = (
        Invoice.objects.filter(workspace_id=actor.workspace_id)
        .select_related(
            "resident",
            "recorded_by",
            "tenancy",
        )
        .prefetch_related("lines", "allocations__reversal", "void_record")
    )
    if actor.role != Membership.Role.RESIDENT:
        return rows
    return rows.filter(resident_id__in=_own_resident_ids(actor))


def _payment_queryset(actor: Membership) -> QuerySet[Payment]:
    ensure_can_read_billing(actor)
    rows = (
        Payment.objects.filter(workspace_id=actor.workspace_id)
        .select_related(
            "resident",
            "recorded_by",
        )
        .prefetch_related(
            "allocations__invoice",
            "allocations__reversal",
            "refunds",
            "void_record",
        )
    )
    if actor.role != Membership.Role.RESIDENT:
        return rows
    return rows.filter(resident_id__in=_own_resident_ids(actor))


def list_invoices(actor: Membership) -> QuerySet[Invoice]:
    return _invoice_queryset(actor)


def get_invoice(actor: Membership, raw_id: str) -> Invoice:
    row = _invoice_queryset(actor).filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def list_payments(actor: Membership) -> QuerySet[Payment]:
    return _payment_queryset(actor)


def get_payment(actor: Membership, raw_id: str) -> Payment:
    row = _payment_queryset(actor).filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def list_arrears(actor: Membership, on: date) -> list[Invoice]:
    ensure_staff_billing(actor)
    rows = (
        Invoice.objects.filter(
            workspace_id=actor.workspace_id,
            status=Invoice.Status.ISSUED,
            due_on__lte=on,
        )
        .select_related("resident")
        .prefetch_related("lines", "allocations__reversal")
        .order_by("due_on", "reference")
    )
    return [row for row in rows if invoice_outstanding(row) > 0]


def _next_reference(workspace: Workspace, *, kind: str) -> str:
    counter, _created = DocumentCounter.objects.get_or_create(workspace=workspace)
    if kind == "invoice":
        number = counter.next_invoice
        counter.next_invoice = number + 1
        prefix = "INV"
    else:
        number = counter.next_payment
        counter.next_payment = number + 1
        prefix = "PAY"
    counter.save(update_fields=["next_invoice", "next_payment"])
    return f"{prefix}-{number:04d}"


def _tenancy_for_invoice(
    actor: Membership,
    resident: Resident,
    data: dict[str, Any],
) -> Tenancy | None:
    tenancy_id = data.get("tenancy_id")
    booking_id = data.get("booking_id")
    tenancy: Tenancy | None = None
    if tenancy_id is not None:
        tenancy = Tenancy.objects.filter(
            workspace_id=actor.workspace_id,
            id=tenancy_id,
        ).first()
        if tenancy is None:
            raise NotFound()
    if booking_id is not None:
        from bookings.models import Booking

        booking = Booking.objects.filter(
            workspace_id=actor.workspace_id,
            id=booking_id,
        ).first()
        if booking is None:
            raise NotFound()
        linked = Tenancy.objects.filter(
            workspace_id=actor.workspace_id,
            booking_id=booking.id,
        ).first()
        if linked is None:
            raise ValidationError(
                {"booking_id": ("Convert the reservation before invoicing its fee.")}
            )
        if tenancy is not None and tenancy.id != linked.id:
            raise ValidationError(
                {"booking_id": "The reservation and the agreement do not match."}
            )
        tenancy = linked
    if tenancy is not None and tenancy.resident_id != resident.id:
        raise ValidationError({"tenancy_id": "Choose an agreement for this resident."})
    return tenancy


def _lines_from_tenancy(
    tenancy: Tenancy,
    *,
    include_deposit: bool,
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    if tenancy.fee_amount > 0:
        lines.append(
            {
                "description": "Agreed fee",
                "quantity": Decimal("1.0000"),
                "unit_amount": tenancy.fee_amount,
            }
        )
    if include_deposit and tenancy.deposit_amount > 0:
        lines.append(
            {
                "description": "Deposit",
                "quantity": Decimal("1.0000"),
                "unit_amount": tenancy.deposit_amount,
            }
        )
    if not lines:
        raise ValidationError(
            {"tenancy_id": "The agreement has no fee or deposit to invoice."}
        )
    return lines


def _save(
    instance: Invoice
    | InvoiceLine
    | Payment
    | Allocation
    | Refund
    | InvoiceVoid
    | PaymentVoid
    | AllocationReversal,
) -> None:
    try:
        instance.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc


@transaction.atomic
def issue_invoice(*, actor: Membership, data: dict[str, Any]) -> Invoice:
    ensure_can_write_billing(actor)
    workspace = _lock_workspace(actor)
    resident = _resident(actor, data["resident_id"])
    tenancy = _tenancy_for_invoice(actor, resident, data)
    from_tenancy = bool(data.get("from_tenancy"))
    if from_tenancy and tenancy is None:
        raise ValidationError(
            {"tenancy_id": "Choose an agreement when the invoice uses its fee."}
        )
    if from_tenancy and data.get("lines"):
        raise ValidationError(
            {"lines": "Use the agreement fee or enter lines, not both."}
        )
    raw_lines: list[dict[str, Any]]
    if from_tenancy:
        assert tenancy is not None
        raw_lines = _lines_from_tenancy(
            tenancy,
            include_deposit=bool(data.get("include_deposit")),
        )
    else:
        raw_lines = list(data.get("lines") or [])
    if not raw_lines:
        raise ValidationError({"lines": "Enter a line."})
    invoice = Invoice(
        workspace=workspace,
        resident=resident,
        tenancy=tenancy,
        reference=_next_reference(workspace, kind="invoice"),
        issued_on=data["issued_on"],
        due_on=data["due_on"],
        currency_code=workspace.currency_code,
        status=Invoice.Status.ISSUED,
        recorded_by=actor.user,
    )
    _save(invoice)
    total = ZERO
    for position, raw in enumerate(raw_lines, start=1):
        quantity = raw["quantity"]
        unit_amount = raw["unit_amount"]
        if not isinstance(quantity, Decimal) or not isinstance(unit_amount, Decimal):
            raise ValidationError({"lines": "Enter amounts as decimals."})
        if quantity <= 0:
            raise ValidationError({"quantity": "Enter a quantity greater than zero."})
        if unit_amount <= 0:
            raise ValidationError({"unit_amount": "Enter an amount greater than zero."})
        amount = (quantity * unit_amount).quantize(Decimal("0.0001"))
        if amount >= MONEY_ABS_LIMIT or amount < 0:
            raise ValidationError({"lines": "The line total is out of range."})
        total += amount
        _save(
            InvoiceLine(
                invoice=invoice,
                position=position,
                description=str(raw["description"]),
                quantity=quantity,
                unit_amount=unit_amount,
                line_total=amount,
            )
        )
    if total <= 0:
        raise ValidationError({"lines": "The invoice total must be greater than zero."})
    _audit(
        actor=actor,
        action=AuditEvent.Action.INVOICE_ISSUED,
        target_type="invoice",
        target_id=invoice.id,
    )
    return get_invoice(actor, str(invoice.id))


def _lock_invoice(actor: Membership, raw_id: str) -> Invoice:
    row = (
        Invoice.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    return row


def _lock_payment(actor: Membership, raw_id: str | uuid.UUID) -> Payment:
    row = (
        Payment.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    return row


@transaction.atomic
def void_invoice(
    *,
    actor: Membership,
    raw_id: str,
    reason: str,
    voided_on: date,
) -> Invoice:
    ensure_can_write_billing(actor)
    _lock_workspace(actor)
    invoice = _lock_invoice(actor, raw_id)
    if invoice.status == Invoice.Status.VOID:
        raise ValidationError({"detail": "This invoice is already void."})
    active = Allocation.objects.filter(invoice=invoice).exclude(reversal__isnull=False)
    if active.exists():
        raise ValidationError(
            {"detail": ("Reverse the allocations before voiding this invoice.")}
        )
    invoice.status = Invoice.Status.VOID
    _save(invoice)
    _save(
        InvoiceVoid(
            invoice=invoice,
            reason=reason,
            voided_on=voided_on,
            recorded_by=actor.user,
        )
    )
    _audit(
        actor=actor,
        action=AuditEvent.Action.INVOICE_VOIDED,
        target_type="invoice",
        target_id=invoice.id,
    )
    return get_invoice(actor, str(invoice.id))


@transaction.atomic
def record_payment(*, actor: Membership, data: dict[str, Any]) -> Payment:
    ensure_can_write_billing(actor)
    workspace = _lock_workspace(actor)
    resident = _resident(actor, data["resident_id"])
    amount = data["amount"]
    if not isinstance(amount, Decimal) or amount <= 0:
        raise ValidationError({"amount": "Enter an amount greater than zero."})
    payment = Payment(
        workspace=workspace,
        resident=resident,
        reference=_next_reference(workspace, kind="payment"),
        amount=amount,
        currency_code=workspace.currency_code,
        paid_on=data["paid_on"],
        method=data["method"],
        external_reference=str(data.get("external_reference") or ""),
        status=Payment.Status.RECORDED,
        recorded_by=actor.user,
    )
    _save(payment)
    _audit(
        actor=actor,
        action=AuditEvent.Action.PAYMENT_RECORDED,
        target_type="payment",
        target_id=payment.id,
    )
    return get_payment(actor, str(payment.id))


@transaction.atomic
def void_payment(
    *,
    actor: Membership,
    raw_id: str,
    reason: str,
    voided_on: date,
) -> Payment:
    ensure_can_write_billing(actor)
    _lock_workspace(actor)
    payment = _lock_payment(actor, raw_id)
    if payment.status == Payment.Status.VOID:
        raise ValidationError({"detail": "This payment is already void."})
    if payment.refunds.exists():
        raise ValidationError(
            {"detail": "This payment has a refund and cannot be voided."}
        )
    active = payment.allocations.exclude(reversal__isnull=False)
    if active.exists():
        raise ValidationError(
            {"detail": "Reverse the allocations before voiding this payment."}
        )
    payment.status = Payment.Status.VOID
    _save(payment)
    _save(
        PaymentVoid(
            payment=payment,
            reason=reason,
            voided_on=voided_on,
            recorded_by=actor.user,
        )
    )
    _audit(
        actor=actor,
        action=AuditEvent.Action.PAYMENT_VOIDED,
        target_type="payment",
        target_id=payment.id,
    )
    return get_payment(actor, str(payment.id))


@transaction.atomic
def allocate_payment(*, actor: Membership, data: dict[str, Any]) -> Allocation:
    ensure_can_write_billing(actor)
    _lock_workspace(actor)
    amount = data["amount"]
    if not isinstance(amount, Decimal) or amount <= 0:
        raise ValidationError({"amount": "Enter an amount greater than zero."})
    invoice = _lock_invoice(actor, str(data["invoice_id"]))
    payment = _lock_payment(actor, data["payment_id"])
    if payment.status != Payment.Status.RECORDED:
        raise ValidationError({"payment_id": "That payment is void."})
    if invoice.status != Invoice.Status.ISSUED:
        raise ValidationError({"invoice_id": "That invoice is void."})
    if payment.resident_id != invoice.resident_id:
        raise ValidationError(
            {"invoice_id": "The payment and the invoice are for different residents."}
        )
    if payment.currency_code != invoice.currency_code:
        raise ValidationError(
            {"currency_code": ("The payment and the invoice use different currencies.")}
        )
    payment = get_payment(actor, str(payment.id))
    invoice = get_invoice(actor, str(invoice.id))
    if amount > payment_unallocated(payment):
        raise ValidationError(
            {"amount": "This allocation is more than the unallocated payment."}
        )
    if amount > invoice_outstanding(invoice):
        raise ValidationError(
            {"amount": "This allocation is more than the amount still outstanding."}
        )
    allocation = Allocation(
        workspace_id=actor.workspace_id,
        payment_id=payment.id,
        invoice_id=invoice.id,
        amount=amount,
        currency_code=payment.currency_code,
        recorded_by=actor.user,
    )
    _save(allocation)
    _audit(
        actor=actor,
        action=AuditEvent.Action.ALLOCATION_CREATED,
        target_type="allocation",
        target_id=allocation.id,
    )
    return allocation


@transaction.atomic
def reverse_allocation(
    *,
    actor: Membership,
    raw_id: str,
    reason: str,
    reversed_on: date,
) -> Allocation:
    ensure_can_write_billing(actor)
    _lock_workspace(actor)
    allocation = (
        Allocation.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if allocation is None:
        raise NotFound()
    _lock_invoice(actor, str(allocation.invoice_id))
    _lock_payment(actor, allocation.payment_id)
    if AllocationReversal.objects.filter(allocation=allocation).exists():
        raise ValidationError({"detail": "This allocation is already reversed."})
    _save(
        AllocationReversal(
            allocation=allocation,
            reason=reason,
            reversed_on=reversed_on,
            recorded_by=actor.user,
        )
    )
    _audit(
        actor=actor,
        action=AuditEvent.Action.ALLOCATION_REVERSED,
        target_type="allocation",
        target_id=allocation.id,
    )
    return (
        Allocation.objects.select_related("invoice", "payment")
        .prefetch_related("reversal")
        .get(id=allocation.id)
    )


@transaction.atomic
def record_refund(
    *,
    actor: Membership,
    raw_payment_id: str,
    data: dict[str, Any],
) -> Refund:
    ensure_can_write_billing(actor)
    _lock_workspace(actor)
    payment = _lock_payment(actor, raw_payment_id)
    if payment.status != Payment.Status.RECORDED:
        raise ValidationError({"detail": "That payment is void."})
    amount = data["amount"]
    if not isinstance(amount, Decimal) or amount <= 0:
        raise ValidationError({"amount": "Enter an amount greater than zero."})
    current = get_payment(actor, str(payment.id))
    if amount > payment_unallocated(current):
        raise ValidationError(
            {"amount": "The refund is more than the unallocated payment."}
        )
    refund = Refund(
        workspace_id=actor.workspace_id,
        payment_id=payment.id,
        amount=amount,
        currency_code=payment.currency_code,
        refunded_on=data["refunded_on"],
        reason=str(data["reason"]),
        external_reference=str(data.get("external_reference") or ""),
        recorded_by=actor.user,
    )
    _save(refund)
    _audit(
        actor=actor,
        action=AuditEvent.Action.REFUND_RECORDED,
        target_type="refund",
        target_id=refund.id,
    )
    return refund
