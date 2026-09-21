"""Tests for per-column profiling."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from datasonde.models import ColumnProfile, DtypeFamily
from datasonde.profile import profile_column, profile_dataframe

UNHASHABLE = "n_unique not computed: unhashable values"
UNSUPPORTED = "n_unique not computed: unsupported dtype"
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


def test_unhashable_message_is_not_the_unsupported_one() -> None:
    p = profile_column("c", pd.Series([[1], [2]]))
    assert p.warnings == (UNHASHABLE,)
    assert UNSUPPORTED not in p.warnings


def test_unsupported_dtype_gives_none_and_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_implemented(*args: object, **kwargs: object) -> int:
        raise NotImplementedError

    monkeypatch.setattr(pd.Series, "nunique", not_implemented)
    p = profile_column("c", pd.Series([1.0, None, 3.0]))
    assert p.n_unique is None
    assert p.warnings == (UNSUPPORTED,)
    assert p.n_rows == 3
    assert p.n_missing == 1
    assert p.n_non_missing == 2
    assert p.missing_rate == pytest.approx(1 / 3)
    assert p.family is DtypeFamily.NUMERIC
    json.dumps(p.to_dict(), allow_nan=False)


@pytest.mark.parametrize("kind", ["list", "struct", "map"])
def test_nested_arrow_dtype_gives_none_and_warning(kind: str) -> None:
    # Skipped in CI (pyarrow is not a dependency); the monkeypatch test covers the branch.
    pa = pytest.importorskip("pyarrow")
    types_and_values = {
        "list": (pa.list_(pa.int64()), [[1, 2], None, [3]]),
        "struct": (pa.struct([("a", pa.int64())]), [{"a": 1}, None, {"a": 2}]),
        "map": (pa.map_(pa.string(), pa.int64()), [[("k", 1)], None, [("j", 2)]]),
    }
    arrow_type, values = types_and_values[kind]
    p = profile_column("c", pd.Series(values, dtype=pd.ArrowDtype(arrow_type)))
    assert p.n_unique is None
    assert p.warnings == (UNSUPPORTED,)
    assert p.n_rows == 3
    assert p.n_missing == 1
    assert p.n_non_missing == 2


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


def _mixed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "num": [1.0, None, 3.0],
            "flag": [True, False, True],
            "when": pd.to_datetime(["2020-01-01", None, "2020-01-03"]),
            "kind": pd.Series(["a", "b", "a"], dtype="category"),
            "text": ["x", "y", None],
            "lists": [[1], [2], [3]],
        }
    )


def test_profile_dataframe_full_profile() -> None:
    profile = profile_dataframe(_mixed_frame())
    assert [c.name for c in profile.columns] == ["num", "flag", "when", "kind", "text", "lists"]
    assert [c.family for c in profile.columns] == [
        DtypeFamily.NUMERIC,
        DtypeFamily.BOOLEAN,
        DtypeFamily.DATETIME,
        DtypeFamily.CATEGORICAL,
        DtypeFamily.TEXT_OR_OBJECT,
        DtypeFamily.TEXT_OR_OBJECT,
    ]
    assert [c.n_missing for c in profile.columns] == [1, 0, 1, 0, 1, 0]
    assert profile.columns[-1].n_unique is None
    assert profile.columns[-1].warnings == (UNHASHABLE,)


def test_profile_dataframe_metadata_matches_columns() -> None:
    profile = profile_dataframe(_mixed_frame())
    assert profile.metadata.n_rows == 3
    assert profile.metadata.n_columns == len(profile.columns) == 6
    assert [c.name for c in profile.metadata.columns] == [c.name for c in profile.columns]
    assert all(c.n_rows == profile.metadata.n_rows for c in profile.columns)


def test_profile_dataframe_non_string_column_names() -> None:
    df = pd.DataFrame({0: [1, None], "a": ["x", "y"], 2.5: [True, False]})
    profile = profile_dataframe(df)
    assert [c.name for c in profile.columns] == ["0", "a", "2.5"]
    assert profile.columns[0].n_missing == 1
    assert profile.columns[1].family is DtypeFamily.TEXT_OR_OBJECT
    assert profile.columns[2].family is DtypeFamily.BOOLEAN


def test_profile_dataframe_repeated_index_values() -> None:
    df = pd.DataFrame({"a": [1, 2, None], "b": ["x", "x", "y"]}, index=[7, 7, 7])
    profile = profile_dataframe(df)
    assert [(c.n_rows, c.n_missing, c.n_unique) for c in profile.columns] == [(3, 1, 2), (3, 0, 2)]


def test_profile_dataframe_zero_rows() -> None:
    profile = profile_dataframe(pd.DataFrame({"a": pd.Series([], dtype="int64")}))
    assert profile.metadata.n_rows == 0
    assert profile.columns[0].missing_rate is None
    assert profile.columns[0].n_unique == 0


def test_profile_dataframe_to_dict_is_strict_json() -> None:
    profile = profile_dataframe(_mixed_frame())
    d = profile.to_dict()
    assert set(d) == {"metadata", "columns"}
    text = json.dumps(d, allow_nan=False)
    assert json.loads(text)["columns"][0]["family"] == "numeric"


def test_profile_dataframe_does_not_modify_input() -> None:
    df = _mixed_frame()
    before = df.copy(deep=True)
    profile_dataframe(df)
    pd.testing.assert_frame_equal(df, before)


@pytest.mark.parametrize(
    ("bad", "error"),
    [
        ([1, 2], TypeError),
        (pd.DataFrame(), ValueError),
        (pd.DataFrame({1: [1], "1": [2]}), ValueError),
    ],
    ids=["not_a_dataframe", "no_columns", "colliding_names"],
)
def test_profile_dataframe_rejects_invalid_input(bad: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        profile_dataframe(bad)
