# DataSonde

DataSonde is a modular Python toolkit for automated data profiling, quality
assessment, exploratory analysis and report generation.

> Status: early development (V0.1 in progress). Not yet published on PyPI.

## Installation (development)

```bash
git clone https://github.com/<ton-compte>/datasonde.git
cd datasonde
uv sync
```

## Planned usage

```python
from datasonde import analyze

report = analyze("customers.csv")
report.export("customers_report.html")
report.export("customers_report.json")
```

## Development

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## License

MIT — see [LICENSE](LICENSE).
