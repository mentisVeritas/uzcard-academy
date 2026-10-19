"""Full database analysis for credit scoring dataset."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
AS_OF = "2025-05-31"

DATA.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    for base in (ROOT, ROOT.parent):
        dotenv = base / ".env"
        if not dotenv.exists():
            continue
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def get_dsn() -> str:
    _load_dotenv()
    user = os.environ.get("DB_USER", "bkenesbaev")
    password = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ.get("DB_HOST", "thomas.proxy.rlwy.net")
    port = os.environ.get("DB_PORT", "51432")
    name = os.environ.get("DB_NAME", "academy_db")
    sslmode = os.environ.get("DB_SSLMODE", "require")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode={sslmode}"


def q(engine, sql: str) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine)


PAYMENT_DPD_SQL = f"""
payment_dpd AS (
    SELECT
        p.contract_id,
        c.issue_date,
        p.due_date,
        CASE
            WHEN p.paid_date IS NULL THEN
                CASE
                    WHEN p.due_date <= DATE '{AS_OF}'
                        THEN DATE '{AS_OF}' - p.due_date
                    ELSE 0
                END
            ELSE GREATEST(0, p.paid_date - p.due_date)
        END AS dpd_days
    FROM scoring_payments p
    JOIN scoring_contracts c ON p.contract_id = c.contract_id
)"""

CONTRACT_PERF_SQL = f"""
contract_perf AS (
    SELECT
        c.contract_id,
        c.application_id,
        c.client_id,
        c.issue_date,
        c.term_months,
        c.issued_amount_uzs,
        (c.issue_date + INTERVAL '12 months')::date AS perf_end_12m,
        MAX(pd.dpd_days) FILTER (
            WHERE pd.due_date <= DATE '{AS_OF}'
              AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
        ) AS max_dpd,
        COUNT(*) FILTER (
            WHERE pd.due_date <= DATE '{AS_OF}'
              AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
        ) AS installments_in_window,
        CASE
            WHEN (c.issue_date + INTERVAL '12 months')::date <= DATE '{AS_OF}'
             AND COUNT(*) FILTER (
                    WHERE pd.due_date <= DATE '{AS_OF}'
                      AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
                 ) >= 1
            THEN 1
            ELSE 0
        END AS window_closed_12m
    FROM scoring_contracts c
    LEFT JOIN payment_dpd pd ON c.contract_id = pd.contract_id
    GROUP BY 1, 2, 3, 4, 5, 6
)"""

TARGET_SQL = f"""
WITH {PAYMENT_DPD_SQL},
{CONTRACT_PERF_SQL}
SELECT
    a.application_id,
    a.client_id,
    a.decision_date,
    cp.issue_date,
    cp.contract_id,
    cp.max_dpd,
    cp.window_closed_12m,
    cp.installments_in_window,
    CASE
        WHEN COALESCE(cp.max_dpd, 0) >= 90 THEN 1
        WHEN cp.window_closed_12m = 1 AND COALESCE(cp.max_dpd, 0) < 90 THEN 0
        ELSE NULL
    END AS target_90,
    CASE
        WHEN COALESCE(cp.max_dpd, 0) >= 60 THEN 1
        WHEN cp.window_closed_12m = 1 AND COALESCE(cp.max_dpd, 0) < 60 THEN 0
        ELSE NULL
    END AS target_60,
    CASE
        WHEN COALESCE(cp.max_dpd, 0) >= 30 THEN 1
        WHEN cp.window_closed_12m = 1 AND COALESCE(cp.max_dpd, 0) < 30 THEN 0
        ELSE NULL
    END AS target_30
FROM scoring_applications a
JOIN contract_perf cp ON a.application_id = cp.application_id
WHERE a.final_decision = 'approved'
"""

BAD_BY_MONTH_SQL = f"""
WITH {PAYMENT_DPD_SQL},
{CONTRACT_PERF_SQL}
SELECT
    DATE_TRUNC('month', issue_date)::date AS issue_month,
    COUNT(*) FILTER (WHERE window_closed_12m = 1) AS n_mature,
    ROUND(
        AVG(
            CASE
                WHEN window_closed_12m = 1 AND COALESCE(max_dpd, 0) >= 90 THEN 1.0
                WHEN window_closed_12m = 1 THEN 0.0
            END
        )::numeric,
        4
    ) AS bad_rate_90,
    ROUND(
        AVG(
            CASE
                WHEN window_closed_12m = 1 AND COALESCE(max_dpd, 0) >= 30 THEN 1.0
                WHEN window_closed_12m = 1 THEN 0.0
            END
        )::numeric,
        4
    ) AS bad_rate_30
FROM contract_perf
GROUP BY 1
ORDER BY 1
"""

BAD_BY_MONTH_6M_SQL = f"""
WITH {PAYMENT_DPD_SQL},
contract_6m AS (
    SELECT
        c.contract_id,
        c.issue_date,
        MAX(pd.dpd_days) FILTER (
            WHERE pd.due_date <= DATE '{AS_OF}'
              AND pd.due_date <= (c.issue_date + INTERVAL '6 months')::date
        ) AS max_dpd_6m,
        CASE
            WHEN (c.issue_date + INTERVAL '6 months')::date <= DATE '{AS_OF}' THEN 1
            ELSE 0
        END AS window_closed_6m
    FROM scoring_contracts c
    LEFT JOIN payment_dpd pd ON c.contract_id = pd.contract_id
    GROUP BY 1, 2
)
SELECT
    DATE_TRUNC('month', issue_date)::date AS issue_month,
    COUNT(*) FILTER (WHERE window_closed_6m = 1) AS n_6m,
    ROUND(
        AVG(
            CASE
                WHEN window_closed_6m = 1 AND COALESCE(max_dpd_6m, 0) >= 90 THEN 1.0
                WHEN window_closed_6m = 1 THEN 0.0
            END
        )::numeric,
        4
    ) AS bad_rate_90_6m,
    ROUND(
        AVG(
            CASE
                WHEN window_closed_6m = 1 AND COALESCE(max_dpd_6m, 0) >= 30 THEN 1.0
                WHEN window_closed_6m = 1 THEN 0.0
            END
        )::numeric,
        4
    ) AS bad_rate_30_6m
FROM contract_6m
GROUP BY 1
ORDER BY 1
"""

BAD_BY_MONTH_6M_SQL = f"""
WITH {PAYMENT_DPD_SQL},
contract_6m AS (
    SELECT
        c.contract_id,
        c.issue_date,
        MAX(pd.dpd_days) FILTER (
            WHERE pd.due_date <= DATE '{AS_OF}'
              AND pd.due_date <= (c.issue_date + INTERVAL '6 months')::date
        ) AS max_dpd_6m,
        CASE
            WHEN (c.issue_date + INTERVAL '6 months')::date <= DATE '{AS_OF}' THEN 1
            ELSE 0
        END AS window_closed_6m
    FROM scoring_contracts c
    LEFT JOIN payment_dpd pd ON c.contract_id = pd.contract_id
    GROUP BY 1, 2
)
SELECT
    DATE_TRUNC('month', issue_date)::date AS issue_month,
    COUNT(*) FILTER (WHERE window_closed_6m = 1) AS n_6m,
    ROUND(
        AVG(
            CASE
                WHEN window_closed_6m = 1 AND COALESCE(max_dpd_6m, 0) >= 90 THEN 1.0
                WHEN window_closed_6m = 1 THEN 0.0
            END
        )::numeric,
        4
    ) AS bad_rate_90_6m,
    ROUND(
        AVG(
            CASE
                WHEN window_closed_6m = 1 AND COALESCE(max_dpd_6m, 0) >= 30 THEN 1.0
                WHEN window_closed_6m = 1 THEN 0.0
            END
        )::numeric,
        4
    ) AS bad_rate_30_6m
FROM contract_6m
GROUP BY 1
ORDER BY 1
"""

MATURE_BAD_RATE_SQL = """
ROUND(
    AVG(
        CASE
            WHEN window_closed_12m = 1 AND COALESCE(max_dpd, 0) >= {threshold} THEN 1.0
            WHEN window_closed_12m = 1 THEN 0.0
        END
    )::numeric,
    4
) AS bad{threshold}
"""


def main() -> None:
    engine = create_engine(get_dsn())
    results: dict = {}

    # --- Stage 1-2: Table inventory ---
    tables = q(
        engine,
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname='public' AND tablename LIKE 'scoring\\_%'
        ORDER BY tablename
        """,
    )["tablename"].tolist()

    table_profiles = []
    for t in tables:
        cnt = int(q(engine, f"SELECT COUNT(*) c FROM {t}")["c"][0])
        cols = q(
            engine,
            f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='{t}'
            ORDER BY ordinal_position
            """,
        )
        null_sql = ", ".join(
            f"SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS {c}_null"
            for c in cols["column_name"]
        )
        nulls = q(engine, f"SELECT {null_sql} FROM {t}").iloc[0].to_dict()
        dup_cols = [c for c in cols["column_name"] if "id" in c.lower()]
        dup_info = {}
        for c in dup_cols[:3]:
            dup_info[c] = int(
                cnt
                - q(engine, f"SELECT COUNT(DISTINCT {c}) d FROM {t}")["d"][0]
            )
        table_profiles.append(
            {
                "table": t,
                "rows": cnt,
                "columns": cols.to_dict("records"),
                "nulls": nulls,
                "duplicate_keys": dup_info,
            }
        )
    results["table_profiles"] = table_profiles

    # --- Applications ---
    results["applications_decisions"] = q(
        engine,
        """
        SELECT final_decision, COUNT(*) cnt,
               ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),2) pct
        FROM scoring_applications GROUP BY 1 ORDER BY 2 DESC
        """,
    ).to_dict("records")

    results["applications_dates"] = q(
        engine,
        """
        SELECT MIN(decision_date) min_d, MAX(decision_date) max_d,
               COUNT(DISTINCT application_id) apps,
               COUNT(DISTINCT client_id) clients,
               COUNT(*) - COUNT(DISTINCT application_id) dup_apps
        FROM scoring_applications
        """,
    ).iloc[0].to_dict()

    # --- Contracts linkage ---
    results["contracts_vs_apps"] = q(
        engine,
        """
        SELECT
          (SELECT COUNT(*) FROM scoring_applications
           WHERE final_decision='approved') approved_apps,
          (SELECT COUNT(*) FROM scoring_contracts) contracts,
          (SELECT COUNT(DISTINCT a.application_id)
           FROM scoring_applications a
           JOIN scoring_contracts c ON a.application_id=c.application_id) matched,
          (SELECT COUNT(*) FROM scoring_applications a
           WHERE final_decision='approved' AND NOT EXISTS (
             SELECT 1 FROM scoring_contracts c
             WHERE c.application_id=a.application_id)) approved_no_contract
        """,
    ).iloc[0].to_dict()

    # --- DPD analysis (12-month performance window) ---
    results["dpd_installment"] = q(
        engine,
        f"""
        WITH {PAYMENT_DPD_SQL}
        SELECT
          SUM(CASE WHEN dpd_days = 0 THEN 1 ELSE 0 END) dpd0,
          SUM(CASE WHEN dpd_days BETWEEN 1 AND 29 THEN 1 ELSE 0 END) dpd1_29,
          SUM(CASE WHEN dpd_days BETWEEN 30 AND 59 THEN 1 ELSE 0 END) dpd30_59,
          SUM(CASE WHEN dpd_days BETWEEN 60 AND 89 THEN 1 ELSE 0 END) dpd60_89,
          SUM(CASE WHEN dpd_days >= 90 THEN 1 ELSE 0 END) dpd90plus
        FROM payment_dpd
        WHERE due_date <= DATE '{AS_OF}'
          AND due_date <= (issue_date + INTERVAL '12 months')::date
        """,
    ).iloc[0].to_dict()

    results["contract_max_dpd"] = q(
        engine,
        f"""
        WITH {PAYMENT_DPD_SQL},
        {CONTRACT_PERF_SQL}
        SELECT
          SUM(CASE WHEN COALESCE(max_dpd, 0) = 0 THEN 1 ELSE 0 END) good0,
          SUM(CASE WHEN COALESCE(max_dpd, 0) BETWEEN 1 AND 29 THEN 1 ELSE 0 END) dpd1_29,
          SUM(CASE WHEN COALESCE(max_dpd, 0) BETWEEN 30 AND 59 THEN 1 ELSE 0 END) dpd30,
          SUM(CASE WHEN COALESCE(max_dpd, 0) BETWEEN 60 AND 89 THEN 1 ELSE 0 END) dpd60,
          SUM(CASE WHEN COALESCE(max_dpd, 0) >= 90 THEN 1 ELSE 0 END) dpd90,
          COUNT(*) total_contracts
        FROM contract_perf
        """,
    ).iloc[0].to_dict()

    results["bad_rates"] = q(
        engine,
        f"""
        WITH {PAYMENT_DPD_SQL},
        {CONTRACT_PERF_SQL}
        SELECT
          {MATURE_BAD_RATE_SQL.format(threshold=30)},
          {MATURE_BAD_RATE_SQL.format(threshold=60)},
          {MATURE_BAD_RATE_SQL.format(threshold=90)},
          COUNT(*) FILTER (WHERE window_closed_12m = 1) AS n_mature
        FROM contract_perf
        """,
    ).iloc[0].to_dict()

    results["immature_contracts"] = q(
        engine,
        f"""
        SELECT COUNT(*) total,
          SUM(CASE WHEN (issue_date + INTERVAL '12 months')::date
                > DATE '{AS_OF}' THEN 1 ELSE 0 END) not_mature,
          SUM(CASE WHEN (issue_date + INTERVAL '12 months')::date
                <= DATE '{AS_OF}' THEN 1 ELSE 0 END) mature
        FROM scoring_contracts
        """,
    ).iloc[0].to_dict()

    # --- Customer / card coverage ---
    results["coverage"] = q(
        engine,
        """
        SELECT
          (SELECT COUNT(*) FROM scoring_customers) customers,
          (SELECT COUNT(DISTINCT client_id) FROM scoring_applications) app_clients,
          (SELECT COUNT(DISTINCT a.client_id)
           FROM scoring_applications a
           JOIN scoring_customers c ON a.client_id=c.customer_id) apps_in_customers,
          (SELECT COUNT(DISTINCT a.client_id)
           FROM scoring_applications a
           WHERE EXISTS (
             SELECT 1 FROM scoring_card_transactions t
             WHERE t.client_id=a.client_id)) apps_with_card_txn,
          (SELECT COUNT(DISTINCT a.client_id)
           FROM scoring_applications a
           WHERE NOT EXISTS (
             SELECT 1 FROM scoring_card_transactions t
             WHERE t.client_id=a.client_id)) apps_without_card_txn
        """,
    ).iloc[0].to_dict()

    # --- Junk tables comparison ---
    results["junk_compare"] = q(
        engine,
        """
        SELECT
          (SELECT COUNT(*) FROM scoring_applications_full) apps_full,
          (SELECT COUNT(*) FROM scoring_applications
           WHERE final_decision='approved') approved,
          (SELECT COUNT(*) FROM scoring_payments) payments,
          (SELECT COUNT(*) FROM scoring_payments_backup) payments_backup,
          (SELECT COUNT(*) FROM scoring_payments p
           JOIN scoring_payments_backup b ON p.payment_id=b.payment_id) pay_overlap,
          (SELECT COUNT(*) FROM scoring_temp) temp_rows,
          (SELECT COUNT(*) FROM scoring_txn_sample) txn_sample
        """,
    ).iloc[0].to_dict()

    # --- Rejected vs approved ---
    results["reject_vs_approve"] = q(
        engine,
        """
        SELECT final_decision,
          ROUND(AVG(requested_amount_uzs)) avg_amount,
          ROUND(AVG(declared_income_uzs)) avg_income,
          ROUND(AVG(term_months),1) avg_term,
          ROUND(AVG(employment_months),1) avg_emp,
          COUNT(*) n
        FROM scoring_applications GROUP BY 1
        """,
    ).to_dict("records")

    # --- Date ranges all tables ---
    date_cols = {
        "scoring_applications": ["decision_date"],
        "scoring_contracts": ["issue_date"],
        "scoring_payments": ["due_date", "paid_date"],
        "scoring_bureau_snapshots": ["snapshot_date"],
        "scoring_bureau_inquiries": ["inquiry_date"],
        "scoring_bureau_loans": ["open_date", "close_date"],
        "scoring_card_transactions": ["txn_ts"],
        "scoring_collection_actions": ["action_date"],
        "scoring_cards": ["issue_date"],
        "scoring_customers": ["birth_date", "onboarding_date"],
    }
    date_ranges = {}
    for tbl, cols in date_cols.items():
        for c in cols:
            row = q(
                engine,
                f"SELECT MIN({c}) min_d, MAX({c}) max_d FROM {tbl}",
            ).iloc[0]
            date_ranges[f"{tbl}.{c}"] = row.to_dict()
    results["date_ranges"] = date_ranges

    # --- Build TARGET dataset ---
    target_df = q(engine, TARGET_SQL)
    target_df.to_csv(DATA / "target_dataset.csv", index=False)

    target_summary = q(
        engine,
        f"""
        WITH base AS ({TARGET_SQL})
        SELECT
          COUNT(*) total_approved_with_contract,
          SUM(CASE WHEN target_90 IS NOT NULL THEN 1 ELSE 0 END) labeled_90,
          ROUND(AVG(target_90)::numeric, 4) bad_rate_90,
          SUM(CASE WHEN target_60 IS NOT NULL THEN 1 ELSE 0 END) labeled_60,
          ROUND(AVG(target_60)::numeric, 4) bad_rate_60,
          SUM(CASE WHEN target_30 IS NOT NULL THEN 1 ELSE 0 END) labeled_30,
          ROUND(AVG(target_30)::numeric, 4) bad_rate_30,
          SUM(CASE WHEN window_closed_12m = 0 THEN 1 ELSE 0 END) immature
        FROM base
        """,
    ).iloc[0].to_dict()
    results["target_summary"] = target_summary

    bad_by_month = q(engine, BAD_BY_MONTH_SQL)
    bad_by_month.to_csv(DATA / "bad_rate_by_month.csv", index=False)
    results["bad_by_month"] = bad_by_month.to_dict("records")

    bad_by_month_6m = q(engine, BAD_BY_MONTH_6M_SQL)
    bad_by_month_6m.to_csv(DATA / "bad_rate_by_month_6m.csv", index=False)
    results["bad_by_month_6m"] = bad_by_month_6m.to_dict("records")

    bad_by_month_6m = q(engine, BAD_BY_MONTH_6M_SQL)
    bad_by_month_6m.to_csv(DATA / "bad_rate_by_month_6m.csv", index=False)
    results["bad_by_month_6m"] = bad_by_month_6m.to_dict("records")

    mature_bad_rate = """
        ROUND(
            AVG(
                CASE
                    WHEN b.window_closed_12m = 1 AND COALESCE(b.max_dpd, 0) >= 90 THEN 1.0
                    WHEN b.window_closed_12m = 1 THEN 0.0
                END
            )::numeric,
            4
        ) AS bad_rate_90
    """
    mature_count = "COUNT(*) FILTER (WHERE b.window_closed_12m = 1) AS n"

    # --- EDA slices (mature cohorts only) ---
    eda_channel = q(
        engine,
        f"""
        WITH base AS ({TARGET_SQL})
        SELECT a.channel, {mature_count}, {mature_bad_rate}
        FROM base b
        JOIN scoring_applications a ON b.application_id=a.application_id
        GROUP BY 1
        HAVING COUNT(*) FILTER (WHERE b.window_closed_12m = 1) > 0
        ORDER BY bad_rate_90 DESC NULLS LAST
        """,
    )
    eda_channel.to_csv(DATA / "eda_bad_by_channel.csv", index=False)

    eda_purpose = q(
        engine,
        f"""
        WITH base AS ({TARGET_SQL})
        SELECT a.purpose, {mature_count}, {mature_bad_rate}
        FROM base b
        JOIN scoring_applications a ON b.application_id=a.application_id
        GROUP BY 1
        HAVING COUNT(*) FILTER (WHERE b.window_closed_12m = 1) > 0
        ORDER BY bad_rate_90 DESC NULLS LAST
        """,
    )
    eda_purpose.to_csv(DATA / "eda_bad_by_purpose.csv", index=False)

    eda_amount = q(
        engine,
        f"""
        WITH base AS ({TARGET_SQL})
        SELECT
          CASE
            WHEN a.requested_amount_uzs < 5000000 THEN '<5M'
            WHEN a.requested_amount_uzs < 10000000 THEN '5-10M'
            WHEN a.requested_amount_uzs < 20000000 THEN '10-20M'
            ELSE '20M+'
          END AS amount_band,
          {mature_count}, {mature_bad_rate}
        FROM base b
        JOIN scoring_applications a ON b.application_id=a.application_id
        GROUP BY 1
        HAVING COUNT(*) FILTER (WHERE b.window_closed_12m = 1) > 0
        ORDER BY 1
        """,
    )
    eda_amount.to_csv(DATA / "eda_bad_by_amount.csv", index=False)

    bureau_asof_cte = """
    bureau_asof AS (
      SELECT DISTINCT ON (a.application_id)
        a.application_id,
        s.bureau_score
      FROM scoring_applications a
      JOIN scoring_bureau_snapshots s
        ON a.client_id = s.client_id AND s.snapshot_date <= a.decision_date
      WHERE a.final_decision = 'approved'
      ORDER BY a.application_id, s.snapshot_date DESC
    ),
    inq_6m AS (
      SELECT a.application_id,
        COUNT(*)::int AS inq_cnt_6m
      FROM scoring_applications a
      JOIN scoring_bureau_inquiries i
        ON a.client_id = i.client_id
        AND i.inquiry_date BETWEEN a.decision_date - interval '6 months'
                               AND a.decision_date
      WHERE a.final_decision = 'approved'
      GROUP BY 1
    )
    """

    eda_bureau = q(
        engine,
        f"""
        WITH {bureau_asof_cte},
        base AS ({TARGET_SQL})
        SELECT
          CASE
            WHEN ba.bureau_score < 500 THEN '<500'
            WHEN ba.bureau_score < 650 THEN '500-650'
            WHEN ba.bureau_score < 750 THEN '650-750'
            WHEN ba.bureau_score < 850 THEN '750-850'
            ELSE '850+'
          END AS bureau_band,
          {mature_count}, {mature_bad_rate}
        FROM base b
        JOIN bureau_asof ba ON b.application_id = ba.application_id
        WHERE ba.bureau_score IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) FILTER (WHERE b.window_closed_12m = 1) > 0
        ORDER BY 1
        """,
    )
    eda_bureau.to_csv(DATA / "eda_bad_by_bureau.csv", index=False)

    eda_dti = q(
        engine,
        f"""
        WITH {bureau_asof_cte},
        base AS ({TARGET_SQL})
        SELECT
          CASE
            WHEN a.declared_income_uzs > 0
                 AND a.requested_amount_uzs::numeric / a.declared_income_uzs < 1 THEN '<1x'
            WHEN a.declared_income_uzs > 0
                 AND a.requested_amount_uzs::numeric / a.declared_income_uzs < 2 THEN '1-2x'
            WHEN a.declared_income_uzs > 0
                 AND a.requested_amount_uzs::numeric / a.declared_income_uzs < 3 THEN '2-3x'
            ELSE '3x+'
          END AS dti_band,
          {mature_count}, {mature_bad_rate}
        FROM base b
        JOIN scoring_applications a ON b.application_id = a.application_id
        WHERE a.declared_income_uzs > 0
        GROUP BY 1
        HAVING COUNT(*) FILTER (WHERE b.window_closed_12m = 1) > 0
        ORDER BY 1
        """,
    )
    eda_dti.to_csv(DATA / "eda_bad_by_dti.csv", index=False)

    # --- Feature dataset (core) ---
    features_sql = """
    WITH bureau_asof AS (
      SELECT DISTINCT ON (a.application_id)
        a.application_id,
        s.bureau_score,
        s.existing_debt_uzs,
        s.active_loans_cnt,
        s.snapshot_date
      FROM scoring_applications a
      JOIN scoring_bureau_snapshots s
        ON a.client_id = s.client_id AND s.snapshot_date <= a.decision_date
      WHERE a.final_decision = 'approved'
      ORDER BY a.application_id, s.snapshot_date DESC
    ),
    bureau_inq_6m AS (
      SELECT a.application_id,
        COUNT(*) AS inq_cnt_6m
      FROM scoring_applications a
      JOIN scoring_bureau_inquiries i
        ON a.client_id = i.client_id
        AND i.inquiry_date BETWEEN a.decision_date - interval '6 months'
                               AND a.decision_date
      WHERE a.final_decision = 'approved'
      GROUP BY a.application_id
    ),
    card_6m AS (
      SELECT a.application_id,
        COUNT(*) FILTER (WHERE t.status='approved') AS txn_approved_6m,
        COUNT(*) FILTER (WHERE t.status='declined') AS txn_declined_6m,
        SUM(CASE WHEN t.status='approved' THEN t.amount_uzs ELSE 0 END) AS spend_6m,
        SUM(CASE WHEN t.txn_type='salary_in' AND t.status='approved'
            THEN t.amount_uzs ELSE 0 END) AS salary_in_6m
      FROM scoring_applications a
      JOIN scoring_card_transactions t
        ON a.client_id = t.client_id
        AND t.txn_ts::date BETWEEN a.decision_date - interval '6 months'
                               AND a.decision_date - interval '1 day'
      WHERE a.final_decision = 'approved'
      GROUP BY a.application_id
    )
    SELECT
      a.application_id,
      a.client_id,
      a.decision_date,
      a.channel,
      a.purpose,
      a.requested_amount_uzs,
      a.term_months,
      a.declared_income_uzs,
      a.employment_months,
      cu.gender,
      cu.region,
      cu.customer_segment,
      cu.income_band,
      EXTRACT(YEAR FROM age(a.decision_date, cu.birth_date))::int AS age_at_decision,
      b.bureau_score,
      b.existing_debt_uzs,
      b.active_loans_cnt,
      COALESCE(i.inq_cnt_6m, 0) AS inq_cnt_6m,
      COALESCE(c.txn_approved_6m, 0) AS txn_approved_6m,
      COALESCE(c.txn_declined_6m, 0) AS txn_declined_6m,
      COALESCE(c.spend_6m, 0) AS spend_6m,
      COALESCE(c.salary_in_6m, 0) AS salary_in_6m,
      CASE WHEN a.declared_income_uzs > 0
        THEN ROUND(c.salary_in_6m::numeric / a.declared_income_uzs, 4)
        ELSE NULL END AS salary_to_declared_ratio
    FROM scoring_applications a
    LEFT JOIN scoring_customers cu ON a.client_id = cu.customer_id
    LEFT JOIN bureau_asof b ON a.application_id = b.application_id
    LEFT JOIN bureau_inq_6m i ON a.application_id = i.application_id
    LEFT JOIN card_6m c ON a.application_id = c.application_id
    WHERE a.final_decision = 'approved'
    """
    features_df = q(engine, features_sql)
    features_df.to_csv(DATA / "features_pre_decision.csv", index=False)

    # Merge target + features
    final_df = target_df.merge(
        features_df,
        on=["application_id", "client_id", "decision_date"],
        how="inner",
    )
    final_df.to_csv(DATA / "modeling_dataset.csv", index=False)

    results["dataset_rows"] = {
        "target": len(target_df),
        "features": len(features_df),
        "merged": len(final_df),
        "labeled_target_90": int(target_df["target_90"].notna().sum()),
    }

    with open(DATA / "analysis_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("Analysis complete.")
    print(json.dumps(results["target_summary"], indent=2))
    print(json.dumps(results["bad_rates"], indent=2))
    print(json.dumps(results["coverage"], indent=2))


if __name__ == "__main__":
    main()
