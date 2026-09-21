"""Tests for type inference from dtype, numeric values and plain text."""

import json
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from datasonde.inference import (
    SAMPLE_SEED,
    _sample_values,
    infer_column_type,
    infer_types,
)
from datasonde.models import (
    ColumnTypeInference,
    InferenceThresholds,
    InferredType,
    ReasonCode,
    RoleHint,
)
from datasonde.profile import profile_column, profile_dataframe

T = InferredType
R = ReasonCode


def infer(series: pd.Series, **kwargs: Any) -> ColumnTypeInference:
    return infer_column_type(series, profile_column("c", series), **kwargs)


def evidence(result: ColumnTypeInference) -> dict[str, Any]:
    return dict(result.reasons[0].evidence)


def uniques(k: int, repeated_to: int) -> list[int]:
    """``repeated_to`` integers with exactly ``k`` distinct values."""
    return [i % k for i in range(repeated_to)]


# --- Catalogue of cases: one per rule -----------------------------------------------------

CASES = [
    # (series, inferred type, role hint, reason code)
    (pd.Series([None, None, None], dtype="float64"), T.UNKNOWN, None, R.ALL_MISSING),
    (pd.Series([], dtype="float64"), T.UNKNOWN, None, R.ALL_MISSING),
    (pd.Series([[1], [2]]), T.UNKNOWN, None, R.UNSUPPORTED_VALUES),
    (pd.Series([True, False, True]), T.BOOLEAN, None, R.DTYPE_BOOLEAN),
    (pd.Series(pd.to_datetime(["2024-01-01", "2024-02-01"])), T.DATETIME, None, R.DTYPE_DATETIME),
    (pd.Series(["a", "b"], dtype="category"), T.CATEGORICAL, None, R.DTYPE_CATEGORICAL),
    (pd.Series(pd.to_timedelta([1, 2], unit="D")), T.UNKNOWN, None, R.DTYPE_OTHER),
    (pd.Series([0, 1, 0, 1]), T.BOOLEAN, None, R.BINARY_0_1),
    (pd.Series([0.0, 1.0, None]), T.BOOLEAN, None, R.BINARY_0_1),
    (
        pd.Series(range(30)),
        T.NUMERIC_DISCRETE,
        RoleHint.IDENTIFIER_CANDIDATE,
        R.INTEGER_UNIQUE_IDENTIFIER,
    ),
    (pd.Series(uniques(5, 60)), T.NUMERIC_DISCRETE, None, R.INTEGER_FEW_DISTINCT),
    (pd.Series(uniques(100, 300)), T.NUMERIC_CONTINUOUS, None, R.INTEGER_MANY_DISTINCT),
    (pd.Series([i * 1.5 for i in range(30)]), T.NUMERIC_CONTINUOUS, None, R.NON_INTEGER_NUMBERS),
    (pd.Series([True, None, False]), T.BOOLEAN, None, R.OBJECT_BOOL_VALUES),
    (pd.Series([Decimal("1.5"), Decimal("2")]), T.UNKNOWN, None, R.NON_TEXT_OBJECTS),
    (pd.Series(["a", 1, 2.5], dtype=object), T.UNKNOWN, None, R.NON_TEXT_OBJECTS),
    (pd.Series(["yes", "no", "yes"]), T.BOOLEAN, None, R.BOOLEAN_TEXT_VOCABULARY),
    (
        pd.Series([f"id_{i}" for i in range(30)]),
        T.TEXT,
        RoleHint.IDENTIFIER_CANDIDATE,
        R.TEXT_IDENTIFIER_LIKE,
    ),
    (pd.Series([f"v{i}" for i in uniques(10, 100)]), T.CATEGORICAL, None, R.FEW_REPEATED_VALUES),
    (pd.Series([f"v{i}" for i in uniques(200, 400)]), T.TEXT, None, R.FREE_TEXT_FALLBACK),
]


@pytest.mark.parametrize(("series", "expected_type", "expected_role", "code"), CASES)
def test_case_catalogue(
    series: pd.Series, expected_type: T, expected_role: RoleHint | None, code: R
) -> None:
    result = infer(series)
    assert result.inferred_type is expected_type
    assert result.role_hint is expected_role
    assert [reason.code for reason in result.reasons] == [code]
    assert result.warnings == ()
    assert result.overridden is False


def test_catalogue_covers_every_reason_code_used_by_this_step() -> None:
    covered = {case[3] for case in CASES}
    not_yet_used = {
        R.USER_OVERRIDE,
        R.DATETIME_TEXT_FORMAT,
        R.DATETIME_TEXT_AMBIGUOUS,
        R.DATETIME_TEXT_CONFLICT,
        R.NUMERIC_TEXT,
        R.NUMERIC_LOCALE_FORMAT,
        R.NUMERIC_LOOKING_LEADING_ZEROS,
    }
    assert set(R) - not_yet_used == covered


# --- Cases from our experiments ------------------------------------------------------------


def test_unique_floats_are_continuous_without_role() -> None:
    result = infer(pd.Series([i + 0.5 for i in range(50)]))
    assert result.inferred_type is T.NUMERIC_CONTINUOUS
    assert result.role_hint is None


def test_unique_text_with_spaces_is_not_an_identifier() -> None:
    result = infer(pd.Series([f"person number {i}" for i in range(30)]))
    assert result.inferred_type is T.TEXT
    assert result.role_hint is None
    assert result.reasons[0].code is R.FREE_TEXT_FALLBACK


@pytest.mark.parametrize("n", [5, 19])
def test_fewer_than_twenty_rows_gives_no_identifier_hint(n: int) -> None:
    assert infer(pd.Series(range(n))).role_hint is None
    assert infer(pd.Series([f"id_{i}" for i in range(n)])).role_hint is None


def test_float_with_nan_but_integer_values_is_treated_as_integer() -> None:
    series = pd.Series([float(i) for i in range(30)] + [None])
    result = infer(series)
    assert result.inferred_type is T.NUMERIC_DISCRETE
    assert result.role_hint is RoleHint.IDENTIFIER_CANDIDATE


def test_inf_is_not_an_integer() -> None:
    series = pd.Series([float(i) for i in range(30)] + [float("inf")])
    result = infer(series)
    assert result.inferred_type is T.NUMERIC_CONTINUOUS
    assert result.reasons[0].code is R.NON_INTEGER_NUMBERS


def test_nullable_integer_with_na() -> None:
    result = infer(pd.Series(list(range(30)) + [None], dtype="Int64"))
    assert result.role_hint is RoleHint.IDENTIFIER_CANDIDATE


def test_only_one_is_not_boolean() -> None:
    result = infer(pd.Series([1, 1, 1]))
    assert result.inferred_type is T.NUMERIC_DISCRETE
    assert result.reasons[0].code is R.INTEGER_FEW_DISTINCT


def test_zero_one_two_is_not_boolean() -> None:
    assert infer(pd.Series([0, 1, 2])).inferred_type is T.NUMERIC_DISCRETE


# --- Booleans, objects ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "vocabulary"),
    [
        (["true", "false", "true"], "true_false"),
        (["TRUE", "False"], "true_false"),
        (["Yes", "no"], "yes_no"),
        ([" YES ", "\tNo\n"], "yes_no"),
        (["y", "N"], "y_n"),
        (["OUI", "non"], "oui_non"),
        (["T", "f"], "t_f"),
    ],
)
def test_text_boolean_vocabularies(values: list[str], vocabulary: str) -> None:
    result = infer(pd.Series(values))
    assert result.inferred_type is T.BOOLEAN
    assert result.reasons[0].code is R.BOOLEAN_TEXT_VOCABULARY
    assert evidence(result)["vocabulary"] == vocabulary


@pytest.mark.parametrize(
    "values",
    [
        ["yes", "no", "maybe"],
        ["yes", "yes", "yes"],
        ["yes", "Yes", "YES"],
        ["yes", "oui"],
        ["true", "no"],
    ],
)
def test_not_a_boolean_vocabulary(values: list[str]) -> None:
    assert infer(pd.Series(values)).inferred_type is not T.BOOLEAN


def test_python_booleans_in_object_column() -> None:
    result = infer(pd.Series([True, None, False, True], dtype=object))
    assert result.inferred_type is T.BOOLEAN
    assert result.reasons[0].code is R.OBJECT_BOOL_VALUES


def test_mixed_object_evidence_names_the_dominant_type() -> None:
    result = infer(pd.Series(["a", "b", "c", 1], dtype=object))
    assert result.reasons[0].code is R.NON_TEXT_OBJECTS
    assert evidence(result) == {"dominant_share": 0.75, "dominant_type": "str", "n_non_missing": 4}


def test_dominant_type_tie_is_broken_alphabetically() -> None:
    result = infer(pd.Series([1, 2.5], dtype=object))
    assert evidence(result)["dominant_type"] == "float"


# --- Thresholds: just below, exactly at, just above ----------------------------------------


def id_role(series: pd.Series, **threshold: Any) -> RoleHint | None:
    return infer(series, thresholds=InferenceThresholds(**threshold)).role_hint


@pytest.mark.parametrize(
    ("n_unique", "is_identifier"), [(97, False), (98, True), (99, True), (100, True)]
)
def test_identifier_min_unique_ratio(n_unique: int, is_identifier: bool) -> None:
    series = pd.Series(uniques(n_unique, 100))
    expected = RoleHint.IDENTIFIER_CANDIDATE if is_identifier else None
    assert id_role(series, identifier_min_unique_ratio=0.98) is expected


@pytest.mark.parametrize(("n", "is_identifier"), [(24, False), (25, True), (26, True)])
def test_identifier_min_rows(n: int, is_identifier: bool) -> None:
    expected = RoleHint.IDENTIFIER_CANDIDATE if is_identifier else None
    assert id_role(pd.Series(range(n)), identifier_min_rows=25) is expected
    assert id_role(pd.Series([f"id{i}" for i in range(n)]), identifier_min_rows=25) is expected


@pytest.mark.parametrize(
    ("k", "expected"), [(4, T.NUMERIC_DISCRETE), (5, T.NUMERIC_DISCRETE), (6, T.NUMERIC_CONTINUOUS)]
)
def test_discrete_max_unique(k: int, expected: T) -> None:
    result = infer(pd.Series(uniques(k, 60)), thresholds=InferenceThresholds(discrete_max_unique=5))
    assert result.inferred_type is expected


@pytest.mark.parametrize(("k", "expected"), [(9, T.CATEGORICAL), (10, T.CATEGORICAL), (11, T.TEXT)])
def test_categorical_max_unique(k: int, expected: T) -> None:
    series = pd.Series([f"v{i}" for i in uniques(k, 100)])
    result = infer(series, thresholds=InferenceThresholds(categorical_max_unique=10))
    assert result.inferred_type is expected


@pytest.mark.parametrize(("k", "expected"), [(9, T.CATEGORICAL), (10, T.CATEGORICAL), (11, T.TEXT)])
def test_categorical_max_unique_ratio(k: int, expected: T) -> None:
    series = pd.Series([f"v{i}" for i in uniques(k, 40)])
    result = infer(series, thresholds=InferenceThresholds(categorical_max_unique_ratio=0.25))
    assert result.inferred_type is expected


def test_sample_size_is_recorded_only_when_a_sample_is_used() -> None:
    series = pd.Series([f"id_{i}" for i in range(50)])
    sampled = infer(series, thresholds=InferenceThresholds(sample_size=10))
    whole = infer(series, thresholds=InferenceThresholds(sample_size=50))
    assert sampled.reasons[0].code is R.TEXT_IDENTIFIER_LIKE
    assert evidence(sampled)["sample_size"] == 10
    assert evidence(sampled)["population"] == 50
    assert "sample_size" not in evidence(whole)
    assert "population" not in evidence(whole)


# --- Overrides -----------------------------------------------------------------------------


def test_override_with_string_and_enum() -> None:
    series = pd.Series(range(30))
    for value in ("text", T.TEXT):
        result = infer(series, override=value)
        assert result.inferred_type is T.TEXT
        assert result.overridden is True
        assert result.role_hint is None
        assert [reason.code for reason in result.reasons] == [R.USER_OVERRIDE]
        assert evidence(result) == {"automatic_type": "numeric_discrete"}


def test_override_invalid_value_lists_valid_ones() -> None:
    with pytest.raises(ValueError, match="numeric_continuous") as error:
        infer(pd.Series([1, 2]), override="integer")
    assert "'integer'" in str(error.value)


def test_infer_types_overrides() -> None:
    df = pd.DataFrame({"a": range(30), "b": ["x", "y"] * 15})
    result = infer_types(df, profile_dataframe(df), overrides={"a": "categorical"})
    by_name = {c.name: c for c in result.columns}
    assert by_name["a"].inferred_type is T.CATEGORICAL
    assert by_name["a"].overridden is True
    assert by_name["b"].overridden is False


def test_infer_types_rejects_unknown_override_column_and_lists_columns() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(ValueError, match="nope") as error:
        infer_types(df, profile_dataframe(df), overrides={"nope": "text"})
    assert "['a', 'b']" in str(error.value)


def test_infer_types_rejects_invalid_override_value_before_any_computation() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(ValueError, match="valid values"):
        infer_types(df, profile_dataframe(df), overrides={"a": "text", "b": "nonsense"})


# --- infer_types ---------------------------------------------------------------------------


def test_infer_types_covers_columns_in_order_with_thresholds() -> None:
    df = pd.DataFrame({"z": range(30), "a": ["u", "v"] * 15})
    thresholds = InferenceThresholds(sample_size=7)
    result = infer_types(df, profile_dataframe(df), thresholds=thresholds)
    assert [c.name for c in result.columns] == ["z", "a"]
    assert result.thresholds == thresholds


def test_infer_types_uses_default_thresholds() -> None:
    df = pd.DataFrame({"a": [1]})
    assert infer_types(df, profile_dataframe(df)).thresholds == InferenceThresholds()


def test_infer_types_non_string_column_labels() -> None:
    df = pd.DataFrame({0: [1, 2], 1: ["a", "b"]})
    result = infer_types(df, profile_dataframe(df))
    assert [c.name for c in result.columns] == ["0", "1"]


def test_infer_types_rejects_mismatching_profile() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    profile = profile_dataframe(df)
    with pytest.raises(ValueError, match="do not match"):
        infer_types(df.rename(columns={"a": "x"}), profile)
    with pytest.raises(ValueError, match="do not match"):
        infer_types(df[["a"]], profile)
    with pytest.raises(ValueError, match="rows"):
        infer_types(df.iloc[:1], profile)


def test_infer_types_rejects_non_dataframe() -> None:
    with pytest.raises(TypeError):
        infer_types([1, 2], profile_dataframe(pd.DataFrame({"a": [1]})))  # type: ignore[arg-type]


def test_infer_column_type_rejects_length_mismatch() -> None:
    series = pd.Series([1, 2, 3])
    profile = profile_column("c", series)
    with pytest.raises(ValueError, match="rows"):
        infer_column_type(series.iloc[:2], profile)


def test_input_is_not_modified() -> None:
    df = pd.DataFrame({"a": range(30), "b": [f"id_{i}" for i in range(30)]})
    before = df.copy()
    infer_types(df, profile_dataframe(df))
    pd.testing.assert_frame_equal(df, before)


# --- Determinism and pinned sample ---------------------------------------------------------


def test_same_input_gives_same_result() -> None:
    df = pd.DataFrame({"a": range(2000), "b": [f"id_{i}" for i in range(2000)]})
    profile = profile_dataframe(df)
    assert infer_types(df, profile) == infer_types(df, profile)


def test_sample_is_pinned_across_pandas_versions() -> None:
    # Values recorded under pandas 3.0.6 and 2.3.3 (identical): guards the sampling.
    series = pd.Series([f"s{i}" for i in range(5000)], dtype=object)
    sample = _sample_values(series, 1000)
    assert SAMPLE_SEED == 0
    assert len(sample) == 1000
    assert list(sample.head(10)) == [
        "s398", "s3833", "s4836", "s4572", "s636", "s2545", "s1161", "s2230", "s148", "s2530",
    ]  # fmt: skip
    assert int(sample.index.to_series().sum()) == 2511234


def test_small_populations_are_not_sampled() -> None:
    series = pd.Series(["a", "b", "c"])
    assert list(_sample_values(series, 3)) == ["a", "b", "c"]


# --- Output safety and invariants ----------------------------------------------------------


def test_no_cell_value_in_results() -> None:
    df = pd.DataFrame(
        {
            "ids": [f"SECRET_VALUE_{i}" for i in range(30)],
            "mixed": [f"SECRET_VALUE_{i}" if i % 2 else i for i in range(30)],
            "few": [f"SECRET_VALUE_{i % 3}" for i in range(30)],
            "vocab": ["SECRET_VALUE_A", "SECRET_VALUE_B"] * 15,
            "free": [f"SECRET_VALUE {i}" for i in range(30)],
        }
    )
    result = infer_types(df, profile_dataframe(df))
    assert "SECRET_VALUE" not in json.dumps(result.to_dict(), allow_nan=False)


INVARIANT_SERIES = [case[0] for case in CASES] + [
    pd.Series(range(500)),
    pd.Series([f"id_{i}" for i in range(500)]),
    pd.Series([float(i) for i in range(50)] + [None]),
    pd.Series(["a", None, "b"] * 20),
]


@pytest.mark.parametrize("series", INVARIANT_SERIES)
def test_invariants(series: pd.Series) -> None:
    thresholds = InferenceThresholds()
    before = series.copy()
    result = infer(series, thresholds=thresholds)

    assert isinstance(result.inferred_type, InferredType)
    assert result.reasons
    if result.role_hint is RoleHint.IDENTIFIER_CANDIDATE:
        data = evidence(result)
        assert data["unique_ratio"] >= thresholds.identifier_min_unique_ratio
        assert data["n_non_missing"] >= thresholds.identifier_min_rows
    for reason in result.reasons:
        assert all(isinstance(key, str) for key, _ in reason.evidence)
    json.dumps(result.to_dict(), allow_nan=False)
    pd.testing.assert_series_equal(series, before)
