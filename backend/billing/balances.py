"""Derived money. Nothing here is an editable balance column."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from billing.models import Allocation, Invoice, Payment
from common.money import MONEY_QUANTUM

ZERO = Decimal("0.0000")


def line_total(quantity: Decimal, unit_amount: Decimal) -> Decimal:
    return (quantity * unit_amount).quantize(MONEY_QUANTUM)


def allocation_is_active(allocation: Allocation) -> bool:
    try:
        reversal = allocation.reversal
    except ObjectDoesNotExist:
        return True
    return reversal is None


def invoice_total(invoice: Invoice) -> Decimal:
    total = ZERO
    for line in invoice.lines.all():
        total += line.line_total
    return total.quantize(MONEY_QUANTUM)


def invoice_allocated(invoice: Invoice) -> Decimal:
    total = ZERO
    for allocation in invoice.allocations.all():
        if allocation_is_active(allocation):
            total += allocation.amount
    return total.quantize(MONEY_QUANTUM)


def invoice_outstanding(invoice: Invoice) -> Decimal:
    if invoice.status == Invoice.Status.VOID:
        return ZERO
    remaining = invoice_total(invoice) - invoice_allocated(invoice)
    if remaining < 0:
        return ZERO
    return remaining.quantize(MONEY_QUANTUM)


def payment_allocated(payment: Payment) -> Decimal:
    total = ZERO
    for allocation in payment.allocations.all():
        if allocation_is_active(allocation):
            total += allocation.amount
    return total.quantize(MONEY_QUANTUM)


def payment_refunded(payment: Payment) -> Decimal:
    total = ZERO
    for refund in payment.refunds.all():
        total += refund.amount
    return total.quantize(MONEY_QUANTUM)


def payment_unallocated(payment: Payment) -> Decimal:
    if payment.status == Payment.Status.VOID:
        return ZERO
    remaining = payment.amount - payment_allocated(payment) - payment_refunded(payment)
    if remaining < 0:
        return ZERO
    return remaining.quantize(MONEY_QUANTUM)
