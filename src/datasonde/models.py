"""Immutable result containers for DataSonde."""

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
    for an empty DataFrame, ``n_unique`` is ``None`` when values are unhashable
    (see ``warnings``).
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
