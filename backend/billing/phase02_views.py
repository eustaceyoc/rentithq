"""Phase 02 HTTP: recurring preview and Paystack checkout."""

from __future__ import annotations

from datetime import date

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice
from billing.paystack import PaystackError, handle_webhook, start_attempt
from billing.permissions import ensure_can_write_billing
from billing.recurrence import generate_for_workspace, workspace_today
from billing.views import _actor
from organizations.models import Membership
from residents.models import Resident


def _as_of(raw: object, workspace_default: date) -> date:
    if raw is None or raw == "":
        return workspace_default
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ValidationError({"as_of": "Choose a date."}) from exc


class RecurringInvoiceView(APIView):
    def post(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_write_billing(actor)
        payload = request.data
        if not isinstance(payload, dict):
            raise ValidationError({"detail": "Send a JSON object."})
        as_of = _as_of(payload.get("as_of"), workspace_today(actor.workspace))
        dry_run = bool(payload.get("dry_run"))
        run = generate_for_workspace(actor.workspace, as_of, dry_run=dry_run)
        return Response(
            {
                "id": str(run.id),
                "as_of": run.as_of.isoformat(),
                "dry_run": run.dry_run,
                "status": run.status,
                "created_count": run.created_count,
                "skipped_count": run.skipped_count,
                "detail": run.detail,
            }
        )


class PaystackInitializeView(APIView):
    def post(self, request: Request) -> Response:
        actor = _actor(request)
        payload = request.data
        if not isinstance(payload, dict):
            raise ValidationError({"detail": "Send a JSON object."})
        invoice_id = payload.get("invoice_id")
        channel = payload.get("channel")
        if channel not in {"card", "mobile_money"}:
            raise ValidationError({"channel": "Choose card or mobile money."})
        invoice = (
            Invoice.objects.filter(
                workspace_id=actor.workspace_id,
                id=str(invoice_id),
            )
            .select_related("resident")
            .first()
        )
        if invoice is None:
            raise ValidationError(
                {"invoice_id": "Choose an invoice in this workspace."}
            )
        if actor.role == Membership.Role.RESIDENT:
            resident = Resident.objects.filter(
                workspace_id=actor.workspace_id,
                user=actor.user,
            ).first()
            if resident is None or resident.id != invoice.resident_id:
                raise ValidationError({"invoice_id": "Choose your own invoice."})
        else:
            ensure_can_write_billing(actor)
            resident = invoice.resident
        try:
            attempt = start_attempt(
                actor=actor,
                invoice=invoice,
                resident=resident,
                channel=str(channel),
            )
        except PaystackError as exc:
            message = str(exc)
            code = 503 if "not configured" in message or "live keys" in message else 400
            return Response(
                {
                    "error": {
                        "code": "paystack_error",
                        "message": message,
                        "details": {},
                    }
                },
                status=code,
            )
        return Response(
            {
                "reference": attempt.reference,
                "authorization_url": attempt.authorization_url,
                "status": attempt.status,
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        status_code, result = handle_webhook(
            request.body,
            request.headers.get("x-paystack-signature", ""),
        )
        return Response({"status": result}, status=status_code)
