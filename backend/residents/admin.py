from django.contrib import admin

from residents.models import Resident


@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("last_name", "first_name", "workspace", "user", "created_at")
    search_fields = ("last_name", "first_name", "email", "workspace__name")
    readonly_fields = ("id", "created_at", "updated_at")
