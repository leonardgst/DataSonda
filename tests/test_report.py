"""Tests for analyze(), Report and export()."""

import dataclasses
import inspect
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import datasonde
from datasonde import Report, __version__, analyze
from datasonde.inference import infer_types
from datasonde.models import InferenceThresholds
from datasonde.profile import profile_dataframe


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "revenue_€": [1.5, None, 3.0],
            "café": ["a", None, "b"],
        }
    )


# --- analyze ------------------------------------------------------------------------------


def test_analyze_returns_report_with_the_profile(df: pd.DataFrame) -> None:
    report = analyze(df, name="demo")
    assert isinstance(report, Report)
    assert report.profile == profile_dataframe(df)
    assert report.name == "demo"


def test_name_defaults_to_none(df: pd.DataFrame) -> None:
    assert analyze(df).name is None


@pytest.mark.parametrize("bad_name", [123, b"x", ["a"]])
def test_name_must_be_str_or_none(df: pd.DataFrame, bad_name: object) -> None:
    with pytest.raises(TypeError):
        analyze(df, name=bad_name)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["customers.csv", None, [1, 2], {"a": [1]}])
def test_analyze_rejects_non_dataframe(bad: object) -> None:
    with pytest.raises(TypeError):
        analyze(bad)


def test_analyze_rejects_colliding_column_names() -> None:
    with pytest.raises(ValueError):
        analyze(pd.DataFrame({1: [1], "1": [2]}))


def test_analyze_does_not_modify_input(df: pd.DataFrame) -> None:
    before = df.copy()
    analyze(df)
    pd.testing.assert_frame_equal(df, before)


def test_report_is_frozen(df: pd.DataFrame) -> None:
    report = analyze(df)
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.name = "other"  # type: ignore[misc]


# --- export -------------------------------------------------------------------------------


def test_export_dispatches_on_extension(df: pd.DataFrame, tmp_path: Path) -> None:
    report = analyze(df, name="demo")
    html_path = report.export(tmp_path / "r.html")
    json_path = report.export(tmp_path / "r.json")
    assert html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert json.loads(json_path.read_text(encoding="utf-8"))["dataset_name"] == "demo"


@pytest.mark.parametrize("filename", ["r.HTML", "r.Html", "r.JSON"])
def test_extension_is_case_insensitive(df: pd.DataFrame, tmp_path: Path, filename: str) -> None:
    assert analyze(df).export(tmp_path / filename).exists()


@pytest.mark.parametrize("filename", ["r.csv", "r.txt", "r", "r.html.bak"])
def test_unknown_extension_raises_and_writes_nothing(
    df: pd.DataFrame, tmp_path: Path, filename: str
) -> None:
    with pytest.raises(ValueError, match=r"\.html, \.json"):
        analyze(df).export(tmp_path / filename)
    assert list(tmp_path.iterdir()) == []


def test_missing_parent_directory_is_not_created(df: pd.DataFrame, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        analyze(df).export(tmp_path / "missing" / "r.html")
    assert not (tmp_path / "missing").exists()


def test_existing_file_is_overwritten(df: pd.DataFrame, tmp_path: Path) -> None:
    target = tmp_path / "r.json"
    target.write_text("old content", encoding="utf-8")
    analyze(df).export(target)
    assert "old content" not in target.read_text(encoding="utf-8")


def test_export_returns_the_written_path_and_accepts_str(df: pd.DataFrame, tmp_path: Path) -> None:
    report = analyze(df)
    as_path = report.export(tmp_path / "a.html")
    as_str = report.export(str(tmp_path / "b.json"))
    assert as_path == tmp_path / "a.html"
    assert as_str == tmp_path / "b.json"
    assert isinstance(as_str, Path)


@pytest.mark.parametrize("filename", ["r.html", "r.json"])
def test_export_bytes(df: pd.DataFrame, tmp_path: Path, filename: str) -> None:
    report = analyze(df, name="Élan")
    first = report.export(tmp_path / filename).read_bytes()
    second = report.export(tmp_path / ("2_" + filename)).read_bytes()
    assert first == second
    assert not first.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in first
    text = first.decode("utf-8")
    for expected in ("revenue_€", "café", "Élan"):
        assert expected in text


# --- JSON ---------------------------------------------------------------------------------


def _reject_constant(value: str) -> Any:
    raise AssertionError(f"non-strict JSON constant: {value}")


def test_json_is_strict_and_has_the_four_keys(df: pd.DataFrame) -> None:
    report = analyze(df, name="demo")
    data = json.loads(report.to_json(), parse_constant=_reject_constant)
    assert set(data) == {"datasonde_version", "dataset_name", "profile", "type_inference"}
    assert data["datasonde_version"] == __version__
    assert data["profile"] == report.profile.to_dict()
    assert data["type_inference"] == report.inference.to_dict()  # type: ignore[union-attr]


def test_json_type_inference_carries_the_thresholds(df: pd.DataFrame) -> None:
    data = json.loads(analyze(df).to_json(), parse_constant=_reject_constant)
    inference = data["type_inference"]
    assert inference["thresholds"] == InferenceThresholds().to_dict()
    assert [c["name"] for c in inference["columns"]] == ["id", "revenue_€", "café"]
    assert all(c["reasons"] for c in inference["columns"])


def test_json_null_name_and_zero_rows_stay_strict() -> None:
    empty = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    data = json.loads(analyze(empty).to_json(), parse_constant=_reject_constant)
    assert data["dataset_name"] is None
    assert data["profile"]["columns"][0]["missing_rate"] is None


def test_to_json_indent(df: pd.DataFrame) -> None:
    report = analyze(df)
    assert "\n" not in report.to_json(indent=None)
    assert "\n" in report.to_json()


def test_no_cell_value_in_json_or_html() -> None:
    report = analyze(pd.DataFrame({"a": ["SECRET_VALUE_123", "x"]}))
    assert "SECRET_VALUE_123" not in report.to_json()
    assert "SECRET_VALUE_123" not in report.to_html()


def test_no_cell_value_with_type_inference_of_every_kind() -> None:
    frame = pd.DataFrame(
        {
            "ids": [f"SECRET_VALUE_{i}" for i in range(30)],
            "mixed": [f"SECRET_VALUE_{i}" if i % 2 else i for i in range(30)],
            "few": [f"SECRET_VALUE_{i % 3}" for i in range(30)],
            "vocab": ["SECRET_VALUE_A", "SECRET_VALUE_B"] * 15,
            "free": [f"SECRET_VALUE {i}" for i in range(30)],
            "lists": [[f"SECRET_VALUE_{i}"] for i in range(30)],
        }
    )
    report = analyze(frame, name="d")
    assert "SECRET_VALUE" not in report.to_json()
    assert "SECRET_VALUE" not in report.to_html()


# --- Type inference in the report ---------------------------------------------------------


def test_analyze_computes_an_inference_consistent_with_the_profile(df: pd.DataFrame) -> None:
    report = analyze(df)
    assert report.inference is not None
    assert [c.name for c in report.inference.columns] == [c.name for c in report.profile.columns]
    assert report.inference == infer_types(df, report.profile)
    assert report.inference.thresholds == InferenceThresholds()


def test_analyze_signature_is_unchanged() -> None:
    parameters = inspect.signature(analyze).parameters
    assert list(parameters) == ["data", "name"]
    assert parameters["name"].kind is inspect.Parameter.KEYWORD_ONLY


def test_report_without_inference_stays_valid(df: pd.DataFrame) -> None:
    report = Report(profile=profile_dataframe(df), name="d")
    assert report.inference is None
    assert report.to_dict()["type_inference"] is None
    assert "(inferred)" not in report.to_html()
    json.loads(report.to_json(), parse_constant=_reject_constant)


def test_html_report_carries_the_inferred_columns(df: pd.DataFrame) -> None:
    page = analyze(df).to_html()
    for header in ("Type (inferred)", "Role hint (inferred)", "Reasons (inferred)"):
        assert header in page


def test_inference_report_is_deterministic(df: pd.DataFrame) -> None:
    assert analyze(df, name="d").to_html() == analyze(df, name="d").to_html()
    assert analyze(df, name="d").to_json() == analyze(df, name="d").to_json()


# --- Public API ---------------------------------------------------------------------------


def test_public_api() -> None:
    assert set(datasonde.__all__) == {"analyze", "Report", "__version__"}
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0.dev0"
