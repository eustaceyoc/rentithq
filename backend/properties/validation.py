"""Availability rules shared by spaces and beds."""

from __future__ import annotations

AVAILABILITY_VALUES = ("active", "inactive", "unavailable")
BLOCK_REASONS = ("", "maintenance")


def block_pair_error(availability: str, block_reason: str) -> dict[str, str] | None:
    """Return a field error when a block reason does not match availability."""
    if availability not in AVAILABILITY_VALUES:
        return {"availability": "Choose a valid availability."}
    if block_reason not in BLOCK_REASONS:
        return {"block_reason": "Choose a valid block reason."}
    if availability != "unavailable" and block_reason:
        return {
            "block_reason": (
                "Only an unavailable space can record a block reason. "
                "Use unavailable with maintenance to block a space for maintenance."
            )
        }
    return None
