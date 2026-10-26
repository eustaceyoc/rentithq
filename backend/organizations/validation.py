"""Shared field checks for workspace settings."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError

from common.money import MoneyFormatError, validate_currency_code


def currency_code_or_error(value: object) -> str:
    try:
        return validate_currency_code(value)
    except MoneyFormatError as exc:
        raise ValidationError(str(exc)) from exc


def timezone_name_or_error(value: object) -> str:
    if not isinstance(value, str):
        raise ValidationError("Enter a valid IANA timezone.")
    name = value.strip()
    if not name or len(name) > 64 or any(character.isspace() for character in name):
        raise ValidationError("Enter a valid IANA timezone.")
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("Enter a valid IANA timezone.") from exc
    return name
