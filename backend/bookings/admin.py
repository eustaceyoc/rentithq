from django.contrib import admin

from bookings.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("resident", "status", "start_date", "end_date", "workspace")
    list_filter = ("status",)
    readonly_fields = ("id", "created_at", "updated_at")
