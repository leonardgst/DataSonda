"""Tests for the HTML renderer. Never compare the rendered HTML exactly."""

import json
from html.parser import HTMLParser
from typing import Any

import pandas as pd
import pytest

from datasonde.html_report import (
    INFERRED_NOTE,
    LIMITS_HEADING,
    WARNINGS_HEADING,
    bar_width,
    format_bytes,
    format_evidence,
    format_percent,
    render_html,
)
from datasonde.inference import infer_types
from datasonde.profile import profile_dataframe

VERSION = "9.9.9-test"


class PageParser(HTMLParser):
    """Collect table rows, ``h2`` headings and every text node of a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.headings: list[str] = []
        self.texts: list[str] = []
        self._cell: list[str] | None = None
        self._heading: list[str] | None = None
        self._row: list[list[str]] | None = None
        self._in_tbody = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "h2":
            self._heading = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "tbody":
            self._in_tbody = False
        elif tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(["".join(cell) for cell in self._row])
            self._row = None
        elif tag == "h2" and self._heading is not None:
            self.headings.append("".join(self._heading))
            self._heading = None

    def handle_data(self, data: str) -> None:
        self.texts.append(data)
        if self._cell is not None:
            self._cell.append(data)
        if self._heading is not None:
            self._heading.append(data)


def parse(page: str) -> PageParser:
    parser = PageParser()
    parser.feed(page)
    parser.close()
    return parser


def render(df: pd.DataFrame, name: str | None = None) -> str:
    return render_html(profile_dataframe(df), name=name, version=VERSION)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "score": [1.5, None, 3.0, None],
            "label": ["a", "b", None, "a"],
        }
    )


# --- Nominal ------------------------------------------------------------------------------


def test_nominal_page_structure(sample_df: pd.DataFrame) -> None:
    page = render(sample_df, name="my_data")
    parsed = parse(page)
    assert page.startswith("<!DOCTYPE html>")
    assert '<meta charset="utf-8">' in page
    assert '<html lang="en">' in page
    assert len(parsed.rows) == 3
    assert [row[0] for row in parsed.rows] == ["id", "score", "label"]
    assert LIMITS_HEADING in parsed.headings
    assert "my_data" in [text.strip() for text in parsed.texts]
    assert VERSION in page


def test_row_cells_are_facts(sample_df: pd.DataFrame) -> None:
    rows = {row[0]: row for row in parse(render(sample_df)).rows}
    assert rows["score"][1] == "numeric"
    assert rows["score"][4] == "2 (50.0%)"
    assert rows["score"][5] == "2"
    assert rows["id"][6] == "-"


def test_no_name_means_no_dataset_name_element(sample_df: pd.DataFrame) -> None:
    assert '<p class="dataset-name">' not in render(sample_df)


# --- Security ------------------------------------------------------------------------------

HOSTILE = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "a&b",
    "it's",
]


def test_hostile_names_are_escaped() -> None:
    df = pd.DataFrame({hostile: [1, 2] for hostile in HOSTILE[:1]})
    for hostile in HOSTILE[1:]:
        df[hostile] = [3, 4]
    dataset_name = '<b onclick="x">it\'s & "q"</b>'
    page = render(df, name=dataset_name)
    parsed = parse(page)

    assert "<script>alert(1)</script>" not in page
    assert "<img src=x" not in page
    assert '"><img' not in page
    assert "a&b" not in page
    assert "it's" not in page
    assert "<b onclick" not in page
    assert [row[0] for row in parsed.rows] == HOSTILE
    assert dataset_name in [text.strip() for text in parsed.texts]


def test_warning_text_is_escaped() -> None:
    df = pd.DataFrame({"<i>x</i>": [[1], [2]]})
    page = render(df)
    assert "<i>x</i>" not in page
    assert "unhashable values" in page


def test_no_script_and_no_external_url(sample_df: pd.DataFrame) -> None:
    page = render(sample_df, name="d")
    assert "<script" not in page.lower()
    assert "http://" not in page
    assert "https://" not in page
    assert "Content-Security-Policy" in page


def test_no_cell_value_is_rendered() -> None:
    df = pd.DataFrame({"a": ["SECRET_VALUE_123", "x"], "b": [1, 2]})
    assert "SECRET_VALUE_123" not in render(df)
    assert "SECRET_VALUE_123" not in json.dumps(profile_dataframe(df).to_dict())


# --- Formatting ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1024**2, "1.0 MiB"),
        (5 * 1024**2, "5.0 MiB"),
        (1024**3, "1.0 GiB"),
    ],
)
def test_format_bytes(n: int, expected: str) -> None:
    assert format_bytes(n) == expected


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (None, "n/a"),
        (0, "0.0%"),
        (1, "100.0%"),
        (0.5, "50.0%"),
        (0.1234, "12.3%"),
        (0.00001, "<0.1%"),
        (0.0004, "<0.1%"),
        (0.001, "0.1%"),
        (0.99999, ">99.9%"),
        (0.9996, ">99.9%"),
    ],
)
def test_format_percent(rate: float | None, expected: str) -> None:
    assert format_percent(rate) == expected


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (None, None),
        (0, 0.0),
        (0.00001, 1.0),
        (0.5, 50.0),
        (1, 100.0),
        (1.5, 100.0),
        (-1, 0.0),
    ],
)
def test_bar_width_is_bounded(rate: float | None, expected: float | None) -> None:
    assert bar_width(rate) == expected


# --- Edge cases ---------------------------------------------------------------------------


def test_zero_rows_has_no_rate_and_no_bar() -> None:
    df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    page = render(df)
    assert parse(page).rows[0][4] == "0 (n/a)"
    assert '<span class="bar"' not in page


def test_single_column() -> None:
    assert len(parse(render(pd.DataFrame({"only": [1, 2]}))).rows) == 1


def test_warnings_section_only_when_there_are_warnings() -> None:
    with_warning = pd.DataFrame({"tags": [[1], [2]]})
    without = pd.DataFrame({"a": [1, 2]})
    assert WARNINGS_HEADING in parse(render(with_warning)).headings
    assert WARNINGS_HEADING not in parse(render(without)).headings


def test_two_hundred_columns() -> None:
    df = pd.DataFrame({f"c{i}": [i] for i in range(200)})
    assert len(parse(render(df)).rows) == 200


def test_bar_is_decorative_and_text_carries_the_value(sample_df: pd.DataFrame) -> None:
    page = render(sample_df)
    assert 'class="bar" aria-hidden="true"' in page
    assert "<caption>" in page
    assert 'scope="col"' in page


# --- Type inference columns ---------------------------------------------------------------


def render_inferred(
    df: pd.DataFrame, name: str | None = None, overrides: dict[str, str] | None = None
) -> str:
    profile = profile_dataframe(df)
    inference = infer_types(df, profile, overrides=overrides)
    return render_html(profile, name=name, version=VERSION, inference=inference)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "none"),
        (True, "true"),
        (False, "false"),
        (1, "1"),
        (1.0, "1"),
        (0.5, "0.5"),
        (0.92734, "0.9273"),
        (1 / 3, "0.3333"),
        ("dmy_slash", "dmy_slash"),
    ],
)
def test_format_evidence(value: Any, expected: str) -> None:
    assert format_evidence(value) == expected


def test_inferred_columns_are_added_after_the_facts(sample_df: pd.DataFrame) -> None:
    plain = parse(render(sample_df)).rows
    inferred = parse(render_inferred(sample_df)).rows
    assert all(len(row) == 7 for row in plain)
    assert all(len(row) == 10 for row in inferred)
    assert [row[:7] for row in inferred] == plain  # the measured facts do not move


def test_inferred_cells_show_type_role_and_numbers() -> None:
    df = pd.DataFrame({"id": range(30), "score": [i * 1.5 for i in range(30)]})
    rows = {row[0]: row for row in parse(render_inferred(df)).rows}
    assert rows["id"][7:9] == ["numeric_discrete", "identifier_candidate"]
    assert "integer_unique_identifier" in rows["id"][9]
    assert "unique_ratio=1" in rows["id"][9]
    assert rows["score"][7:9] == ["numeric_continuous", "-"]


def test_inferred_note_and_headers_only_with_inference(sample_df: pd.DataFrame) -> None:
    with_inference = render_inferred(sample_df)
    without = render(sample_df)
    assert INFERRED_NOTE in [t.strip() for t in parse(with_inference).texts]
    assert "(inferred)" not in without
    assert "Type (inferred)" in with_inference


def test_inference_warnings_join_the_warnings_section_with_escaped_names() -> None:
    hostile = "<b>1,5</b>"
    df = pd.DataFrame({hostile: ["1,5", "2,25"] * 10})
    page = render_inferred(df)
    parsed = parse(page)
    assert WARNINGS_HEADING in parsed.headings
    assert hostile not in page
    assert any(
        text.strip() == f"{hostile}: values look numeric with locale-specific separators: "
        "not converted"
        for text in parsed.texts
    )


def test_no_warnings_section_when_neither_profile_nor_inference_warns(
    sample_df: pd.DataFrame,
) -> None:
    assert WARNINGS_HEADING not in parse(render_inferred(sample_df)).headings


def test_limits_mention_inference_only_when_it_is_shown(sample_df: pd.DataFrame) -> None:
    without = " ".join(parse(render(sample_df)).texts)
    with_inference = " ".join(parse(render_inferred(sample_df)).texts)
    assert "no type or role inference" not in without
    assert "heuristic suggestions" not in without
    assert "heuristic suggestions" in with_inference
    assert "cannot be told apart from real measurements" in with_inference
    assert "never guessed" in with_inference
    assert "not flagged yet" in with_inference
    assert "no type or role inference" not in with_inference
    assert "no quality alerts" in with_inference.lower()


def test_user_override_is_marked() -> None:
    df = pd.DataFrame({"code": range(30)})
    rows = parse(render_inferred(df, overrides={"code": "categorical"})).rows
    assert rows[0][7] == "categorical (user override)"
    assert "user_override" in rows[0][9]


def test_evidence_is_escaped_exactly_once() -> None:
    # A Python type name is one of the few free strings allowed in evidence.
    odd = type("A&B<img src=x>", (), {})
    df = pd.DataFrame({"objects": [odd(), odd(), odd()]})
    page = render_inferred(df)
    assert "A&amp;B&lt;img src=x&gt;" in page
    assert "&amp;amp;" not in page
    assert "<img src=x>" not in page
    cell = parse(page).rows[0][9]
    assert "dominant_type=A&B<img src=x>" in cell  # read back exactly, no double escaping


def test_inference_page_is_safe_and_deterministic() -> None:
    df = pd.DataFrame(
        {
            "ids": [f"SECRET_VALUE_{i}" for i in range(30)],
            "tags": [[f"SECRET_VALUE_{i}"] for i in range(30)],
            "mixed": [f"SECRET_VALUE_{i}" if i % 2 else i for i in range(30)],
        }
    )
    page = render_inferred(df, name="d")
    assert "SECRET_VALUE" not in page
    assert "<script" not in page.lower()
    assert "http://" not in page
    assert "https://" not in page
    assert page == render_inferred(df, name="d")


def test_inference_with_zero_rows_and_many_columns() -> None:
    empty = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    assert "all_missing" in parse(render_inferred(empty)).rows[0][9]
    wide = pd.DataFrame({f"c{i}": [i] for i in range(200)})
    assert len(parse(render_inferred(wide)).rows) == 200


# --- Determinism --------------------------------------------------------------------------


def test_same_profile_gives_identical_string(sample_df: pd.DataFrame) -> None:
    profile = profile_dataframe(sample_df)
    first = render_html(profile, name="d", version=VERSION)
    second = render_html(profile, name="d", version=VERSION)
    assert first == second
