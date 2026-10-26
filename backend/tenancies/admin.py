from django.contrib import admin

from tenancies.models import Assignment, OccupancyBlock, Tenancy


@admin.register(Tenancy)
class TenancyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "resident",
        "status",
        "start_date",
        "end_date",
        "currency_code",
        "workspace",
    )
    list_filter = ("status", "fee_period")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "resident",
        "space",
        "bed",
        "status",
        "start_date",
        "end_date",
        "workspace",
    )
    list_filter = ("status",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(OccupancyBlock)
class OccupancyBlockAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("assignment", "space", "bed", "period", "workspace")
    readonly_fields = ("id",)
