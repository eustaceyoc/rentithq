"""Decimal money helpers. Binary floats are rejected."""

from __future__ import annotations

import re
from decimal import Decimal

from django.db import models

MONEY_MAX_DIGITS = 19
MONEY_DECIMAL_PLACES = 4
MONEY_QUANTUM = Decimal("0.0001")
MONEY_ABS_LIMIT = Decimal(10) ** (MONEY_MAX_DIGITS - MONEY_DECIMAL_PLACES)
_MONEY_TEXT = re.compile(r"^[+-]?(?:\d+|\d+\.\d+)$")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


class MoneyFormatError(ValueError):
    """Raised when a value cannot be stored as money."""


def parse_money(value: object) -> Decimal:
    """Return a canonical 4-decimal Decimal, or raise MoneyFormatError."""
    if isinstance(value, (bool, float)):
        raise MoneyFormatError("Money must not be a boolean or a binary float.")
    if isinstance(value, int):
        amount = Decimal(value)
    elif isinstance(value, str):
        if _MONEY_TEXT.fullmatch(value) is None:
            raise MoneyFormatError(
                "Money must be a plain decimal string with at most 4 fractional digits."
            )
        amount = Decimal(value)
    elif isinstance(value, Decimal):
        amount = value
    else:
        raise MoneyFormatError("Money must be a decimal string, int, or Decimal.")

    if not amount.is_finite():
        raise MoneyFormatError("Money must be a finite decimal.")
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or -exponent > MONEY_DECIMAL_PLACES:
        raise MoneyFormatError("Money supports at most 4 fractional digits.")
    if abs(amount) >= MONEY_ABS_LIMIT:
        raise MoneyFormatError("Money exceeds the supported range.")
    return amount.quantize(MONEY_QUANTUM)


def money_to_api_string(value: object) -> str:
    """Serialize money as a base-10 string with exactly 4 fractional digits."""
    return format(parse_money(value), "f")


def validate_currency_code(code: object) -> str:
    """Accept the shape of an ISO 4217 code without choosing a currency."""
    if not isinstance(code, str) or _CURRENCY_CODE.fullmatch(code) is None:
        raise MoneyFormatError(
            "Currency must be a three-letter uppercase ISO 4217 code."
        )
    return code


def money_amount_field(
    *, null: bool = False, help_text: str = ""
) -> models.DecimalField[Decimal, Decimal]:
    """Column type for a monetary amount. Pair it with an explicit currency code."""
    return models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        null=null,
        blank=null,
        help_text=help_text,
    )
