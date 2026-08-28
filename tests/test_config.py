"""Configuration safety tests."""

import pytest

from agentic_brief.config import (
    _validate_location,
    _validate_lookback_hours,
    _validate_model,
)


def test_location_must_remain_global() -> None:
    assert _validate_location("global") == "global"

    with pytest.raises(RuntimeError, match="global"):
        _validate_location("us-central1")


@pytest.mark.parametrize("value", ["0", "169", "not-a-number"])
def test_lookback_hours_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(RuntimeError, match="LOOKBACK"):
        _validate_lookback_hours(value)


def test_lookback_hours_accepts_one_week_or_less() -> None:
    assert _validate_lookback_hours("24") == 24
    assert _validate_lookback_hours("168") == 168


@pytest.mark.parametrize("model", ["gemini-2.5-flash", "gemini-3.0-pro", "other"])
def test_model_rejects_versions_below_hackathon_requirement(model: str) -> None:
    with pytest.raises(RuntimeError, match="3.5"):
        _validate_model(model)


@pytest.mark.parametrize("model", ["gemini-3.5-flash", "gemini-3.7-flash"])
def test_model_accepts_gemini_3_5_or_newer(model: str) -> None:
    assert _validate_model(model) == model
