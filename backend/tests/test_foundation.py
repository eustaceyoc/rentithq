from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.db import models
from rest_framework.exceptions import ValidationError

from common.api.errors import api_exception_handler
from common.api.pagination import StandardPagination
from common.api.renderers import DecimalJSONRenderer
from common.money import (
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
    MoneyFormatError,
    money_amount_field,
    money_to_api_string,
    parse_money,
    validate_currency_code,
)


def test_pagination_limits() -> None:
    pagination = StandardPagination()
    assert pagination.page_size == 25
    assert pagination.max_page_size == 100
    assert pagination.page_size_query_param == "page_size"


def test_money_accepts_plain_decimal_text() -> None:
    assert parse_money("10.5") == Decimal("10.5000")
    assert parse_money("-2") == Decimal("-2.0000")
    assert money_to_api_string("10.5") == "10.5000"


def test_money_rejects_floats_scientific_notation_and_extra_scale() -> None:
    with pytest.raises(MoneyFormatError):
        parse_money(10.5)
    with pytest.raises(MoneyFormatError):
        parse_money("1e2")
    with pytest.raises(MoneyFormatError):
        parse_money("1.23456")
    with pytest.raises(MoneyFormatError):
        parse_money("1,000.00")
    with pytest.raises(MoneyFormatError):
        parse_money(True)


def test_money_rejects_values_outside_the_column_range() -> None:
    with pytest.raises(MoneyFormatError):
        parse_money("1000000000000000")


def test_currency_code_is_structural_only() -> None:
    assert validate_currency_code("EUR") == "EUR"
    with pytest.raises(MoneyFormatError):
        validate_currency_code("usd")
    with pytest.raises(MoneyFormatError):
        validate_currency_code("US")


def test_money_field_is_a_decimal_column() -> None:
    field = money_amount_field()
    assert isinstance(field, models.DecimalField)
    assert field.max_digits == MONEY_MAX_DIGITS
    assert field.decimal_places == MONEY_DECIMAL_PLACES


def test_renderer_writes_decimals_as_strings() -> None:
    rendered = DecimalJSONRenderer().render({"amount": Decimal("10.50")})
    assert rendered is not None
    assert b'"10.5000"' in rendered
    assert json.loads(rendered) == {"amount": "10.5000"}


def test_renderer_refuses_binary_floats() -> None:
    with pytest.raises(TypeError):
        DecimalJSONRenderer().render({"amount": 10.5})


def test_validation_errors_use_the_shared_shape() -> None:
    response = api_exception_handler(
        ValidationError({"email": ["Enter a valid email address."]}),
        {},
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert "email" in response.data["error"]["details"]


def test_unhandled_errors_hide_the_exception_text() -> None:
    response = api_exception_handler(RuntimeError("token=secret"), {})
    assert response.status_code == 500
    assert response.data["error"]["code"] == "server_error"
    assert response.data["error"]["details"] == {}
    rendered = str(response.data)
    assert "token=secret" not in rendered
    assert "RuntimeError" not in rendered
