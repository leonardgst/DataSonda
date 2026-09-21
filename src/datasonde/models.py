"""Immutable result containers for DataSonde."""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DtypeFamily(StrEnum):
    """Coarse, pandas-version-independent family of a column dtype."""

    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    CATEGORICAL = "categorical"
    TEXT_OR_OBJECT = "text_or_object"
    OTHER = "other"


@dataclass(frozen=True)
class ColumnInfo:
    """General information about a single column."""

    name: str
    dtype: str
    memory_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "dtype": self.dtype, "memory_bytes": self.memory_bytes}


@dataclass(frozen=True)
class DatasetMetadata:
    """General metadata about a dataset: shape, column types and memory footprint."""

    n_rows: int
    n_columns: int
    columns: tuple[ColumnInfo, ...]
    memory_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_rows": self.n_rows,
            "n_columns": self.n_columns,
            "columns": [c.to_dict() for c in self.columns],
            "memory_bytes": self.memory_bytes,
        }


@dataclass(frozen=True)
class ColumnProfile:
    """Basic facts about the values of a single column.

    ``None`` means "not computable", never NaN or 0: ``missing_rate`` is ``None``
    for an empty DataFrame, ``n_unique`` is ``None`` when values are unhashable or
    of a type pandas cannot count (see ``warnings``).
    """

    name: str
    family: DtypeFamily
    n_rows: int
    n_missing: int
    n_non_missing: int
    missing_rate: float | None
    n_unique: int | None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family.value,
            "n_rows": self.n_rows,
            "n_missing": self.n_missing,
            "n_non_missing": self.n_non_missing,
            "missing_rate": self.missing_rate,
            "n_unique": self.n_unique,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class DatasetProfile:
    """General metadata plus the basic profile of every column, in column order."""

    metadata: DatasetMetadata
    columns: tuple[ColumnProfile, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "columns": [c.to_dict() for c in self.columns],
        }


class InferredType(StrEnum):
    """Statistical type suggested for a column by the inference rules."""

    NUMERIC_CONTINUOUS = "numeric_continuous"
    NUMERIC_DISCRETE = "numeric_discrete"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TEXT = "text"
    UNKNOWN = "unknown"


class RoleHint(StrEnum):
    """Optional role suggested for a column, in addition to its inferred type."""

    IDENTIFIER_CANDIDATE = "identifier_candidate"
    CODE_CANDIDATE = "code_candidate"


class ReasonCode(StrEnum):
    """Closed catalogue of the rules that can decide an inferred type."""

    USER_OVERRIDE = "user_override"
    ALL_MISSING = "all_missing"
    UNSUPPORTED_VALUES = "unsupported_values"
    DTYPE_BOOLEAN = "dtype_boolean"
    DTYPE_DATETIME = "dtype_datetime"
    DTYPE_CATEGORICAL = "dtype_categorical"
    DTYPE_OTHER = "dtype_other"
    BINARY_0_1 = "binary_0_1"
    INTEGER_UNIQUE_IDENTIFIER = "integer_unique_identifier"
    INTEGER_FEW_DISTINCT = "integer_few_distinct"
    INTEGER_MANY_DISTINCT = "integer_many_distinct"
    NON_INTEGER_NUMBERS = "non_integer_numbers"
    OBJECT_BOOL_VALUES = "object_bool_values"
    NON_TEXT_OBJECTS = "non_text_objects"
    BOOLEAN_TEXT_VOCABULARY = "boolean_text_vocabulary"
    DATETIME_TEXT_FORMAT = "datetime_text_format"
    DATETIME_TEXT_AMBIGUOUS = "datetime_text_ambiguous"
    DATETIME_TEXT_CONFLICT = "datetime_text_conflict"
    NUMERIC_TEXT = "numeric_text"
    NUMERIC_LOCALE_FORMAT = "numeric_locale_format"
    NUMERIC_LOOKING_LEADING_ZEROS = "numeric_looking_leading_zeros"
    TEXT_IDENTIFIER_LIKE = "text_identifier_like"
    FEW_REPEATED_VALUES = "few_repeated_values"
    FREE_TEXT_FALLBACK = "free_text_fallback"


EvidenceValue = int | float | bool | str | None


@dataclass(frozen=True)
class Reason:
    """A rule code and the numbers that triggered it. Never carries a cell value.

    ``evidence`` is an immutable, hashable tuple of ``(key, value)`` pairs sorted by
    key. Allowed values: ``int``, finite ``float``, ``bool``, ``None`` and ``str``
    taken from closed catalogues (a format identifier, a vocabulary identifier, a
    Python type name); the type system cannot enforce that last rule, so the rules
    that build a ``Reason`` must respect it. Use :meth:`create` to build one.
    """

    code: ReasonCode
    evidence: tuple[tuple[str, EvidenceValue], ...] = ()

    def __post_init__(self) -> None:
        keys = [key for key, _ in self.evidence]
        if any(not isinstance(key, str) for key in keys):
            raise ValueError("evidence keys must be str")
        if len(set(keys)) != len(keys):
            raise ValueError("evidence keys must be unique")
        for key, value in self.evidence:
            if value is not None and not isinstance(value, int | float | str):
                raise ValueError(f"evidence {key!r} has unsupported type {type(value).__name__}")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"evidence {key!r} must be a finite float")

    @classmethod
    def create(cls, code: ReasonCode, **evidence: EvidenceValue) -> "Reason":
        """Build a ``Reason`` from keyword evidence, stored sorted by key."""
        return cls(code=code, evidence=tuple(sorted(evidence.items())))

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "evidence": dict(self.evidence)}


@dataclass(frozen=True)
class InferenceThresholds:
    """Thresholds used by the type inference rules (documented in ``inference.py``).

    Ratios must be in ]0, 1] and counts must be >= 1, otherwise ``ValueError``.
    """

    identifier_min_unique_ratio: float = 0.99
    identifier_min_rows: int = 20
    discrete_max_unique: int = 20
    categorical_max_unique: int = 50
    categorical_max_unique_ratio: float = 0.5
    text_parse_min_ratio: float = 0.95
    sample_size: int = 1000

    def __post_init__(self) -> None:
        for name in (
            "identifier_min_unique_ratio",
            "categorical_max_unique_ratio",
            "text_parse_min_ratio",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{name} must be a number in ]0, 1], got {value!r}")
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in ]0, 1], got {value!r}")
        for name in (
            "identifier_min_rows",
            "discrete_max_unique",
            "categorical_max_unique",
            "sample_size",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be an integer >= 1, got {value!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier_min_unique_ratio": self.identifier_min_unique_ratio,
            "identifier_min_rows": self.identifier_min_rows,
            "discrete_max_unique": self.discrete_max_unique,
            "categorical_max_unique": self.categorical_max_unique,
            "categorical_max_unique_ratio": self.categorical_max_unique_ratio,
            "text_parse_min_ratio": self.text_parse_min_ratio,
            "sample_size": self.sample_size,
        }


@dataclass(frozen=True)
class ColumnTypeInference:
    """The interpretation of one column: an inferred type, an optional role and why.

    Unlike :class:`ColumnProfile` (measured facts), this is a suggestion derived from
    documented rules. ``reasons`` is never empty.
    """

    name: str
    inferred_type: InferredType
    role_hint: RoleHint | None
    reasons: tuple[Reason, ...]
    warnings: tuple[str, ...] = ()
    overridden: bool = False

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError("reasons must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "inferred_type": self.inferred_type.value,
            "role_hint": None if self.role_hint is None else self.role_hint.value,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "warnings": list(self.warnings),
            "overridden": self.overridden,
        }


@dataclass(frozen=True)
class DatasetTypeInference:
    """Type inference of every column, in column order, with the thresholds used."""

    columns: tuple[ColumnTypeInference, ...]
    thresholds: InferenceThresholds

    def to_dict(self) -> dict[str, Any]:
        return {
            "thresholds": self.thresholds.to_dict(),
            "columns": [column.to_dict() for column in self.columns],
        }