"""Generate one rent invoice per agreement period. A rerun does not duplicate.

Rules, kept small on purpose:
- The period starts on the agreement start date, then every night, week, or
  month. A month uses the same day number, or the last day of a shorter month.
- The invoice date and the due date are that period start. A late run still
  dates the invoice on the period, not on the day the command ran.
- There is no proration. The line is the fee stored on the agreement at the
  moment of generation. A later fee change does not rewrite an issued invoice.
- The deposit is not included. Staff still add it on a manual invoice.
- A cancelled agreement is skipped. There is no paused status.
- An ended agreement is billed only for period starts on or before the day it
  ended. An active agreement with an end date stops the same way. The end date
  is the last occupied day.
- A zero fee is skipped and is not remembered, so a later fee can still bill
  that period.
- "Today" is the workspace timezone, not the server clock.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.utils import timezone

from billing.models import DocumentCounter, Invoice, InvoiceLine
from billing.phase02_models import BillingJobRun, RecurringCharge
from notifications.services import enqueue_invoice_issued
from organizations.models import AuditEvent, Membership, Workspace
from tenancies.models import Tenancy

logger = logging.getLogger(__name__)
ZERO = Decimal("0.0000")


def workspace_today(workspace: Workspace, now: datetime | None = None) -> date:
    moment = now or timezone.now()
    try:
        zone = ZoneInfo(workspace.timezone)
    except Exception:
        zone = ZoneInfo("UTC")
    return moment.astimezone(zone).date()


def _add_period(anchor: date, current: date, period: str) -> date:
    if period == Tenancy.FeePeriod.NIGHT:
        return current + timedelta(days=1)
    if period == Tenancy.FeePeriod.WEEK:
        return current + timedelta(days=7)
    month = current.month + 1
    year = current.year
    if month == 13:
        month = 1
        year += 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor.day, last))


def _last_occupied(tenancy: Tenancy) -> date | None:
    if tenancy.status == Tenancy.Status.CANCELLED:
        return date.min
    if tenancy.status == Tenancy.Status.ENDED and tenancy.ended_on is not None:
        return tenancy.ended_on
    return tenancy.end_date


def period_starts(tenancy: Tenancy, as_of: date) -> list[date]:
    last = _last_occupied(tenancy)
    if last == date.min:
        return []
    starts: list[date] = []
    cursor = tenancy.start_date
    for _ in range(240):
        if cursor > as_of:
            break
        if last is not None and cursor > last:
            break
        starts.append(cursor)
        cursor = _add_period(tenancy.start_date, cursor, tenancy.fee_period)
    return starts


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


def _next_invoice_reference(workspace: Workspace) -> str:
    counter, _created = DocumentCounter.objects.select_for_update().get_or_create(
        workspace=workspace
    )
    number = counter.next_invoice
    counter.next_invoice = number + 1
    counter.save(update_fields=["next_invoice", "next_payment"])
    return f"INV-{number:04d}"


@transaction.atomic
def _issue_period(tenancy: Tenancy, period_start: date, actor: Membership) -> bool:
    if RecurringCharge.objects.filter(
        tenancy=tenancy,
        period_start=period_start,
    ).exists():
        return False
    if tenancy.fee_amount <= ZERO:
        return False
    workspace = Workspace.objects.select_for_update().get(pk=tenancy.workspace_id)
    invoice = Invoice(
        workspace=workspace,
        resident_id=tenancy.resident_id,
        tenancy=tenancy,
        reference=_next_invoice_reference(workspace),
        issued_on=period_start,
        due_on=period_start,
        currency_code=workspace.currency_code,
        status=Invoice.Status.ISSUED,
        recorded_by=actor.user,
    )
    invoice.save()
    InvoiceLine.objects.create(
        invoice=invoice,
        position=1,
        description=f"Rent for the period starting {period_start.isoformat()}",
        quantity=Decimal("1.0000"),
        unit_amount=tenancy.fee_amount,
        line_total=tenancy.fee_amount,
    )
    try:
        RecurringCharge.objects.create(
            workspace=workspace,
            tenancy=tenancy,
            period_start=period_start,
            invoice=invoice,
            fee_amount=tenancy.fee_amount,
            fee_period=tenancy.fee_period,
        )
    except IntegrityError:
        transaction.set_rollback(True)
        return False
    AuditEvent.objects.create(
        workspace=workspace,
        actor=actor.user,
        action=AuditEvent.Action.INVOICE_ISSUED,
        target_type="invoice",
        target_id=invoice.id,
    )
    enqueue_invoice_issued(invoice)
    return True


def generate_for_workspace(
    workspace: Workspace,
    as_of: date,
    *,
    dry_run: bool,
) -> BillingJobRun:
    actor = _owner(workspace)
    created = 0
    skipped = 0
    detail = ""
    status = BillingJobRun.Status.COMPLETED
    if actor is None:
        status = BillingJobRun.Status.FAILED
        detail = "No active owner."
    else:
        tenancies = Tenancy.objects.filter(workspace=workspace).select_related(
            "resident"
        )
        for tenancy in tenancies:
            for start in period_starts(tenancy, as_of):
                if RecurringCharge.objects.filter(
                    tenancy=tenancy,
                    period_start=start,
                ).exists():
                    skipped += 1
                    continue
                if tenancy.fee_amount <= ZERO:
                    skipped += 1
                    continue
                if dry_run:
                    created += 1
                    continue
                try:
                    made = _issue_period(tenancy, start, actor)
                except Exception:
                    logger.exception(
                        "recurring invoice failed workspace=%s",
                        workspace.id,
                    )
                    status = BillingJobRun.Status.FAILED
                    detail = "A period could not be invoiced."
                    made = False
                if made:
                    created += 1
                else:
                    skipped += 1
    run = BillingJobRun.objects.create(
        workspace=workspace,
        kind=BillingJobRun.Kind.RECURRING,
        as_of=as_of,
        dry_run=dry_run,
        status=status,
        created_count=created,
        skipped_count=skipped,
        detail=detail,
        finished_at=timezone.now(),
    )
    logger.info(
        "recurring invoices workspace=%s dry_run=%s created=%s skipped=%s",
        workspace.id,
        dry_run,
        created,
        skipped,
    )
    return run
