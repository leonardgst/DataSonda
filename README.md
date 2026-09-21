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

For each column: its technical family (numeric, boolean, datetime, categorical,
text_or_object, other), pandas dtype, memory, missing values (count and share), distinct
values and warnings. The HTML report is a single standalone page (no script, no external
resource) and shows facts only. No raw cell value is ever written to the report.

### Limits

- Families come from the pandas dtype: there is no type or role inference yet (a
  boolean column containing nulls appears as `text_or_object`).
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
