"""Statistical type inference: an explainable interpretation of each column.

The profile (:mod:`datasonde.profile`) holds measured facts. This module turns them
into *suggestions* (an inferred type, an optional role hint, the reasons and warnings)
from documented rules and thresholds. It never converts or modifies data, never guesses
silently, and never puts a cell value in its results: evidence only holds numbers and
identifiers from closed catalogues.

Rules, in order; the first one that applies wins. ``n`` is the number of non-missing
values, ``unique_ratio`` is ``n_unique / n``. Defaults of the thresholds are in
:class:`~datasonde.models.InferenceThresholds`.

For every column:

1. ``n == 0`` -> ``unknown`` (``ALL_MISSING``).
2. ``n_unique`` not computable (unhashable or unsupported values) -> ``unknown``
   (``UNSUPPORTED_VALUES``).

Then by dtype family:

3. ``boolean`` -> ``boolean``; ``datetime`` -> ``datetime``; ``categorical`` ->
   ``categorical``; ``other`` -> ``unknown`` (``DTYPE_*``).
4. ``numeric``. "Integer" means every non-null value is finite and equal to its
   integer part, checked on the whole column (``inf`` is not an integer):

   a. exactly two distinct values, ``{0, 1}`` -> ``boolean`` (``BINARY_0_1``);
   b. integer, ``unique_ratio >= identifier_min_unique_ratio`` and
      ``n >= identifier_min_rows`` -> ``numeric_discrete`` with role
      ``identifier_candidate`` (``INTEGER_UNIQUE_IDENTIFIER``);
   c. integer, ``n_unique <= discrete_max_unique`` -> ``numeric_discrete``
      (``INTEGER_FEW_DISTINCT``);
   d. integer otherwise -> ``numeric_continuous`` (``INTEGER_MANY_DISTINCT``);
   e. not integer -> ``numeric_continuous`` (``NON_INTEGER_NUMBERS``). A non-integer
      float is never an identifier.
5. ``text_or_object``:

   a. values not all ``str``: all ``bool`` -> ``boolean`` (``OBJECT_BOOL_VALUES``),
      otherwise ``unknown`` (``NON_TEXT_OBJECTS``);
   b. all ``str``, exactly two distinct values which, stripped and case-folded, form
      one of the closed pairs true/false, yes/no, y/n, oui/non, t/f -> ``boolean``
      (``BOOLEAN_TEXT_VOCABULARY``);
   c. numbers stored as text. Canonical form: ``[+-]?[0-9]+(\\.[0-9]+)?`` on the raw
      string (no strip; no scientific notation or hexadecimal). If at least
      ``text_parse_min_ratio`` of the values are canonical:

      * at least one integer with a leading zero (``007``) -> a code, never a number:
        ``categorical`` if rule 5d-ii holds, else ``text``; role
        ``identifier_candidate`` if the counts of rule 5d-i hold, else ``code_candidate``
        (``NUMERIC_LOOKING_LEADING_ZEROS``);
      * otherwise the numeric rules 4a-4e apply, "integer" meaning that no canonical
        value has a decimal point, with the extra reason ``NUMERIC_TEXT``.

      Otherwise, if some values use regional separators (decimal comma, thousands
      space, non-breaking or narrow space, thousands comma) and canonical + regional
      values reach ``text_parse_min_ratio`` -> ``unknown`` (``NUMERIC_LOCALE_FORMAT``),
      with a warning. Such values are never converted and the comma is never guessed
      (``1,234`` is ambiguous);
   d. for the remaining strings:

      i. ``unique_ratio >= identifier_min_unique_ratio``, ``n >= identifier_min_rows``
         and no whitespace in the sample -> ``text`` with role ``identifier_candidate``
         (``TEXT_IDENTIFIER_LIKE``);
      ii. ``n_unique <= categorical_max_unique`` and
          ``unique_ratio <= categorical_max_unique_ratio`` -> ``categorical``
          (``FEW_REPEATED_VALUES``);
      iii. otherwise -> ``text`` (``FREE_TEXT_FALLBACK``).

Text analyses run on the non-null values, or on a deterministic sample of at most
``sample_size`` of them (``sample(random_state=SAMPLE_SEED)``) when there are more.
With at most two distinct values, counts are exact over the whole column instead.
"""

from collections.abc import Mapping
from dataclasses import replace

import pandas as pd
from pandas.api import types as pdt

from datasonde.metadata import validate_dataframe
from datasonde.models import (
    ColumnProfile,
    ColumnTypeInference,
    DatasetProfile,
    DatasetTypeInference,
    DtypeFamily,
    InferenceThresholds,
    InferredType,
    Reason,
    ReasonCode,
    RoleHint,
)

SAMPLE_SEED = 0

_BOOLEAN_VOCABULARIES: dict[str, frozenset[str]] = {
    "true_false": frozenset({"true", "false"}),
    "yes_no": frozenset({"yes", "no"}),
    "y_n": frozenset({"y", "n"}),
    "oui_non": frozenset({"oui", "non"}),
    "t_f": frozenset({"t", "f"}),
}

# Patterns for numbers stored as text, matched on the raw string (no strip) with
# ``str.fullmatch``. Digits are ASCII only.
_CANONICAL_NUMBER = r"[+-]?[0-9]+(\.[0-9]+)?"
_LEADING_ZERO_INTEGER = r"[+-]?0[0-9]+"
_LOCALE_NUMBERS = (
    r"[+-]?[0-9]+,[0-9]+",  # decimal comma
    r"[+-]?[0-9]{1,3}([   ][0-9]{3})+([.,][0-9]+)?",  # space thousands
    r"[+-]?[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?",  # comma thousands
)
LOCALE_NUMBER_WARNING = "values look numeric with locale-specific separators: not converted"

_DTYPE_RULES: dict[DtypeFamily, tuple[InferredType, ReasonCode]] = {
    DtypeFamily.BOOLEAN: (InferredType.BOOLEAN, ReasonCode.DTYPE_BOOLEAN),
    DtypeFamily.DATETIME: (InferredType.DATETIME, ReasonCode.DTYPE_DATETIME),
    DtypeFamily.CATEGORICAL: (InferredType.CATEGORICAL, ReasonCode.DTYPE_CATEGORICAL),
    DtypeFamily.OTHER: (InferredType.UNKNOWN, ReasonCode.DTYPE_OTHER),
}


def _meets_identifier_counts(
    unique_ratio: float, n_non_missing: int, thresholds: InferenceThresholds
) -> bool:
    return (
        unique_ratio >= thresholds.identifier_min_unique_ratio
        and n_non_missing >= thresholds.identifier_min_rows
    )


def _is_categorical(n_unique: int, unique_ratio: float, thresholds: InferenceThresholds) -> bool:
    return (
        n_unique <= thresholds.categorical_max_unique
        and unique_ratio <= thresholds.categorical_max_unique_ratio
    )


def _sample_values(non_null: pd.Series, sample_size: int) -> pd.Series:
    """Return ``non_null``, or a deterministic sample of ``sample_size`` of its values."""
    if len(non_null) > sample_size:
        return non_null.sample(sample_size, random_state=SAMPLE_SEED)
    return non_null


def _is_integer_valued(non_null: pd.Series) -> bool:
    """True when every value is finite and equal to its integer part (``inf`` is not)."""
    return bool((non_null.astype("float64") % 1 == 0).all())


def _classify_numeric(
    *,
    n_unique: int,
    n_non_missing: int,
    is_integer: bool,
    is_binary: bool,
    thresholds: InferenceThresholds,
) -> tuple[InferredType, RoleHint | None, Reason]:
    """Numeric rules 4a-4e, shared with numbers stored as text."""
    unique_ratio = n_unique / n_non_missing
    if is_binary:
        reason = Reason.create(ReasonCode.BINARY_0_1, n_non_missing=n_non_missing)
        return InferredType.BOOLEAN, None, reason
    if not is_integer:
        reason = Reason.create(
            ReasonCode.NON_INTEGER_NUMBERS, n_unique=n_unique, n_non_missing=n_non_missing
        )
        return InferredType.NUMERIC_CONTINUOUS, None, reason
    if _meets_identifier_counts(unique_ratio, n_non_missing, thresholds):
        reason = Reason.create(
            ReasonCode.INTEGER_UNIQUE_IDENTIFIER,
            n_unique=n_unique,
            n_non_missing=n_non_missing,
            unique_ratio=unique_ratio,
        )
        return InferredType.NUMERIC_DISCRETE, RoleHint.IDENTIFIER_CANDIDATE, reason
    if n_unique <= thresholds.discrete_max_unique:
        reason = Reason.create(
            ReasonCode.INTEGER_FEW_DISTINCT, n_unique=n_unique, n_non_missing=n_non_missing
        )
        return InferredType.NUMERIC_DISCRETE, None, reason
    reason = Reason.create(
        ReasonCode.INTEGER_MANY_DISTINCT, n_unique=n_unique, n_non_missing=n_non_missing
    )
    return InferredType.NUMERIC_CONTINUOUS, None, reason


def _result(
    profile: ColumnProfile,
    inferred_type: InferredType,
    reason: Reason,
    role_hint: RoleHint | None = None,
    warnings: tuple[str, ...] = (),
) -> ColumnTypeInference:
    return ColumnTypeInference(
        name=profile.name,
        inferred_type=inferred_type,
        role_hint=role_hint,
        reasons=(reason,),
        warnings=warnings,
    )


def _infer_numeric(
    series: pd.Series, profile: ColumnProfile, n_unique: int, thresholds: InferenceThresholds
) -> ColumnTypeInference:
    non_null = series.dropna()
    is_binary = n_unique == 2 and set(non_null.unique()) == {0, 1}
    inferred_type, role_hint, reason = _classify_numeric(
        n_unique=n_unique,
        n_non_missing=profile.n_non_missing,
        is_integer=_is_integer_valued(non_null),
        is_binary=is_binary,
        thresholds=thresholds,
    )
    return _result(profile, inferred_type, reason, role_hint)


def _dominant_type(non_null: pd.Series) -> tuple[str, int]:
    """Name and count of the most frequent Python type (ties: alphabetical order)."""
    counts = {
        str(name): int(count)
        for name, count in non_null.map(lambda value: type(value).__name__).value_counts().items()
    }
    dominant = min(counts, key=lambda name: (-counts[name], name))
    return dominant, counts[dominant]


def _boolean_vocabulary(distinct_values: list[str]) -> str | None:
    normalised = frozenset(value.strip().casefold() for value in distinct_values)
    for identifier, pair in _BOOLEAN_VOCABULARIES.items():
        if normalised == pair:
            return identifier
    return None


def _matching(distinct: pd.Series, *patterns: str) -> pd.Series:
    """Boolean mask of the distinct values that fully match at least one pattern."""
    mask = distinct.str.fullmatch(patterns[0])
    for pattern in patterns[1:]:
        mask = mask | distinct.str.fullmatch(pattern)
    return mask


def _share(counts: pd.Series, mask: pd.Series) -> float:
    """Share of the values (weighted by their count) selected by ``mask``."""
    return int(counts[mask.to_numpy()].sum()) / int(counts.sum())


def _infer_number_text(
    profile: ColumnProfile,
    n_unique: int,
    counts: pd.Series,
    sample_evidence: dict[str, int | float],
    thresholds: InferenceThresholds,
) -> ColumnTypeInference | None:
    """Recognise numbers stored as text (rule 5c); ``None`` when the values are not numbers.

    ``counts`` maps each distinct string of the (sampled) values to its count. Nothing is
    converted. Values with a leading zero are codes, never numbers; values with regional
    separators are reported as unknown, never converted or guessed.
    """
    n_non_missing = profile.n_non_missing
    distinct = pd.Series(counts.index)
    canonical = _matching(distinct, _CANONICAL_NUMBER)
    parse_ratio = _share(counts, canonical)
    unique_ratio = n_unique / n_non_missing

    if parse_ratio >= thresholds.text_parse_min_ratio:
        leading_zero_ratio = _share(counts, _matching(distinct, _LEADING_ZERO_INTEGER))
        if leading_zero_ratio > 0:
            code_role = (
                RoleHint.IDENTIFIER_CANDIDATE
                if _meets_identifier_counts(unique_ratio, n_non_missing, thresholds)
                else RoleHint.CODE_CANDIDATE
            )
            code_type = (
                InferredType.CATEGORICAL
                if _is_categorical(n_unique, unique_ratio, thresholds)
                else InferredType.TEXT
            )
            reason = Reason.create(
                ReasonCode.NUMERIC_LOOKING_LEADING_ZEROS,
                leading_zero_ratio=leading_zero_ratio,
                parse_ratio=parse_ratio,
                n_unique=n_unique,
                n_non_missing=n_non_missing,
                unique_ratio=unique_ratio,
                **sample_evidence,
            )
            return _result(profile, code_type, reason, code_role)

        has_point = bool(distinct[canonical].str.contains(".", regex=False).any())
        inferred_type, role, numeric_reason = _classify_numeric(
            n_unique=n_unique,
            n_non_missing=n_non_missing,
            is_integer=not has_point,
            is_binary=n_unique == 2 and set(distinct) == {"0", "1"},
            thresholds=thresholds,
        )
        text_reason = Reason.create(
            ReasonCode.NUMERIC_TEXT, parse_ratio=parse_ratio, **sample_evidence
        )
        return ColumnTypeInference(
            name=profile.name,
            inferred_type=inferred_type,
            role_hint=role,
            reasons=(text_reason, numeric_reason),
        )

    locale_ratio = _share(counts, _matching(distinct, *_LOCALE_NUMBERS))
    # parse_ratio is below the threshold here, so reaching it implies some regional value.
    if parse_ratio + locale_ratio >= thresholds.text_parse_min_ratio:
        reason = Reason.create(
            ReasonCode.NUMERIC_LOCALE_FORMAT,
            parse_ratio=parse_ratio,
            locale_ratio=locale_ratio,
            n_non_missing=n_non_missing,
            **sample_evidence,
        )
        return _result(
            profile, InferredType.UNKNOWN, reason, warnings=(LOCALE_NUMBER_WARNING,)
        )
    return None


def _infer_text_or_object(
    series: pd.Series, profile: ColumnProfile, n_unique: int, thresholds: InferenceThresholds
) -> ColumnTypeInference:
    non_null = series.dropna()
    n_non_missing = profile.n_non_missing

    value_kind = pdt.infer_dtype(non_null, skipna=True)
    if value_kind == "boolean":
        reason = Reason.create(ReasonCode.OBJECT_BOOL_VALUES, n_non_missing=n_non_missing)
        return _result(profile, InferredType.BOOLEAN, reason)
    if value_kind != "string":
        type_name, count = _dominant_type(non_null)
        reason = Reason.create(
            ReasonCode.NON_TEXT_OBJECTS,
            dominant_type=type_name,
            dominant_share=count / n_non_missing,
            n_non_missing=n_non_missing,
        )
        return _result(profile, InferredType.UNKNOWN, reason)

    if n_unique == 2:
        vocabulary = _boolean_vocabulary(list(non_null.unique()))
        if vocabulary is not None:
            reason = Reason.create(
                ReasonCode.BOOLEAN_TEXT_VOCABULARY,
                vocabulary=vocabulary,
                n_non_missing=n_non_missing,
            )
            return _result(profile, InferredType.BOOLEAN, reason)

    # With at most two distinct values the counts are exact; otherwise use the sample.
    exact = n_unique <= 2
    sample = non_null if exact else _sample_values(non_null, thresholds.sample_size)
    sample_evidence: dict[str, int | float] = (
        {"sample_size": len(sample), "population": len(non_null)}
        if len(non_null) > len(sample)
        else {}
    )

    counts = sample.value_counts()
    numbers = _infer_number_text(profile, n_unique, counts, sample_evidence, thresholds)
    if numbers is not None:
        return numbers

    unique_ratio = n_unique / n_non_missing
    if _meets_identifier_counts(unique_ratio, n_non_missing, thresholds):
        whitespace_ratio = float(sample.str.contains(r"\s", regex=True).mean())
        if whitespace_ratio == 0:
            reason = Reason.create(
                ReasonCode.TEXT_IDENTIFIER_LIKE,
                n_unique=n_unique,
                n_non_missing=n_non_missing,
                unique_ratio=unique_ratio,
                whitespace_ratio=whitespace_ratio,
                **sample_evidence,
            )
            return _result(profile, InferredType.TEXT, reason, RoleHint.IDENTIFIER_CANDIDATE)

    evidence_counts = {
        "n_unique": n_unique,
        "n_non_missing": n_non_missing,
        "unique_ratio": unique_ratio,
    }
    if _is_categorical(n_unique, unique_ratio, thresholds):
        reason = Reason.create(ReasonCode.FEW_REPEATED_VALUES, **evidence_counts)
        return _result(profile, InferredType.CATEGORICAL, reason)
    reason = Reason.create(ReasonCode.FREE_TEXT_FALLBACK, **evidence_counts)
    return _result(profile, InferredType.TEXT, reason)


def _infer_automatic(
    series: pd.Series, profile: ColumnProfile, thresholds: InferenceThresholds
) -> ColumnTypeInference:
    if profile.n_non_missing == 0:
        reason = Reason.create(ReasonCode.ALL_MISSING, n_rows=profile.n_rows)
        return _result(profile, InferredType.UNKNOWN, reason)
    n_unique = profile.n_unique
    if n_unique is None:
        reason = Reason.create(ReasonCode.UNSUPPORTED_VALUES, family=profile.family.value)
        return _result(profile, InferredType.UNKNOWN, reason)
    if profile.family in _DTYPE_RULES:
        inferred_type, code = _DTYPE_RULES[profile.family]
        reason = Reason.create(code, family=profile.family.value)
        return _result(profile, inferred_type, reason)
    if profile.family is DtypeFamily.NUMERIC:
        return _infer_numeric(series, profile, n_unique, thresholds)
    return _infer_text_or_object(series, profile, n_unique, thresholds)


def _parse_override(value: InferredType | str, column: str) -> InferredType:
    try:
        return InferredType(value)
    except ValueError:
        valid = ", ".join(member.value for member in InferredType)
        raise ValueError(
            f"invalid inferred type {value!r} for column {column!r}: valid values are {valid}"
        ) from None


def infer_column_type(
    series: pd.Series,
    profile: ColumnProfile,
    *,
    thresholds: InferenceThresholds | None = None,
    override: InferredType | str | None = None,
) -> ColumnTypeInference:
    """Infer the statistical type of one column from its values and its profile.

    ``profile`` must be the profile of ``series``; only its length is checked. Nothing
    is modified or converted. With ``override``, the automatic rules still run: the
    result carries the imposed type, ``overridden=True``, no role hint, the single reason
    ``USER_OVERRIDE`` (with the automatic type as evidence) and the automatic warnings.

    Raises:
        ValueError: ``override`` is not a valid type, or ``series`` and ``profile``
            have different lengths.
    """
    thresholds = thresholds if thresholds is not None else InferenceThresholds()
    imposed = None if override is None else _parse_override(override, profile.name)
    if len(series) != profile.n_rows:
        raise ValueError(
            f"series has {len(series)} rows but the profile of {profile.name!r} has "
            f"{profile.n_rows}"
        )
    automatic = _infer_automatic(series, profile, thresholds)
    if imposed is None:
        return automatic
    reason = Reason.create(ReasonCode.USER_OVERRIDE, automatic_type=automatic.inferred_type.value)
    return replace(
        automatic, inferred_type=imposed, role_hint=None, reasons=(reason,), overridden=True
    )


def infer_types(
    df: pd.DataFrame,
    profile: DatasetProfile,
    *,
    thresholds: InferenceThresholds | None = None,
    overrides: Mapping[str, InferredType | str] | None = None,
) -> DatasetTypeInference:
    """Infer the statistical type of every column of ``df``.

    Columns are read by position and named ``str(label)``, like in
    :func:`~datasonde.profile.profile_dataframe`. ``overrides`` maps column names to an
    imposed type (an :class:`InferredType` or its string value) and is validated before
    any computation. The input is not modified.

    Raises:
        TypeError, ValueError: ``df`` is not a valid DataFrame (see
            :func:`~datasonde.metadata.validate_dataframe`).
        ValueError: ``profile`` does not match ``df`` (row count, column count or
            names), or ``overrides`` names an unknown column or an invalid type.
    """
    df = validate_dataframe(df)
    thresholds = thresholds if thresholds is not None else InferenceThresholds()

    names = [str(label) for label in df.columns]
    profile_names = [column.name for column in profile.columns]
    if profile.metadata.n_rows != len(df):
        raise ValueError(
            f"profile has {profile.metadata.n_rows} rows but the DataFrame has {len(df)}"
        )
    if names != profile_names:
        raise ValueError(
            f"profile columns {profile_names} do not match DataFrame columns {names}"
        )

    imposed: dict[str, InferredType] = {}
    if overrides:
        unknown = [name for name in overrides if name not in names]
        if unknown:
            raise ValueError(f"overrides name unknown columns {unknown}; known columns: {names}")
        imposed = {name: _parse_override(value, name) for name, value in overrides.items()}

    columns = tuple(
        infer_column_type(
            df.iloc[:, position],
            column_profile,
            thresholds=thresholds,
            override=imposed.get(column_profile.name),
        )
        for position, column_profile in enumerate(profile.columns)
    )
    return DatasetTypeInference(columns=columns, thresholds=thresholds)
