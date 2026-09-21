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
    (
        pd.Series([f"{i:05d}" for i in uniques(40, 500)]),
        T.CATEGORICAL,
        RoleHint.CODE_CANDIDATE,
        R.NUMERIC_LOOKING_LEADING_ZEROS,
    ),
    (pd.Series(["1,5", "2,25", "3,75"] * 10), T.UNKNOWN, None, R.NUMERIC_LOCALE_FORMAT),
]

# Numbers stored as text: (series, type, role, [reason codes]). NUMERIC_TEXT comes first.
NUMBER_TEXT_CASES = [
    (
        pd.Series([f"{i}.5" for i in range(30)]),
        T.NUMERIC_CONTINUOUS,
        None,
        [R.NUMERIC_TEXT, R.NON_INTEGER_NUMBERS],
    ),
    (
        pd.Series([str(i) for i in uniques(5, 60)]),
        T.NUMERIC_DISCRETE,
        None,
        [R.NUMERIC_TEXT, R.INTEGER_FEW_DISTINCT],
    ),
    (
        pd.Series([str(i) for i in uniques(100, 300)]),
        T.NUMERIC_CONTINUOUS,
        None,
        [R.NUMERIC_TEXT, R.INTEGER_MANY_DISTINCT],
    ),
    (
        pd.Series([str(1000 + i) for i in range(30)]),
        T.NUMERIC_DISCRETE,
        RoleHint.IDENTIFIER_CANDIDATE,
        [R.NUMERIC_TEXT, R.INTEGER_UNIQUE_IDENTIFIER],
    ),
    (pd.Series(["0", "1"] * 10), T.BOOLEAN, None, [R.NUMERIC_TEXT, R.BINARY_0_1]),
    (
        pd.Series(["-5", "+7", "12", "3.5"] * 10),
        T.NUMERIC_CONTINUOUS,
        None,
        [R.NUMERIC_TEXT, R.NON_INTEGER_NUMBERS],
    ),
]


@pytest.mark.parametrize(("series", "expected_type", "expected_role", "code"), CASES)
def test_case_catalogue(
    series: pd.Series, expected_type: T, expected_role: RoleHint | None, code: R
) -> None:
    result = infer(series)
    assert result.inferred_type is expected_type
    assert result.role_hint is expected_role
    assert [reason.code for reason in result.reasons] == [code]
    assert bool(result.warnings) is (code is R.NUMERIC_LOCALE_FORMAT)
    assert result.overridden is False


@pytest.mark.parametrize(("series", "expected_type", "expected_role", "codes"), NUMBER_TEXT_CASES)
def test_number_text_catalogue(
    series: pd.Series, expected_type: T, expected_role: RoleHint | None, codes: list[R]
) -> None:
    result = infer(series)
    assert result.inferred_type is expected_type
    assert result.role_hint is expected_role
    assert [reason.code for reason in result.reasons] == codes
    assert result.warnings == ()


def test_catalogue_covers_every_reason_code_used_by_this_step() -> None:
    covered = {case[3] for case in CASES}
    covered |= {code for case in NUMBER_TEXT_CASES for code in case[3]}
    covered |= {R.USER_OVERRIDE}  # covered by the override tests
    not_yet_used = {R.DATETIME_TEXT_FORMAT, R.DATETIME_TEXT_AMBIGUOUS, R.DATETIME_TEXT_CONFLICT}
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


# --- Numbers stored as text ----------------------------------------------------------------


def codes(result: ColumnTypeInference) -> list[R]:
    return [reason.code for reason in result.reasons]


def evidence_of(result: ColumnTypeInference, code: R) -> dict[str, Any]:
    return next(dict(reason.evidence) for reason in result.reasons if reason.code is code)


def test_leading_zero_codes_are_never_numbers() -> None:
    result = infer(pd.Series(["00123", "01000"] * 15))
    assert result.inferred_type is T.CATEGORICAL
    assert result.role_hint is RoleHint.CODE_CANDIDATE
    assert codes(result) == [R.NUMERIC_LOOKING_LEADING_ZEROS]


def test_unique_leading_zero_codes_are_text_identifiers() -> None:
    result = infer(pd.Series([f"{i:05d}" for i in range(30)]))
    assert result.inferred_type is T.TEXT
    assert result.role_hint is RoleHint.IDENTIFIER_CANDIDATE
    assert codes(result) == [R.NUMERIC_LOOKING_LEADING_ZEROS]


def test_many_repeated_leading_zero_codes_are_text_with_code_hint() -> None:
    result = infer(pd.Series([f"{i:05d}" for i in uniques(200, 400)]))
    assert result.inferred_type is T.TEXT
    assert result.role_hint is RoleHint.CODE_CANDIDATE


def test_leading_zero_ratio_evidence() -> None:
    result = infer(pd.Series(["007", "8", "9", "10"] * 10))
    data = evidence(result)
    assert data["leading_zero_ratio"] == 0.25
    assert data["parse_ratio"] == 1.0


@pytest.mark.parametrize("values", [["0", "0.5", "10"], ["0", "10", "20"], ["-0.5", "0.25", "3"]])
def test_zero_or_decimal_starting_with_zero_is_not_a_leading_zero_code(values: list[str]) -> None:
    result = infer(pd.Series(values * 10))
    assert R.NUMERIC_LOOKING_LEADING_ZEROS not in codes(result)
    assert R.NUMERIC_TEXT in codes(result)


def test_leading_zeros_in_a_mostly_textual_column_do_not_make_it_numeric() -> None:
    result = infer(pd.Series(["007", "008"] + ["word"] * 98))
    assert codes(result) == [R.FEW_REPEATED_VALUES]


@pytest.mark.parametrize(
    "values",
    [
        ["1,5", "2,25", "10,125"],
        ["1 234", "12 345", "123 456 789"],
        ["1 234", "12 345"],
        ["1 234", "12 345"],
        ["1,234", "12,345,678"],
        ["1,234.56", "1 234,56"],
    ],
)
def test_locale_formats_are_reported_and_never_converted(values: list[str]) -> None:
    result = infer(pd.Series(values * 10))
    assert result.inferred_type is T.UNKNOWN
    assert result.role_hint is None
    assert codes(result) == [R.NUMERIC_LOCALE_FORMAT]
    assert result.warnings == (
        "values look numeric with locale-specific separators: not converted",
    )


def test_canonical_wins_when_it_reaches_the_threshold() -> None:
    result = infer(pd.Series([str(i) for i in range(96)] + ["1,5"] * 4))
    assert R.NUMERIC_TEXT in codes(result)
    assert result.warnings == ()


def test_canonical_and_locale_together_reach_the_threshold() -> None:
    result = infer(pd.Series([str(i) for i in range(50)] + [f"{i},5" for i in range(50)]))
    assert codes(result) == [R.NUMERIC_LOCALE_FORMAT]
    data = evidence(result)
    assert data["parse_ratio"] == 0.5
    assert data["locale_ratio"] == 0.5


def test_locale_values_mixed_with_words_are_plain_text() -> None:
    result = infer(pd.Series(["1,5"] * 90 + ["abc"] * 10))
    assert codes(result) == [R.FEW_REPEATED_VALUES]
    assert result.warnings == ()


@pytest.mark.parametrize(
    "values",
    [
        [" 1", " 2"],  # no strip: a leading space is not canonical
        ["1e5", "2e6"],
        ["0x1F", "0x2A"],
        ["1.", ".5"],
        ["١٢٣", "٤٥٦"],  # non-ASCII digits
    ],
)
def test_non_canonical_number_like_strings_stay_text(values: list[str]) -> None:
    result = infer(pd.Series(values * 10))
    assert codes(result) == [R.FEW_REPEATED_VALUES]


@pytest.mark.parametrize(("numeric", "recognised"), [(89, False), (90, True), (91, True)])
def test_text_parse_min_ratio_boundary(numeric: int, recognised: bool) -> None:
    series = pd.Series([str(i) for i in range(numeric)] + ["N/A"] * (100 - numeric))
    result = infer(series, thresholds=InferenceThresholds(text_parse_min_ratio=0.9))
    assert (R.NUMERIC_TEXT in codes(result)) is recognised


@pytest.mark.parametrize(("numeric", "recognised"), [(94, False), (95, True)])
def test_default_tolerance_is_five_percent(numeric: int, recognised: bool) -> None:
    series = pd.Series([str(i) for i in range(numeric)] + ["N/A"] * (100 - numeric))
    assert (R.NUMERIC_TEXT in codes(infer(series))) is recognised


def test_two_distinct_values_use_exact_counts_without_sampling() -> None:
    series = pd.Series(["1"] * 2990 + ["x"] * 10)
    result = infer(series)
    data = evidence_of(result, R.NUMERIC_TEXT)
    assert data == {"parse_ratio": pytest.approx(2990 / 3000)}
    assert result.inferred_type is T.NUMERIC_DISCRETE


def test_sample_evidence_is_recorded_for_sampled_numbers() -> None:
    result = infer(pd.Series([str(i) for i in range(3000)]))
    assert evidence_of(result, R.NUMERIC_TEXT) == {
        "parse_ratio": 1.0,
        "population": 3000,
        "sample_size": 1000,
    }


def test_number_text_parse_ratio_is_pinned_across_pandas_versions() -> None:
    # Recorded under pandas 3.0.6 and 2.3.3 (identical). The true share on all 5000
    # values is 0.923: the difference comes from the deterministic sample.
    series = pd.Series(["x" if i % 13 == 0 else str(i) for i in range(5000)], dtype=object)
    result = infer(series, thresholds=InferenceThresholds(text_parse_min_ratio=0.9))
    assert evidence_of(result, R.NUMERIC_TEXT) == {
        "parse_ratio": 0.927,
        "population": 5000,
        "sample_size": 1000,
    }


def test_override_keeps_the_automatic_warnings() -> None:
    result = infer(pd.Series(["1,5", "2,25"] * 10), override="numeric_continuous")
    assert result.inferred_type is T.NUMERIC_CONTINUOUS
    assert result.overridden is True
    assert codes(result) == [R.USER_OVERRIDE]
    assert evidence(result) == {"automatic_type": "unknown"}
    assert result.warnings == (
        "values look numeric with locale-specific separators: not converted",
    )


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


INVARIANT_SERIES = (
    [case[0] for case in CASES]
    + [case[0] for case in NUMBER_TEXT_CASES]
    + [
        pd.Series(range(500)),
        pd.Series([f"id_{i}" for i in range(500)]),
        pd.Series([float(i) for i in range(50)] + [None]),
        pd.Series(["a", None, "b"] * 20),
        pd.Series([f"{i:05d}" for i in range(30)]),
        pd.Series(["1 234", "2 345"] * 20),
    ]
)

# Evidence strings must come from closed catalogues, never from cell values.
CLOSED_STRING_EVIDENCE = {"family", "automatic_type", "vocabulary", "dominant_type"}


@pytest.mark.parametrize("series", INVARIANT_SERIES)
def test_invariants(series: pd.Series) -> None:
    thresholds = InferenceThresholds()
    before = series.copy()
    result = infer(series, thresholds=thresholds)

    assert isinstance(result.inferred_type, InferredType)
    assert result.reasons
    if result.role_hint is RoleHint.IDENTIFIER_CANDIDATE:
        all_evidence = [dict(reason.evidence) for reason in result.reasons]
        data = next(item for item in all_evidence if "unique_ratio" in item)
        assert data["unique_ratio"] >= thresholds.identifier_min_unique_ratio
        assert data["n_non_missing"] >= thresholds.identifier_min_rows
    for reason in result.reasons:
        for key, value in reason.evidence:
            if isinstance(value, str):
                assert key in CLOSED_STRING_EVIDENCE
    json.dumps(result.to_dict(), allow_nan=False)
    pd.testing.assert_series_equal(series, before)
