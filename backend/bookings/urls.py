from django.urls import path

from bookings.views import (
    BookingCancelView,
    BookingConvertView,
    BookingDetailView,
    BookingListCreateView,
)

urlpatterns = [
    path("bookings/", BookingListCreateView.as_view(), name="booking-list"),
    path(
        "bookings/<str:booking_id>/",
        BookingDetailView.as_view(),
        name="booking-detail",
    ),
    path(
        "bookings/<str:booking_id>/cancel/",
        BookingCancelView.as_view(),
        name="booking-cancel",
    ),
    path(
        "bookings/<str:booking_id>/convert/",
        BookingConvertView.as_view(),
        name="booking-convert",
    ),
]
