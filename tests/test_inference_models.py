"""Tests for the type inference result models and thresholds (no inference logic)."""

import dataclasses
import json
import math
from enum import StrEnum
from typing import Any

import pytest

from datasonde.models import (
    ColumnTypeInference,
    DatasetTypeInference,
    InferenceThresholds,
    InferredType,
    Reason,
    ReasonCode,
    RoleHint,
)


def strict_json(data: Any) -> Any:
    return json.loads(json.dumps(data, allow_nan=False))


# --- Enums --------------------------------------------------------------------------------


@pytest.mark.parametrize("enum", [InferredType, RoleHint, ReasonCode])
def test_enum_values_are_lowercase_strings(enum: type[StrEnum]) -> None:
    for member in enum:
        assert isinstance(member.value, str)
        assert member.value == member.value.lower()
        assert member.value == member.name.lower()


def test_expected_inferred_types_and_roles() -> None:
    assert {t.value for t in InferredType} == {
        "numeric_continuous",
        "numeric_discrete",
        "categorical",
        "boolean",
        "datetime",
        "text",
        "unknown",
    }
    assert {r.value for r in RoleHint} == {"identifier_candidate", "code_candidate"}


def test_reason_catalogue_size_and_uniqueness() -> None:
    assert len(ReasonCode) == 24
    assert len({code.value for code in ReasonCode}) == 24


# --- Reason -------------------------------------------------------------------------------


def test_reason_create_sorts_evidence_by_key() -> None:
    reason = Reason.create(ReasonCode.NUMERIC_TEXT, b=2, a=1.5, c=None)
    assert reason.evidence == (("a", 1.5), ("b", 2), ("c", None))


def test_reason_to_dict_and_strict_json() -> None:
    reason = Reason.create(
        ReasonCode.DATETIME_TEXT_FORMAT, format="dmy_slash", parse_ratio=0.98, flag=True
    )
    assert reason.to_dict() == {
        "code": "datetime_text_format",
        "evidence": {"flag": True, "format": "dmy_slash", "parse_ratio": 0.98},
    }
    strict_json(reason.to_dict())


def test_reason_without_evidence_is_valid() -> None:
    assert Reason.create(ReasonCode.ALL_MISSING).to_dict() == {
        "code": "all_missing",
        "evidence": {},
    }


def test_reason_is_immutable_and_hashable() -> None:
    reason = Reason.create(ReasonCode.BINARY_0_1, n=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        reason.code = ReasonCode.ALL_MISSING  # type: ignore[misc]
    assert hash(reason) == hash(Reason.create(ReasonCode.BINARY_0_1, n=2))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_reason_rejects_non_finite_floats(bad: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        Reason.create(ReasonCode.NUMERIC_TEXT, ratio=bad)


@pytest.mark.parametrize("bad", [[1], {"a": 1}, (1,), object(), b"x"])
def test_reason_rejects_unsupported_value_types(bad: Any) -> None:
    with pytest.raises(ValueError, match="unsupported type"):
        Reason(ReasonCode.NUMERIC_TEXT, (("k", bad),))


def test_reason_rejects_duplicate_and_non_str_keys() -> None:
    with pytest.raises(ValueError, match="unique"):
        Reason(ReasonCode.NUMERIC_TEXT, (("k", 1), ("k", 2)))
    with pytest.raises(ValueError, match="str"):
        Reason(ReasonCode.NUMERIC_TEXT, ((1, 1),))  # type: ignore[arg-type]


# --- InferenceThresholds ------------------------------------------------------------------


def test_default_thresholds() -> None:
    thresholds = InferenceThresholds()
    assert thresholds.to_dict() == {
        "identifier_min_unique_ratio": 0.99,
        "identifier_min_rows": 20,
        "discrete_max_unique": 20,
        "categorical_max_unique": 50,
        "categorical_max_unique_ratio": 0.5,
        "text_parse_min_ratio": 0.95,
        "sample_size": 1000,
    }
    strict_json(thresholds.to_dict())


RATIOS = ["identifier_min_unique_ratio", "categorical_max_unique_ratio", "text_parse_min_ratio"]
COUNTS = ["identifier_min_rows", "discrete_max_unique", "categorical_max_unique", "sample_size"]


@pytest.mark.parametrize("name", RATIOS)
@pytest.mark.parametrize("value", [1.0, 1, 0.5, 1e-9])
def test_valid_ratios(name: str, value: float) -> None:
    assert getattr(InferenceThresholds(**{name: value}), name) == value


@pytest.mark.parametrize("name", RATIOS)
@pytest.mark.parametrize("value", [0, 0.0, -0.1, 1.0000001, 2, math.nan, math.inf, True, "0.5"])
def test_invalid_ratios(name: str, value: Any) -> None:
    with pytest.raises(ValueError, match=name):
        InferenceThresholds(**{name: value})


@pytest.mark.parametrize("name", COUNTS)
@pytest.mark.parametrize("value", [1, 2, 10_000])
def test_valid_counts(name: str, value: int) -> None:
    assert getattr(InferenceThresholds(**{name: value}), name) == value


@pytest.mark.parametrize("name", COUNTS)
@pytest.mark.parametrize("value", [0, -1, 1.5, True, None, "5"])
def test_invalid_counts(name: str, value: Any) -> None:
    with pytest.raises(ValueError, match=name):
        InferenceThresholds(**{name: value})


def test_thresholds_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        InferenceThresholds().sample_size = 5  # type: ignore[misc]


# --- ColumnTypeInference / DatasetTypeInference -------------------------------------------


def make_column(**overrides: Any) -> ColumnTypeInference:
    values: dict[str, Any] = {
        "name": "age",
        "inferred_type": InferredType.NUMERIC_CONTINUOUS,
        "role_hint": None,
        "reasons": (Reason.create(ReasonCode.NON_INTEGER_NUMBERS, n_unique=12),),
    }
    values.update(overrides)
    return ColumnTypeInference(**values)


def test_column_inference_to_dict() -> None:
    column = make_column(
        role_hint=RoleHint.CODE_CANDIDATE, warnings=("w",), overridden=True
    )
    assert column.to_dict() == {
        "name": "age",
        "inferred_type": "numeric_continuous",
        "role_hint": "code_candidate",
        "reasons": [{"code": "non_integer_numbers", "evidence": {"n_unique": 12}}],
        "warnings": ["w"],
        "overridden": True,
    }
    strict_json(column.to_dict())


def test_column_inference_defaults() -> None:
    column = make_column()
    assert column.warnings == ()
    assert column.overridden is False
    assert column.to_dict()["role_hint"] is None


def test_column_inference_requires_at_least_one_reason() -> None:
    with pytest.raises(ValueError, match="reasons"):
        make_column(reasons=())


def test_dataset_inference_to_dict_keeps_column_order_and_thresholds() -> None:
    thresholds = InferenceThresholds(sample_size=500)
    dataset = DatasetTypeInference(
        columns=(make_column(name="b"), make_column(name="a")), thresholds=thresholds
    )
    data = dataset.to_dict()
    assert [c["name"] for c in data["columns"]] == ["b", "a"]
    assert data["thresholds"]["sample_size"] == 500
    strict_json(data)
