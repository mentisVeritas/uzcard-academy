"""Download small seg_* tables to data_raw/useful/."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db import get_engine

ROOT = Path(__file__).resolve().parents[1]
USEFUL = ROOT / "data_raw" / "useful"
USEFUL.mkdir(parents=True, exist_ok=True)

SMALL_TABLES = [
    "seg_customers",
    "seg_tariff_current",
    "seg_products",
    "seg_revenue_monthly",
    "seg_balances",
]


def main() -> None:
    engine = get_engine()
    for table in SMALL_TABLES:
        df = pd.read_sql(text(f"SELECT * FROM {table}"), engine)
        path = USEFUL / f"{table}.csv"
        df.to_csv(path, index=False)
        print(f"{table}: {len(df):,} rows -> {path.name}")


if __name__ == "__main__":
    main()
