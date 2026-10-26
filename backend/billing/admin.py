from django.contrib import admin
from django.http import HttpRequest

from billing.models import (
    Allocation,
    AllocationReversal,
    Invoice,
    InvoiceLine,
    InvoiceVoid,
    Payment,
    PaymentVoid,
    Refund,
)


class _HistoryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: object | None = None,
    ) -> bool:
        return False


@admin.register(Invoice)
class InvoiceAdmin(_HistoryAdmin):
    list_display = (
        "reference",
        "resident",
        "status",
        "issued_on",
        "due_on",
        "currency_code",
        "workspace",
    )
    list_filter = ("status",)
    readonly_fields = ("id", "reference", "created_at", "updated_at")


@admin.register(InvoiceLine)
class InvoiceLineAdmin(_HistoryAdmin):
    list_display = ("invoice", "position", "description", "line_total")
    readonly_fields = ("id",)


@admin.register(InvoiceVoid)
class InvoiceVoidAdmin(_HistoryAdmin):
    list_display = ("invoice", "voided_on", "reason")
    readonly_fields = ("id", "created_at")


@admin.register(Payment)
class PaymentAdmin(_HistoryAdmin):
    list_display = (
        "reference",
        "resident",
        "amount",
        "method",
        "status",
        "paid_on",
        "workspace",
    )
    list_filter = ("status", "method")
    readonly_fields = (
        "id",
        "reference",
        "provider",
        "provider_reference",
        "provider_status",
        "created_at",
        "updated_at",
    )


@admin.register(PaymentVoid)
class PaymentVoidAdmin(_HistoryAdmin):
    list_display = ("payment", "voided_on", "reason")
    readonly_fields = ("id", "created_at")


@admin.register(Allocation)
class AllocationAdmin(_HistoryAdmin):
    list_display = ("payment", "invoice", "amount", "workspace")
    readonly_fields = ("id", "created_at")


@admin.register(AllocationReversal)
class AllocationReversalAdmin(_HistoryAdmin):
    list_display = ("allocation", "reversed_on", "reason")
    readonly_fields = ("id", "created_at")


@admin.register(Refund)
class RefundAdmin(_HistoryAdmin):
    list_display = ("payment", "amount", "refunded_on", "workspace")
    readonly_fields = ("id", "created_at")
