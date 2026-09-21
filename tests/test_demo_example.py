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


def test_main_writes_both_reports(demo: ModuleType, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    demo.main(output_dir)
    html_files = list(output_dir.glob("*.html"))
    json_files = list(output_dir.glob("*.json"))
    assert len(html_files) == 1
    assert len(json_files) == 1
    assert "revenue_€" in html_files[0].read_text(encoding="utf-8")
