from django.contrib import admin

from notifications.models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("kind", "status", "attempts", "workspace", "created_at")
    list_filter = ("status", "kind")
    readonly_fields = (
        "workspace",
        "kind",
        "dedupe_key",
        "recipient",
        "subject",
        "body",
        "status",
        "attempts",
        "last_error",
        "created_at",
    )
