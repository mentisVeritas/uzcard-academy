"""Download churn_* tables into data_raw/{useful,junk,leakage}."""

from __future__ import annotations

import os
from pathlib import Path
import psycopg2

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data_raw"

GROUPS: dict[str, list[str]] = {
    "useful": [
        "churn_customers",
        "churn_transactions",
        "churn_cards",
        "churn_app_events",
        "churn_products",
        "churn_product_events",
        "churn_support_tickets",
        "churn_subscriptions",
        "churn_subscription_charges",
        "churn_tariff_changes",
        "churn_retention_campaigns",
    ],
    "leakage": [
        "churn_customers_360",
    ],
    "junk": [
        "churn_customers_crm_old",
        "churn_transactions_archive",
        "churn_temp",
        "churn_nps_survey",
    ],
}


def load_dotenv() -> None:
    for base in (ROOT, PROJECT):
        for name in (".env", ".env.example"):
            dotenv = base / name
            if not dotenv.exists():
                continue
            for line in dotenv.read_text().splitlines():
                line = line.strip().strip("\r")
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\r"))
            return


def connect():
    load_dotenv()
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "thomas.proxy.rlwy.net"),
        port=os.environ.get("DB_PORT", "51432"),
        dbname=os.environ.get("DB_NAME", "academy_db"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode=os.environ.get("DB_SSLMODE", "require").strip(),
    )


def download_table(cur, table: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    sql = f'COPY public."{table}" TO STDOUT WITH CSV HEADER'
    with tmp.open("w", encoding="utf-8", newline="") as f:
        cur.copy_expert(sql, f)
    tmp.replace(dest)


def main() -> None:
    conn = connect()
    conn.set_session(readonly=True, autocommit=True)
    try:
        with conn.cursor() as cur:
            for group, tables in GROUPS.items():
                for table in tables:
                    dest = RAW / group / f"{table}.csv"
                    print(f"{group}/{table} ...", flush=True)
                    download_table(cur, table, dest)
                    size_mb = dest.stat().st_size / 1_048_576
                    print(f"  -> {dest.relative_to(PROJECT)} ({size_mb:.1f} MB)", flush=True)
    finally:
        conn.close()
    print("done")


if __name__ == "__main__":
    main()
