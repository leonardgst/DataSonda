"""Tests for per-column profiling."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from datasonde.models import ColumnProfile, DtypeFamily
from datasonde.profile import profile_column

UNHASHABLE = "n_unique not computed: unhashable values"
THREE_DATES = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-01"])


def test_numeric_column_nominal() -> None:
    p = profile_column("n", pd.Series([1, 2, 2, 3]))
    assert p == ColumnProfile("n", DtypeFamily.NUMERIC, 4, 0, 4, 0.0, 3, ())


@pytest.mark.parametrize(
    ("series", "family"),
    [
        (pd.Series([True, False, True]), DtypeFamily.BOOLEAN),
        (pd.Series(THREE_DATES), DtypeFamily.DATETIME),
        (pd.Series(["a", "b", "a"], dtype="category"), DtypeFamily.CATEGORICAL),
        (pd.Series(["x", "y", "x"]), DtypeFamily.TEXT_OR_OBJECT),
        (pd.Series([1 + 2j, 1 + 2j, 3j]), DtypeFamily.OTHER),
    ],
    ids=["boolean", "datetime", "category", "text", "complex"],
)
def test_one_column_per_family(series: pd.Series, family: DtypeFamily) -> None:
    p = profile_column("c", series)
    assert p.family is family
    assert (p.n_rows, p.n_missing, p.n_non_missing, p.n_unique) == (3, 0, 3, 2)


@pytest.mark.parametrize(
    "series",
    [
        pd.Series([1.0, None, np.nan]),
        pd.Series(["a", None, pd.NA], dtype="object"),
        pd.Series(pd.to_datetime(["2020-01-01", None, pd.NaT])),
        pd.Series([1, None, pd.NA], dtype="Int64"),
        pd.Series(["a", None, pd.NA], dtype="string"),
    ],
    ids=["float", "object", "datetime", "Int64", "string"],
)
def test_every_kind_of_null_is_missing(series: pd.Series) -> None:
    p = profile_column("c", series)
    assert (p.n_missing, p.n_non_missing, p.n_unique) == (2, 1, 1)


def test_sentinels_are_not_missing() -> None:
    p = profile_column("c", pd.Series(["", " ", "N/A", "-999", "ok"]))
    assert (p.n_missing, p.n_unique) == (0, 5)
    p_inf = profile_column("f", pd.Series([np.inf, -np.inf, 1.0]))
    assert (p_inf.n_missing, p_inf.n_unique) == (0, 3)


def test_zero_rows_gives_none_rate_and_zero_unique() -> None:
    p = profile_column("c", pd.Series([], dtype="float64"))
    assert (p.n_rows, p.n_missing, p.n_non_missing) == (0, 0, 0)
    assert p.missing_rate is None
    assert p.n_unique == 0


def test_single_row() -> None:
    p = profile_column("c", pd.Series([42]))
    assert (p.n_rows, p.missing_rate, p.n_unique) == (1, 0.0, 1)


def test_entirely_empty_column() -> None:
    p = profile_column("c", pd.Series([None, None, None]))
    assert (p.n_missing, p.n_non_missing, p.missing_rate, p.n_unique) == (3, 0, 1.0, 0)


def test_missing_rate_value() -> None:
    p = profile_column("c", pd.Series([1.0, None, None, 4.0]))
    assert p.missing_rate == 0.5


@pytest.mark.parametrize(
    "series",
    [
        pd.Series([[1], [2]]),
        pd.Series([{"a": 1}, {"b": 2}]),
        pd.Series([np.array([1]), np.array([2])]),
    ],
    ids=["list", "dict", "ndarray"],
)
def test_unhashable_values_give_none_and_warning(series: pd.Series) -> None:
    p = profile_column("c", series)
    assert p.n_unique is None
    assert p.warnings == (UNHASHABLE,)
    assert p.n_rows == 2
    assert p.family is DtypeFamily.TEXT_OR_OBJECT


def test_boolean_with_none_is_text_or_object() -> None:
    p = profile_column("c", pd.Series([True, None, False]))
    assert p.family is DtypeFamily.TEXT_OR_OBJECT
    assert (p.n_missing, p.n_unique) == (1, 2)


def test_category_counts_observed_values_only() -> None:
    s = pd.Series(pd.Categorical(["a", "a"], categories=["a", "b"]))
    assert profile_column("c", s).n_unique == 1


def test_datetime_with_timezone() -> None:
    s = pd.Series(pd.to_datetime(["2020-01-01", None]).tz_localize("UTC"))
    p = profile_column("c", s)
    assert (p.family, p.n_missing, p.n_unique) == (DtypeFamily.DATETIME, 1, 1)


def test_non_standard_index_is_ignored() -> None:
    s = pd.Series([1, 2, None], index=["x", "x", "y"])
    p = profile_column("c", s)
    assert (p.n_rows, p.n_missing, p.n_unique) == (3, 1, 2)


def test_input_series_is_not_modified() -> None:
    s = pd.Series([1.0, None, 3.0], name="orig")
    before = s.copy(deep=True)
    profile_column("c", s)
    pd.testing.assert_series_equal(s, before)


@pytest.mark.parametrize(
    "series",
    [
        pd.Series([1, None, 3]),
        pd.Series([], dtype="object"),
        pd.Series([None, None]),
        pd.Series([[1], [2]]),
        pd.Series(["a", "b", "a", None]),
    ],
)
def test_invariants_and_json(series: pd.Series) -> None:
    p = profile_column("c", series)
    assert p.n_missing + p.n_non_missing == p.n_rows
    if p.n_unique is not None:
        assert 0 <= p.n_unique <= p.n_non_missing
    if p.missing_rate is not None:
        assert 0.0 <= p.missing_rate <= 1.0
        assert not math.isnan(p.missing_rate)
    text = json.dumps(p.to_dict(), allow_nan=False)
    assert json.loads(text)["family"] == p.family.value


def test_to_dict_shape() -> None:
    d = profile_column("c", pd.Series([[1]])).to_dict()
    assert set(d) == {
        "name",
        "family",
        "n_rows",
        "n_missing",
        "n_non_missing",
        "missing_rate",
        "n_unique",
        "warnings",
    }
    assert d["family"] == "text_or_object"
    assert d["n_unique"] is None
    assert d["warnings"] == [UNHASHABLE]
