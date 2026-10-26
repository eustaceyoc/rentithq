from django.contrib import admin

from properties.models import Bed, Building, Floor, Property, Space


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "workspace", "created_at")
    search_fields = ("name", "workspace__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "property", "workspace", "created_at")
    search_fields = ("name", "property__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "property", "building", "workspace")
    search_fields = ("name", "property__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "kind",
        "availability",
        "block_reason",
        "property",
        "workspace",
    )
    list_filter = ("kind", "availability")
    search_fields = ("name", "property__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "space", "availability", "block_reason", "workspace")
    list_filter = ("availability",)
    search_fields = ("name", "space__name")
    readonly_fields = ("id", "created_at", "updated_at")
