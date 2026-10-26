"""Consistent JSON errors. Unhandled failures do not return exception text."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

logger = logging.getLogger(__name__)

_MESSAGES = {
    400: "The request could not be processed.",
    401: "Authentication is required.",
    403: "You do not have permission to do that.",
    404: "Not found.",
    405: "This method is not allowed.",
    429: "Too many requests.",
}

_CODES = {
    400: "validation_error",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    429: "throttled",
}


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    response = exception_handler(exc, context)
    if response is None:
        set_rollback()
        logger.exception("Unhandled API error (%s).", type(exc).__name__)
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": "The server could not complete the request.",
                    "details": {},
                }
            },
            status=500,
        )

    code = _CODES.get(response.status_code, "error")
    message = _MESSAGES.get(response.status_code, "The request could not be processed.")
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = "not_authenticated"
        message = "Authentication is required."
    # Views set these when a 400/403 needs a stable code other than the status default.
    # ValidationError does not set them, so field errors stay validation_error.
    override_code = getattr(exc, "api_code", None)
    override_message = getattr(exc, "api_message", None)
    if isinstance(override_code, str):
        code = override_code
    if isinstance(override_message, str):
        message = override_message

    if isinstance(response.data, dict):
        details: Any = response.data
    else:
        details = {"detail": response.data}
    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    return response
