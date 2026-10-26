"""Liveness and readiness probes. Responses omit configuration and driver errors."""

from __future__ import annotations

import logging

from django.db import connection
from django.db.utils import Error as DatabaseError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

SERVICE_NAME = "rentithq-api"


class HealthView(APIView):
    """Process liveness. This view does not touch the database."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        response = Response({"status": "ok", "service": SERVICE_NAME})
        response["Cache-Control"] = "no-store"
        return response


class ReadyView(APIView):
    """Readiness. Reports database availability without echoing the failure."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError as exc:
            logger.error(
                "Readiness database check failed (%s).",
                type(exc).__name__,
            )
            response = Response({"status": "unavailable"}, status=503)
        else:
            response = Response({"status": "ok", "database": "ok"})
        response["Cache-Control"] = "no-store"
        return response
