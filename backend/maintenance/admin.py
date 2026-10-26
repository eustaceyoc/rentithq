from django.contrib import admin
from django.http import HttpRequest

from maintenance.models import MaintenanceRequest, MaintenanceUpdate, RequestCounter


class _KeptAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: object | None = None,
    ) -> bool:
        return False


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(_KeptAdmin):
    list_display = (
        "reference",
        "status",
        "priority",
        "property",
        "workspace",
        "created_at",
    )
    list_filter = ("status", "priority")
    search_fields = ("reference", "description")
    readonly_fields = ("id", "reference", "created_at", "updated_at")


@admin.register(MaintenanceUpdate)
class MaintenanceUpdateAdmin(_KeptAdmin):
    list_display = (
        "request",
        "status_before",
        "status_after",
        "workspace",
        "created_at",
    )
    readonly_fields = ("id", "created_at")


@admin.register(RequestCounter)
class RequestCounterAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("workspace", "next_number")
    readonly_fields = ("workspace",)
