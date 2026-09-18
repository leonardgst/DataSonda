"""Tests for dtype family classification (must be identical under pandas 2 and 3)."""

from collections.abc import Callable

import pandas as pd
import pytest

from datasonde.models import DtypeFamily
from datasonde.profile import classify_dtype

B, N, D = DtypeFamily.BOOLEAN, DtypeFamily.NUMERIC, DtypeFamily.DATETIME
C, T, X = DtypeFamily.CATEGORICAL, DtypeFamily.TEXT_OR_OBJECT, DtypeFamily.OTHER

_DATES = pd.to_datetime(["2020-01-01"])

# (id, factory, expected family)
CASES: list[tuple[str, Callable[[], pd.Series], DtypeFamily]] = [
    ("bool", lambda: pd.Series([True, False]), B),
    ("boolean", lambda: pd.Series([True, None], dtype="boolean"), B),
    ("int", lambda: pd.Series([1, 2]), N),
    ("float", lambda: pd.Series([1.5, 2.5]), N),
    ("Int64", lambda: pd.Series([1, None], dtype="Int64"), N),
    ("datetime", lambda: pd.Series(_DATES), D),
    ("datetime_tz", lambda: pd.Series(_DATES.tz_localize("UTC")), D),
    ("category", lambda: pd.Series(["a", "b"], dtype="category"), C),
    ("text_default", lambda: pd.Series(["a", "b"]), T),
    ("string", lambda: pd.Series(["a", None], dtype="string"), T),
    ("object_lists", lambda: pd.Series([[1], [2]]), T),
    ("empty_object", lambda: pd.Series([], dtype="object"), T),
    ("bool_with_none", lambda: pd.Series([True, None]), T),
    ("complex", lambda: pd.Series([1 + 2j]), X),
    ("timedelta", lambda: pd.Series(pd.to_timedelta([1], unit="D")), X),
    ("period", lambda: pd.Series(pd.period_range("2020", periods=2, freq="M")), X),
    ("interval", lambda: pd.Series(pd.interval_range(0, 2)), X),
]


@pytest.mark.parametrize(
    ("make_series", "expected"),
    [pytest.param(make, family, id=name) for name, make, family in CASES],
)
def test_classify_dtype(make_series: Callable[[], pd.Series], expected: DtypeFamily) -> None:
    assert classify_dtype(make_series().dtype) is expected


def test_family_values_are_lowercase_strings() -> None:
    assert [f.value for f in DtypeFamily] == [
        "numeric",
        "boolean",
        "datetime",
        "categorical",
        "text_or_object",
        "other",
    ]
    assert DtypeFamily.NUMERIC == "numeric"
