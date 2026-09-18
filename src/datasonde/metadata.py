"""DataFrame validation and general metadata computation."""

from typing import Any

import pandas as pd

from datasonde.models import ColumnInfo, DatasetMetadata


def validate_dataframe(df: Any) -> pd.DataFrame:
    """Return ``df`` if it is a usable DataFrame, otherwise raise.

    Raises:
        TypeError: if ``df`` is not a ``pandas.DataFrame``.
        ValueError: if ``df`` has no columns, has duplicate column names, or has
            distinct names that become identical once converted to ``str``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas.DataFrame, got {type(df).__name__}")
    if df.shape[1] == 0:
        raise ValueError("DataFrame has no columns")
    duplicates = df.columns[df.columns.duplicated()].unique().tolist()
    if duplicates:
        raise ValueError(f"DataFrame has duplicate column names: {duplicates}")
    # Labels are distinct for pandas here, so equal string forms are a collision (e.g. 1 and "1").
    names = pd.Index([str(c) for c in df.columns])
    collisions = names[names.duplicated()].unique().tolist()
    if collisions:
        raise ValueError(
            f"DataFrame has column names that collide after string conversion: {collisions}"
        )
    return df


def describe_dataframe(df: Any) -> DatasetMetadata:
    """Validate ``df`` and compute its general metadata."""
    df = validate_dataframe(df)
    memory = df.memory_usage(index=False, deep=True)
    columns = tuple(
        ColumnInfo(name=str(name), dtype=str(df[name].dtype), memory_bytes=int(memory[name]))
        for name in df.columns
    )
    return DatasetMetadata(
        n_rows=len(df),
        n_columns=df.shape[1],
        columns=columns,
        memory_bytes=int(df.memory_usage(index=True, deep=True).sum()),
    )
