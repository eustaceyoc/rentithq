"""Platform admin is superuser-only. Workspace owners are not staff."""

from django.contrib import admin
from django.http import HttpRequest


def platform_admin_permission(request: HttpRequest) -> bool:
    user = request.user
    return bool(
        getattr(user, "is_active", False)
        and getattr(user, "is_staff", False)
        and getattr(user, "is_superuser", False)
    )


admin.site.has_permission = platform_admin_permission  # type: ignore[method-assign]
