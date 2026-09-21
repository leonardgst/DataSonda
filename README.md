# DataSonda

DataSonda is a modular Python toolkit for automated data profiling, quality
assessment, exploratory analysis and report generation. The Python package is
named `datasonde`.

> Status: early development (V0.1 in progress). Not yet published on PyPI.

## Installation (development)

```bash
git clone https://github.com/leonardgst/DataSonda.git
cd DataSonda
uv sync
```

## Usage

```python
import pandas as pd

from datasonde import analyze

df = pd.DataFrame(
    {
        "customer_id": [1, 2, 3, 4],
        "age": [34, None, 51, 29],
        "country": ["FR", "DE", None, "FR"],
    }
)

report = analyze(df, name="customers")
report.export("customers_report.html")
report.export("customers_report.json")
```

The format of `export` follows the file extension (`.html` or `.json`). An existing
file is overwritten, and the target folder must already exist.

Loading files (CSV, Parquet, ...) is planned but not available yet: `analyze` only
accepts a pandas DataFrame. The API and the JSON format are provisional while the
version is `0.1.0.dev0`.

### What the report contains

For each column, two kinds of information, kept apart:

- **Measured facts**: technical family (numeric, boolean, datetime, categorical,
  text_or_object, other), pandas dtype, memory, missing values (count and share),
  distinct values and warnings.
- **Inferred interpretation** (columns marked "(inferred)" in the HTML report, and the
  `type_inference` key of the JSON): a statistical type (`numeric_continuous`,
  `numeric_discrete`, `categorical`, `boolean`, `datetime`, `text` or `unknown`), an
  optional role hint (`identifier_candidate`, `code_candidate`), and the reasons with
  the numbers that triggered each rule. It also detects booleans stored as text
  (yes/no), numbers stored as text and dates stored as text. Nothing is converted, and
  `unknown` is a legitimate answer.

The HTML report is a single standalone page (no script, no external resource). No raw
cell value is ever written to the report.

### Limits

- Inferred types and role hints are heuristic suggestions from documented rules and
  thresholds (see `src/datasonde/inference.py`), computed on a deterministic sample of
  bounded size. They are not facts.
- Numeric codes stored as integers cannot be told apart from real measurements. A manual
  override exists at function level (`datasonde.inference.infer_types`), not yet in
  `analyze`.
- Date formats are never guessed: when day and month cannot be told apart, the report
  shows a warning instead of a choice. Only day-first/month-first and ISO-like formats
  from a closed list are recognised, within the years 1677 to 2262; two-digit years,
  month names and time zones are not. Numbers with regional separators (`1 234,5`) are
  reported as `unknown`, never converted.
- Constant and nearly empty columns are not flagged yet.
- "Missing" means a pandas null only: empty strings, `"N/A"` and other sentinels are
  not counted.
- No quality alerts, univariate statistics or charts yet.

## Demo

```bash
uv run python examples/demo.py
```

This profiles a synthetic, deterministic 500-row DataFrame (no real data) and writes
`customers_demo.html` and `customers_demo.json` to `examples/output/`, which is ignored
by Git.

## Development

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## License

MIT — see [LICENSE](LICENSE).
