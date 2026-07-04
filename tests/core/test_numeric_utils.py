"""Tests for `core/numeric_utils.py`.

Before this file, only `safe_int` was indirectly exercised (via
`test_delta_engine.py::test_safe_int_handles_pandas_nan_summary_counts`).
`safe_float`, `round2`, `round4`, and `clamp_pct` had zero direct coverage
despite pervasive use for numeric coercion across pipeline/reporter.
"""

from __future__ import annotations

import pytest

from hype_frog.core.numeric_utils import clamp_pct, round2, round4, safe_float, safe_int


# ---------------------------------------------------------------------------
# safe_float
# ---------------------------------------------------------------------------

def test_safe_float_none_returns_default() -> None:
    assert safe_float(None) == 0.0
    assert safe_float(None, default=-1.0) == -1.0


def test_safe_float_numeric_passthrough() -> None:
    assert safe_float(3.5) == 3.5
    assert safe_float(3) == 3.0


def test_safe_float_numeric_string_coerced() -> None:
    assert safe_float("3.14") == 3.14


def test_safe_float_non_numeric_string_returns_default() -> None:
    assert safe_float("not-a-number", default=-1.0) == -1.0


def test_safe_float_nan_returns_default() -> None:
    assert safe_float(float("nan"), default=-1.0) == -1.0


@pytest.mark.parametrize("inf_value", [float("inf"), float("-inf")])
def test_safe_float_inf_returns_default(inf_value: float) -> None:
    assert safe_float(inf_value, default=-1.0) == -1.0


def test_safe_float_rejects_non_coercible_type() -> None:
    assert safe_float(object(), default=-1.0) == -1.0
    assert safe_float([1, 2, 3], default=-1.0) == -1.0


# ---------------------------------------------------------------------------
# round2 / round4
# ---------------------------------------------------------------------------

def test_round2_rounds_to_two_decimal_places() -> None:
    assert round2(3.14159) == 3.14


def test_round2_non_numeric_returns_default() -> None:
    assert round2("bogus", default=-1.0) == -1.0


def test_round2_none_returns_default() -> None:
    assert round2(None) == 0.0


def test_round4_rounds_to_four_decimal_places() -> None:
    assert round4(1.0 / 3.0) == 0.3333


def test_round4_non_numeric_returns_default() -> None:
    assert round4("bogus", default=-1.0) == -1.0


# ---------------------------------------------------------------------------
# clamp_pct
# ---------------------------------------------------------------------------

def test_clamp_pct_within_range_passthrough() -> None:
    assert clamp_pct(42.5) == 42.5


def test_clamp_pct_clamps_above_100() -> None:
    assert clamp_pct(150) == 100.0


def test_clamp_pct_clamps_below_0() -> None:
    assert clamp_pct(-25) == 0.0


def test_clamp_pct_boundary_values() -> None:
    assert clamp_pct(0) == 0.0
    assert clamp_pct(100) == 100.0


def test_clamp_pct_non_numeric_uses_default_then_clamps() -> None:
    assert clamp_pct("bogus", default=-10.0) == 0.0
    assert clamp_pct("bogus", default=150.0) == 100.0


def test_clamp_pct_nan_uses_default() -> None:
    assert clamp_pct(float("nan"), default=50.0) == 50.0


# ---------------------------------------------------------------------------
# safe_int (existing indirect coverage; direct tests added for completeness)
# ---------------------------------------------------------------------------

def test_safe_int_none_returns_default() -> None:
    assert safe_int(None) == 0
    assert safe_int(None, default=7) == 7


def test_safe_int_truncates_float() -> None:
    assert safe_int(3.9) == 3


def test_safe_int_numeric_string_coerced() -> None:
    assert safe_int("42") == 42


def test_safe_int_non_numeric_returns_default() -> None:
    assert safe_int("bogus", default=-1) == -1


def test_safe_int_nan_and_inf_return_default() -> None:
    assert safe_int(float("nan"), default=-1) == -1
    assert safe_int(float("inf"), default=-1) == -1


def test_safe_int_pandas_na_returns_default() -> None:
    pd = pytest.importorskip("pandas")
    assert safe_int(pd.NA, default=-1) == -1
