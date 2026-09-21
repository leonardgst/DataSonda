"""End-to-end demo: a synthetic DataFrame -> analyze -> HTML and JSON report.

Run from the repository root with ``uv run python examples/demo.py``. The data is fully
synthetic and deterministic: no real or personal data is involved.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from datasonde import analyze

N_ROWS = 500
SEED = 42
COUNTRIES = ["FR", "DE", "ES", "IT", "BE"]
TAGS = ["newsletter", "promo", "vip", "trial", "referral"]


def build_demo_dataframe() -> pd.DataFrame:
    """Build the 500-row synthetic customers DataFrame (deterministic, seed 42)."""
    rng = random.Random(SEED)
    start = datetime(2023, 1, 1)
    # 40 five-digit codes, the first nine starting with 0 (they must stay text).
    zip_codes = [f"{code:05d}" for code in range(1000, 41000, 1000)]

    def maybe_missing(value: object, rate: float) -> object:
        return None if rng.random() < rate else value

    return pd.DataFrame(
        {
            "customer_id": list(range(1000, 1000 + N_ROWS)),
            "age": [maybe_missing(rng.randint(18, 80), 0.04) for _ in range(N_ROWS)],
            "country": pd.Series(
                [rng.choice(COUNTRIES) for _ in range(N_ROWS)], dtype="category"
            ),
            "signup_date": pd.to_datetime(
                pd.Series(
                    [
                        maybe_missing(start + timedelta(days=rng.randint(0, 700)), 0.02)
                        for _ in range(N_ROWS)
                    ]
                )
            ),
            "is_premium": [rng.random() < 0.3 for _ in range(N_ROWS)],
            "notes": [maybe_missing(f"note {i}", 0.70) for i in range(N_ROWS)],
            "source": ["web"] * N_ROWS,
            "tags": [
                [rng.choice(TAGS) for _ in range(rng.randint(1, 3))] for _ in range(N_ROWS)
            ],
            "revenue_€": [
                maybe_missing(round(rng.uniform(5, 500), 2), 0.10) for _ in range(N_ROWS)
            ],
            "zip_code": [rng.choice(zip_codes) for _ in range(N_ROWS)],
            "newsletter": [rng.choice(["yes", "no"]) for _ in range(N_ROWS)],
            "last_login": [
                (datetime(2024, 1, 1) + timedelta(days=rng.randint(0, 365))).strftime("%d/%m/%Y")
                for _ in range(N_ROWS)
            ],
            "opt_in": [maybe_missing(rng.random() < 0.5, 0.05) for _ in range(N_ROWS)],
        }
    )


def main(output_dir: Path = Path("examples/output")) -> None:
    """Profile the demo DataFrame and write the HTML and JSON reports to ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report = analyze(build_demo_dataframe(), name="customers_demo")
    html_path = report.export(output_dir / "customers_demo.html")
    json_path = report.export(output_dir / "customers_demo.json")
    print(f"HTML report: {html_path.resolve()}")
    print(f"JSON report: {json_path.resolve()}")


if __name__ == "__main__":
    main()
