"""CSV built from an already scoped report. Cells cannot start a formula."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from django.http import HttpResponse


def cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def csv_response(filename: str, rows: list[list[object]]) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow([cell(value) for value in row])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


def rows_from(
    header: list[str], records: list[dict[str, Any]], keys: list[str]
) -> list[list[object]]:
    body: list[list[object]] = [list(header)]
    for record in records:
        body.append([record[key] for key in keys])
    return body
