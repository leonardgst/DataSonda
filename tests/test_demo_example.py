"""Smoke test of examples/demo.py (loaded by path, no sys.path tweaking)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

from datasonde import analyze
from datasonde.models import DtypeFamily

DEMO_PATH = Path(__file__).resolve().parent.parent / "examples" / "demo.py"


@pytest.fixture(scope="module")
def demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("datasonde_demo", DEMO_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_dataframe_is_deterministic(demo: ModuleType) -> None:
    pd.testing.assert_frame_equal(demo.build_demo_dataframe(), demo.build_demo_dataframe())


def test_demo_dataframe_shape_and_profile(demo: ModuleType) -> None:
    df = demo.build_demo_dataframe()
    assert len(df) == 500
    profile = {c.name: c for c in analyze(df).profile.columns}

    assert profile["customer_id"].n_unique == 500
    assert profile["source"].n_unique == 1

    assert profile["tags"].n_unique is None
    assert profile["tags"].warnings

    notes_rate = profile["notes"].missing_rate
    assert notes_rate is not None
    assert notes_rate > 0.6

    families = {column.family for column in profile.values()}
    assert {
        DtypeFamily.NUMERIC,
        DtypeFamily.BOOLEAN,
        DtypeFamily.DATETIME,
        DtypeFamily.CATEGORICAL,
        DtypeFamily.TEXT_OR_OBJECT,
    } <= families


EXPECTED_INFERENCE = {
    # column: (inferred type, role hint)
    "customer_id": ("numeric_discrete", "identifier_candidate"),
    "age": ("numeric_continuous", None),
    "country": ("categorical", None),
    "signup_date": ("datetime", None),
    "is_premium": ("boolean", None),
    "notes": ("text", None),
    "source": ("categorical", None),
    "tags": ("unknown", None),
    "revenue_€": ("numeric_continuous", None),
    "zip_code": ("categorical", "code_candidate"),
    "newsletter": ("boolean", None),
    "last_login": ("datetime", None),
    "opt_in": ("boolean", None),
}


def test_demo_dataframe_has_the_expected_columns_in_order(demo: ModuleType) -> None:
    assert list(demo.build_demo_dataframe().columns) == list(EXPECTED_INFERENCE)


def test_demo_type_inference(demo: ModuleType) -> None:
    inference = analyze(demo.build_demo_dataframe()).inference
    assert inference is not None
    actual = {
        c.name: (c.inferred_type.value, None if c.role_hint is None else c.role_hint.value)
        for c in inference.columns
    }
    assert actual == EXPECTED_INFERENCE


def test_demo_dates_and_codes_are_not_guessed(demo: ModuleType) -> None:
    inference = analyze(demo.build_demo_dataframe()).inference
    assert inference is not None
    by_name = {c.name: c for c in inference.columns}

    last_login = by_name["last_login"]
    assert last_login.warnings == ()
    assert dict(last_login.reasons[0].evidence)["format"] == "dmy_slash"

    zip_reason = by_name["zip_code"].reasons[0]
    assert zip_reason.code.value == "numeric_looking_leading_zeros"
    assert dict(zip_reason.evidence)["leading_zero_ratio"] > 0

    demo_frame = demo.build_demo_dataframe()
    assert demo_frame["zip_code"].str.startswith("0").any()  # codes are kept as text


def test_main_writes_both_reports(demo: ModuleType, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    demo.main(output_dir)
    html_files = list(output_dir.glob("*.html"))
    json_files = list(output_dir.glob("*.json"))
    assert len(html_files) == 1
    assert len(json_files) == 1
    assert "revenue_€" in html_files[0].read_text(encoding="utf-8")
