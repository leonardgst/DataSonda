"""Immutable result containers for DataSonde."""

from dataclasses import dataclass
from typing import Any


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
