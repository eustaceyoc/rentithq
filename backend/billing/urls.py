from django.urls import path

from billing.views import (
    AllocationCreateView,
    AllocationReverseView,
    ArrearsView,
    InvoiceDetailView,
    InvoiceListCreateView,
    InvoiceVoidView,
    PaymentDetailView,
    PaymentListCreateView,
    PaymentRefundView,
    PaymentVoidView,
)

urlpatterns = [
    path("invoices/", InvoiceListCreateView.as_view(), name="invoice-list"),
    path(
        "invoices/<str:invoice_id>/",
        InvoiceDetailView.as_view(),
        name="invoice-detail",
    ),
    path(
        "invoices/<str:invoice_id>/void/",
        InvoiceVoidView.as_view(),
        name="invoice-void",
    ),
    path("payments/", PaymentListCreateView.as_view(), name="payment-list"),
    path(
        "payments/<str:payment_id>/",
        PaymentDetailView.as_view(),
        name="payment-detail",
    ),
    path(
        "payments/<str:payment_id>/void/",
        PaymentVoidView.as_view(),
        name="payment-void",
    ),
    path(
        "payments/<str:payment_id>/refunds/",
        PaymentRefundView.as_view(),
        name="payment-refund",
    ),
    path("allocations/", AllocationCreateView.as_view(), name="allocation-create"),
    path(
        "allocations/<str:allocation_id>/reverse/",
        AllocationReverseView.as_view(),
        name="allocation-reverse",
    ),
    path("arrears/", ArrearsView.as_view(), name="arrears"),
]
