"""JSON rendering that refuses binary floats and writes money as strings."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from rest_framework.renderers import JSONRenderer
from rest_framework.utils.encoders import JSONEncoder

from common.money import money_to_api_string


def reject_binary_floats(value: object) -> None:
    if isinstance(value, float):
        raise TypeError("JSON responses cannot contain binary floats.")
    if isinstance(value, dict):
        for item in value.values():
            reject_binary_floats(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_binary_floats(item)


class DecimalSafeJSONEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return money_to_api_string(o)
        return super().default(o)


class DecimalJSONRenderer(JSONRenderer):
    encoder_class = DecimalSafeJSONEncoder

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        reject_binary_floats(data)
        rendered = super().render(data, accepted_media_type, renderer_context)
        if rendered is None:
            return b""
        return rendered
