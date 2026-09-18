"""Per-column profiling: dtype family and basic value facts."""

from typing import TYPE_CHECKING

import pandas as pd
from pandas.api import types as pdt

from datasonde.models import ColumnProfile, DtypeFamily

if TYPE_CHECKING:
    from pandas._typing import DtypeObj


def classify_dtype(dtype: "DtypeObj") -> DtypeFamily:
    """Map a pandas dtype to a :class:`DtypeFamily`, identically under pandas 2 and 3.

    Takes the dtype, not the Series, so no values are ever scanned. The order of
    the tests matters:

    * boolean first, because ``is_numeric_dtype`` is True for booleans;
    * complex before numeric: complex numbers have no ordering, so they are
      classified as ``other`` rather than ``numeric``;
    * categorical before text, because ``is_string_dtype`` is True for a
      ``category`` Series;
    * text and ``object`` together: texts are ``str`` under pandas 3 but
      ``object`` under pandas 2.

    Timedelta, period and interval dtypes fall into ``other``. A boolean column
    containing ``None`` is ``object`` and therefore ``text_or_object``, until type
    inference (a later phase) recovers it.
    """
    if pdt.is_bool_dtype(dtype):
        return DtypeFamily.BOOLEAN
    if pdt.is_complex_dtype(dtype):
        return DtypeFamily.OTHER
    if pdt.is_numeric_dtype(dtype):
        return DtypeFamily.NUMERIC
    if pdt.is_datetime64_any_dtype(dtype):
        return DtypeFamily.DATETIME
    if isinstance(dtype, pdt.CategoricalDtype):
        return DtypeFamily.CATEGORICAL
    if pdt.is_string_dtype(dtype) or pdt.is_object_dtype(dtype):
        return DtypeFamily.TEXT_OR_OBJECT
    return DtypeFamily.OTHER


def profile_column(name: str, series: pd.Series) -> ColumnProfile:
    """Compute the basic facts of one column. Does not validate and does not modify ``series``.

    A missing value is a null in the pandas sense (``isna()``: ``None``, ``NaN``,
    ``pd.NA``, ``NaT``). ``inf``, empty strings, blank strings and sentinels such as
    ``"N/A"`` or ``"-999"`` are NOT missing.

    ``n_unique`` excludes missing values, so an entirely empty column has 0 distinct
    values. It is ``None`` (with a warning) when the values are unhashable.
    ``missing_rate`` is ``None`` when the column has no rows.
    """
    n_rows = len(series)
    n_missing = int(series.isna().sum())
    warnings: list[str] = []
    n_unique: int | None
    try:
        n_unique = int(series.nunique(dropna=True))
    except TypeError:
        n_unique = None
        warnings.append("n_unique not computed: unhashable values")
    return ColumnProfile(
        name=name,
        family=classify_dtype(series.dtype),
        n_rows=n_rows,
        n_missing=n_missing,
        n_non_missing=n_rows - n_missing,
        missing_rate=n_missing / n_rows if n_rows else None,
        n_unique=n_unique,
        warnings=tuple(warnings),
    )
