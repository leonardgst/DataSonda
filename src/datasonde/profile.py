"""Per-column profiling: dtype family and basic value facts."""

from typing import TYPE_CHECKING

from pandas.api import types as pdt

from datasonde.models import DtypeFamily

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
