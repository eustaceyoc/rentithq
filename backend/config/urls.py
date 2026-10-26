from django.contrib import admin
from django.urls import include, path

import config.admin_access  # noqa: F401

admin.site.site_header = "Rent It HQ platform"
admin.site.site_title = "Platform admin"
admin.site.index_title = "Platform operations"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_v1")),
]
