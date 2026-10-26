from django.contrib import admin
from django.http import HttpRequest

from organizations.models import AuditEvent, Membership, Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "currency_code",
        "timezone",
        "status",
        "plan_code",
        "created_at",
    )
    list_filter = ("status", "currency_code", "plan_code")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "workspace", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "workspace__name")
    autocomplete_fields = ("user", "workspace")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "action",
        "target_type",
        "target_id",
        "actor",
        "workspace",
        "created_at",
    )
    list_filter = ("action", "target_type")
    search_fields = ("target_id", "actor__email")
    readonly_fields = (
        "id",
        "workspace",
        "actor",
        "action",
        "target_type",
        "target_id",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: AuditEvent | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: AuditEvent | None = None
    ) -> bool:
        return False
