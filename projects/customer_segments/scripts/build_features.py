"""Build customer feature matrix for segmentation.

Window: as_of = 2025-11-30, lookback = 6 months, min tenure = 90 days.
Personal window starts at max(window_start, signup_date).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from db import read_sql

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

AS_OF = "2025-11-30"
LOOKBACK_MONTHS = 6
MIN_TENURE_DAYS = 90


def features_sql(as_of: str, lookback_months: int, min_tenure_days: int) -> str:
    return f"""
WITH params AS (
    SELECT
        DATE '{as_of}' AS as_of_date,
        (DATE '{as_of}' - INTERVAL '{lookback_months} months')::date AS window_start
),
eligible AS (
    SELECT
        c.customer_id,
        c.region,
        c.gender,
        DATE_PART('year', AGE(p.as_of_date, c.birth_date))::int AS age_years,
        c.signup_date,
        (p.as_of_date - c.signup_date)::int AS tenure_days,
        p.as_of_date,
        p.window_start,
        GREATEST(p.window_start, c.signup_date) AS feat_start
    FROM seg_customers c
    CROSS JOIN params p
    WHERE c.signup_date <= p.as_of_date - INTERVAL '{min_tenure_days} days'
),
txn_feats AS (
    SELECT
        e.customer_id,
        COUNT(*) AS txn_cnt_all,
        COUNT(*) FILTER (WHERE t.direction = 'out') AS txn_cnt,
        COUNT(*) FILTER (WHERE t.direction = 'in') AS credit_cnt,
        COALESCE(SUM(t.amount_uzs) FILTER (WHERE t.direction = 'out'), 0) AS spend_uzs,
        COALESCE(SUM(t.amount_uzs) FILTER (WHERE t.direction = 'in'), 0) AS inflow_uzs,
        COUNT(DISTINCT t.channel) AS channel_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'pos') AS pos_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'ecom') AS ecom_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'p2p') AS p2p_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'atm') AS atm_cnt,
        COUNT(DISTINCT t.mcc_group) AS mcc_cnt,
        MAX(t.txn_ts) AS last_txn_ts
    FROM eligible e
    JOIN seg_transactions t
        ON t.customer_id = e.customer_id
       AND t.txn_ts >= e.feat_start
       AND t.txn_ts < e.as_of_date + INTERVAL '1 day'
    GROUP BY 1
),
bal_feats AS (
    SELECT
        e.customer_id,
        AVG(b.avg_balance_uzs) AS avg_balance_uzs,
        STDDEV(b.avg_balance_uzs) AS balance_volatility
    FROM eligible e
    LEFT JOIN seg_balances b
        ON b.customer_id = e.customer_id
       AND b.month_start >= DATE_TRUNC('month', e.feat_start)::date
       AND b.month_start <= DATE_TRUNC('month', e.as_of_date)::date
    GROUP BY 1
),
rev_feats AS (
    SELECT
        e.customer_id,
        SUM(r.net_revenue_uzs) AS net_revenue_uzs,
        AVG(r.net_revenue_uzs) AS avg_monthly_revenue_uzs,
        SUM(r.interchange_uzs) AS interchange_uzs,
        SUM(r.float_income_uzs) AS float_income_uzs,
        SUM(r.transfer_fee_uzs) AS transfer_fee_uzs,
        SUM(r.atm_cost_uzs) AS atm_cost_uzs
    FROM eligible e
    LEFT JOIN seg_revenue_monthly r
        ON r.customer_id = e.customer_id
       AND r.month_start >= DATE_TRUNC('month', e.feat_start)::date
       AND r.month_start <= DATE_TRUNC('month', e.as_of_date)::date
    GROUP BY 1
),
prod_feats AS (
    SELECT
        e.customer_id,
        COUNT(DISTINCT p.product_code) AS product_cnt
    FROM eligible e
    LEFT JOIN seg_products p
        ON p.customer_id = e.customer_id
       AND p.opened_at <= e.as_of_date
    GROUP BY 1
)
SELECT
    e.customer_id,
    e.region,
    e.gender,
    e.age_years,
    e.tenure_days,
    e.as_of_date,
    e.window_start,
    e.feat_start,
    (e.as_of_date - e.feat_start)::int + 1 AS window_days,
    COALESCE(t.txn_cnt_all, 0) AS txn_cnt_all,
    COALESCE(t.txn_cnt, 0) AS txn_cnt,
    COALESCE(t.credit_cnt, 0) AS credit_cnt,
    COALESCE(t.spend_uzs, 0) AS spend_uzs,
    COALESCE(t.inflow_uzs, 0) AS inflow_uzs,
    COALESCE(t.channel_cnt, 0) AS channel_cnt,
    COALESCE(t.pos_cnt, 0) AS pos_cnt,
    COALESCE(t.ecom_cnt, 0) AS ecom_cnt,
    COALESCE(t.p2p_cnt, 0) AS p2p_cnt,
    COALESCE(t.atm_cnt, 0) AS atm_cnt,
    COALESCE(t.mcc_cnt, 0) AS mcc_cnt,
    t.last_txn_ts,
    COALESCE(b.avg_balance_uzs, 0) AS avg_balance_uzs,
    COALESCE(b.balance_volatility, 0) AS balance_volatility,
    COALESCE(r.net_revenue_uzs, 0) AS net_revenue_uzs,
    COALESCE(r.avg_monthly_revenue_uzs, 0) AS avg_monthly_revenue_uzs,
    COALESCE(r.interchange_uzs, 0) AS interchange_uzs,
    COALESCE(r.float_income_uzs, 0) AS float_income_uzs,
    COALESCE(r.transfer_fee_uzs, 0) AS transfer_fee_uzs,
    COALESCE(r.atm_cost_uzs, 0) AS atm_cost_uzs,
    COALESCE(p.product_cnt, 0) AS product_cnt,
    CASE WHEN COALESCE(t.txn_cnt_all, 0) >= 1 THEN 1 ELSE 0 END AS active_in_window
FROM eligible e
LEFT JOIN txn_feats t ON t.customer_id = e.customer_id
LEFT JOIN bal_feats b ON b.customer_id = e.customer_id
LEFT JOIN rev_feats r ON r.customer_id = e.customer_id
LEFT JOIN prod_feats p ON p.customer_id = e.customer_id
"""


def add_derived(df: pd.DataFrame, as_of: str) -> pd.DataFrame:
    out = df.copy()
    as_of_ts = pd.Timestamp(as_of)
    out["as_of_date"] = pd.to_datetime(out["as_of_date"])
    out["feat_start"] = pd.to_datetime(out["feat_start"])
    out["window_start"] = pd.to_datetime(out["window_start"])
    out["last_txn_ts"] = pd.to_datetime(out["last_txn_ts"])

    days = out["window_days"].clip(lower=1)
    out["txn_per_month"] = out["txn_cnt"] * 30.0 / days
    out["spend_per_month"] = out["spend_uzs"] * 30.0 / days
    out["avg_ticket"] = out["spend_uzs"] / out["txn_cnt"].replace(0, pd.NA)
    out["avg_ticket"] = out["avg_ticket"].fillna(0)

    denom = out["txn_cnt_all"].replace(0, pd.NA)
    for col, share in (
        ("pos_cnt", "pos_share"),
        ("ecom_cnt", "ecom_share"),
        ("p2p_cnt", "p2p_share"),
        ("atm_cnt", "atm_share"),
    ):
        out[share] = (out[col] / denom).fillna(0)

    out["recency_days"] = (as_of_ts - out["last_txn_ts"]).dt.days
    out["recency_days"] = out["recency_days"].fillna(out["window_days"])
    out["short_history"] = (out["feat_start"] > out["window_start"]).astype(int)
    return out


def build(
    as_of: str = AS_OF,
    lookback_months: int = LOOKBACK_MONTHS,
    min_tenure_days: int = MIN_TENURE_DAYS,
    suffix: str = "",
) -> dict:
    print(f"Building features as_of={as_of} lookback={lookback_months}m …")
    sql = features_sql(as_of, lookback_months, min_tenure_days)
    df = read_sql(sql)
    df = add_derived(df, as_of)

    active = df[df["active_in_window"] == 1].copy()
    inactive = df[df["active_in_window"] == 0].copy()

    stem = suffix if suffix else ""
    df.to_csv(DATA / f"features_all_eligible{stem}.csv", index=False)
    active.to_csv(DATA / f"features_active{stem}.csv", index=False)
    inactive.to_csv(DATA / f"features_inactive{stem}.csv", index=False)

    summary = {
        "as_of": as_of,
        "lookback_months": lookback_months,
        "min_tenure_days": min_tenure_days,
        "eligible": int(len(df)),
        "active_in_window": int(len(active)),
        "inactive_in_window": int(len(inactive)),
        "short_history_active": int(active["short_history"].sum()),
        "median_window_days": float(active["window_days"].median()) if len(active) else None,
        "median_spend_uzs": float(active["spend_uzs"].median()) if len(active) else None,
        "p99_spend_uzs": float(active["spend_uzs"].quantile(0.99)) if len(active) else None,
    }
    (DATA / f"features_summary{stem}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(
        f"Eligible: {len(df):,} | Active: {len(active):,} | "
        f"Inactive: {len(inactive):,} | short history: {summary['short_history_active']:,}"
    )
    print(f"Saved -> {DATA / f'features_active{stem}.csv'}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build segmentation feature matrix")
    parser.add_argument("--as-of", default=AS_OF)
    parser.add_argument("--lookback", type=int, default=LOOKBACK_MONTHS)
    parser.add_argument("--min-tenure", type=int, default=MIN_TENURE_DAYS)
    parser.add_argument("--suffix", default="", help="e.g. _no_dec for stability check")
    args = parser.parse_args()
    build(args.as_of, args.lookback, args.min_tenure, args.suffix)


if __name__ == "__main__":
    main()
