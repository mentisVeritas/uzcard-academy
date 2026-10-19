"""Database exploration for customer segments (seg_* tables)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db import get_engine

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)


def q(engine, sql: str) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine)


def _jsonable(o):
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(x) for x in o]
    return str(o)


def main() -> None:
    engine = get_engine()
    results: dict = {}

    tables = q(
        engine,
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tablename LIKE 'seg\\_%' ESCAPE '\\'
        ORDER BY 1
        """,
    )
    results["tables"] = tables["tablename"].tolist()

    rows = q(
        engine,
        """
        SELECT c.relname AS table_name, c.reltuples::bigint AS approx_rows
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname LIKE 'seg\\_%' ESCAPE '\\'
          AND c.relkind = 'r'
        ORDER BY c.reltuples DESC
        """,
    )
    results["row_counts"] = rows.set_index("table_name")["approx_rows"].to_dict()

    results["customers"] = q(
        engine,
        """
        SELECT MIN(signup_date) AS min_signup, MAX(signup_date) AS max_signup,
               COUNT(*) AS n_clients, COUNT(DISTINCT tariff_code) AS n_tariffs
        FROM seg_customers
        """,
    ).iloc[0].to_dict()

    results["tariff"] = q(
        engine,
        "SELECT * FROM seg_tariff_current",
    ).to_dict(orient="records")

    results["transactions"] = q(
        engine,
        """
        SELECT MIN(txn_ts)::date AS min_ts, MAX(txn_ts)::date AS max_ts, COUNT(*) AS n
        FROM seg_transactions
        """,
    ).iloc[0].to_dict()

    archive = q(
        engine,
        """
        SELECT
            (SELECT COUNT(*) FROM seg_transactions_archive) AS archive_rows,
            (SELECT MIN(txn_ts)::date FROM seg_transactions_archive) AS archive_min,
            (SELECT MAX(txn_ts)::date FROM seg_transactions_archive) AS archive_max
        """,
    ).iloc[0].to_dict()
    results["archive"] = archive
    results["archive_overlap"] = int(
        q(
            engine,
            """
            SELECT COUNT(*) AS n
            FROM seg_transactions_archive a
            WHERE EXISTS (
                SELECT 1 FROM seg_transactions t WHERE t.txn_id = a.txn_id
            )
            """,
        ).iloc[0]["n"]
    )

    results["clients_no_txn"] = int(
        q(
            engine,
            """
            SELECT COUNT(*) AS n FROM seg_customers c
            WHERE NOT EXISTS (
                SELECT 1 FROM seg_transactions t WHERE t.customer_id = c.customer_id
            )
            """,
        ).iloc[0]["n"]
    )

    results["signup_after_cutoff"] = int(
        q(
            engine,
            """
            SELECT COUNT(*) AS n FROM seg_customers
            WHERE signup_date > DATE '2025-09-01'
            """,
        ).iloc[0]["n"]
    )

    results["tenure_days_p"] = q(
        engine,
        """
        SELECT percentile_cont(ARRAY[0.1,0.25,0.5,0.75,0.9]) WITHIN GROUP (
            ORDER BY DATE '2025-12-31' - signup_date
        ) AS p FROM seg_customers
        """,
    ).iloc[0]["p"]

    results["channel_mix"] = q(
        engine,
        """
        SELECT channel, COUNT(*) AS n,
               ROUND(SUM(amount_uzs) FILTER (WHERE direction = 'out')) AS debit_uzs
        FROM seg_transactions
        WHERE txn_ts >= DATE '2025-06-01' AND txn_ts < DATE '2025-12-01'
        GROUP BY 1 ORDER BY n DESC
        """,
    ).to_dict(orient="records")

    results["spend_window_p"] = q(
        engine,
        """
        SELECT percentile_cont(ARRAY[0.5,0.9,0.95,0.99,0.999]) WITHIN GROUP (
            ORDER BY spend
        ) AS p
        FROM (
            SELECT customer_id, SUM(amount_uzs) AS spend
            FROM seg_transactions
            WHERE direction = 'out'
              AND txn_ts >= DATE '2025-06-01' AND txn_ts < DATE '2025-12-01'
            GROUP BY 1
        ) s
        """,
    ).iloc[0]["p"]

    results["h1_h2_spend_corr"] = q(
        engine,
        """
        WITH h1 AS (
            SELECT customer_id, SUM(amount_uzs) AS spend
            FROM seg_transactions
            WHERE direction = 'out'
              AND txn_ts >= DATE '2025-01-01' AND txn_ts < DATE '2025-07-01'
            GROUP BY 1
        ),
        h2 AS (
            SELECT customer_id, SUM(amount_uzs) AS spend
            FROM seg_transactions
            WHERE direction = 'out'
              AND txn_ts >= DATE '2025-07-01' AND txn_ts < DATE '2026-01-01'
            GROUP BY 1
        )
        SELECT CORR(h1.spend, h2.spend) AS corr,
               COUNT(*) AS n_both
        FROM h1 JOIN h2 USING (customer_id)
        """,
    ).iloc[0].to_dict()

    results["revenue_2025"] = q(
        engine,
        """
        SELECT COUNT(*) AS clients,
               SUM(cust_rev) AS total_net_rev,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY cust_rev) AS median_rev,
               percentile_cont(0.9) WITHIN GROUP (ORDER BY cust_rev) AS p90_rev,
               MAX(cust_rev) AS max_rev
        FROM (
            SELECT customer_id, SUM(net_revenue_uzs) AS cust_rev
            FROM seg_revenue_monthly
            WHERE month_start >= DATE '2025-01-01'
              AND month_start < DATE '2026-01-01'
            GROUP BY 1
        ) x
        """,
    ).iloc[0].to_dict()

    results["products"] = q(
        engine,
        """
        SELECT COUNT(DISTINCT customer_id) AS clients_with_product,
               COUNT(*) AS rows
        FROM seg_products
        """,
    ).iloc[0].to_dict()

    crm = q(
        engine,
        """
        SELECT crm_segment, COUNT(*) AS n,
               ROUND(AVG(turnover_total)) AS avg_turnover,
               ROUND(STDDEV(turnover_total)) AS sd_turnover
        FROM seg_customers_360
        GROUP BY 1 ORDER BY 1
        """,
    )
    results["crm_segments"] = crm.to_dict(orient="records")

    out = DATA / "exploration_results.json"
    out.write_text(json.dumps(_jsonable(results), ensure_ascii=False, indent=2))
    print(f"Wrote {out}")
    print(f"Tables: {len(results['tables'])}")
    print(f"Clients: {results['customers']['n_clients']}")
    print(f"No txn: {results['clients_no_txn']}")
    print(f"Archive overlap: {results['archive_overlap']}")
    print(f"H1/H2 spend corr: {results['h1_h2_spend_corr']}")


if __name__ == "__main__":
    main()
