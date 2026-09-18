"""Tests for DataFrame validation and general metadata."""

import pandas as pd
import pytest

from datasonde.metadata import describe_dataframe, validate_dataframe


def test_validate_returns_same_dataframe() -> None:
    df = pd.DataFrame({"a": [1]})
    assert validate_dataframe(df) is df


def test_validate_rejects_non_dataframe() -> None:
    with pytest.raises(TypeError, match="pandas.DataFrame"):
        validate_dataframe([1, 2, 3])


def test_validate_rejects_no_columns() -> None:
    with pytest.raises(ValueError, match="no columns"):
        validate_dataframe(pd.DataFrame())


def test_validate_rejects_duplicate_columns() -> None:
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    with pytest.raises(ValueError, match="duplicate"):
        validate_dataframe(df)


def test_validate_rejects_names_colliding_after_str_conversion() -> None:
    df = pd.DataFrame({1: [1], "1": [2]})
    with pytest.raises(ValueError, match="collide.*'1'"):
        validate_dataframe(df)


def test_validate_accepts_mixed_non_colliding_names() -> None:
    df = pd.DataFrame({0: [1], "a": [2]})
    assert validate_dataframe(df) is df


def test_describe_shape_and_dtypes() -> None:
    df = pd.DataFrame({"n": [1, 2, 3], "s": ["x", "y", "z"], "f": [0.1, 0.2, 0.3]})
    meta = describe_dataframe(df)
    assert (meta.n_rows, meta.n_columns) == (3, 3)
    assert [c.name for c in meta.columns] == ["n", "s", "f"]
    assert meta.columns[0].dtype == "int64"
    assert meta.columns[2].dtype == "float64"


def test_describe_memory_is_positive_and_consistent() -> None:
    df = pd.DataFrame({"n": range(100), "s": ["abc"] * 100})
    meta = describe_dataframe(df)
    assert all(c.memory_bytes > 0 for c in meta.columns)
    assert meta.memory_bytes >= sum(c.memory_bytes for c in meta.columns)


def test_describe_empty_rows_is_allowed() -> None:
    meta = describe_dataframe(pd.DataFrame({"a": pd.Series([], dtype="int64")}))
    assert meta.n_rows == 0
    assert meta.n_columns == 1


def test_describe_non_string_column_names_are_stringified() -> None:
    meta = describe_dataframe(pd.DataFrame({0: [1], 1: [2]}))
    assert [c.name for c in meta.columns] == ["0", "1"]


def test_to_dict_roundtrip_shape() -> None:
    meta = describe_dataframe(pd.DataFrame({"a": [1, 2]}))
    d = meta.to_dict()
    assert d["n_rows"] == 2
    assert d["columns"][0]["name"] == "a"
    assert set(d) == {"n_rows", "n_columns", "columns", "memory_bytes"}
