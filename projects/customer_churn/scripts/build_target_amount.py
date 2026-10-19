"""Fourth churn target: approved activity AND spend above a monthly floor.

Same cohort as silence N=60. A customer is alive (target=0) only if the
approved sum in the next 60 days is at least MONTHLY_MIN_UZS * 2.
Otherwise target=1: full silence or 'quiet spender'.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_targets import SNAPSHOTS, label_snapshot, load  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data_raw" / "useful"
OUT = PROJECT / "data" / "targets"

N = 60
# p10 of monthly approved sum among customer-months with ≥1 approved txn
# is ~481k UZS; round to a clean 50k grid. See amount_monthly_stats.csv.
MONTHLY_MIN_UZS = 500_000
WINDOW_MIN_UZS = int(MONTHLY_MIN_UZS * N / 30)  # 1_000_000 for 60 days
TRAIN_SNAP = "2025-07-31"
TEST_SNAP = "2025-09-30"


def load_approved_amounts() -> pd.DataFrame:
    txn = pd.read_csv(
        RAW / "churn_transactions.csv",
        parse_dates=["txn_ts"],
        usecols=["customer_id", "txn_ts", "amount_uzs", "status"],
    )
    ok = txn.loc[txn["status"] == "approved", ["customer_id", "txn_ts", "amount_uzs"]].copy()
    ok["d"] = ok["txn_ts"].dt.normalize()
    return ok


def monthly_spend_stats(ok: pd.DataFrame) -> pd.DataFrame:
    """Distribution of monthly approved sum among months with ≥1 approved txn."""
    m = ok.copy()
    m["month"] = m["txn_ts"].dt.to_period("M")
    monthly = m.groupby(["customer_id", "month"], as_index=False)["amount_uzs"].sum()
    monthly_2025 = monthly[monthly["month"].astype(str).str.startswith("2025")]

    def row(name: str, s: pd.Series, n_months: int) -> dict:
        return {
            "scope": name,
            "n_active_customer_months": n_months,
            "p05_uzs": float(s.quantile(0.05)),
            "p10_uzs": float(s.quantile(0.10)),
            "p25_uzs": float(s.quantile(0.25)),
            "p50_uzs": float(s.quantile(0.50)),
            "p75_uzs": float(s.quantile(0.75)),
            "share_below_50k": float((s < 50_000).mean()),
            "share_below_100k": float((s < 100_000).mean()),
            "share_below_200k": float((s < 200_000).mean()),
            "share_below_500k": float((s < MONTHLY_MIN_UZS).mean()),
            "chosen_monthly_min_uzs": MONTHLY_MIN_UZS,
        }

    return pd.DataFrame(
        [
            row("all_active_months", monthly["amount_uzs"], len(monthly)),
            row("active_months_2025", monthly_2025["amount_uzs"], len(monthly_2025)),
        ]
    )


def horizon_spend(
    ok: pd.DataFrame,
    customer_ids: pd.Series,
    snapshot: pd.Timestamp,
    horizon_end: pd.Timestamp,
) -> pd.DataFrame:
    post = ok[(ok["d"] > snapshot) & (ok["d"] <= horizon_end)]
    if post.empty:
        out = pd.DataFrame({"customer_id": customer_ids.unique()})
        out["horizon_amount_uzs"] = 0
        out["horizon_n_txn"] = 0
        return out
    g = post.groupby("customer_id").agg(
        horizon_amount_uzs=("amount_uzs", "sum"),
        horizon_n_txn=("amount_uzs", "size"),
    )
    out = pd.DataFrame({"customer_id": customer_ids.unique()}).merge(
        g, on="customer_id", how="left"
    )
    out["horizon_amount_uzs"] = out["horizon_amount_uzs"].fillna(0).astype("int64")
    out["horizon_n_txn"] = out["horizon_n_txn"].fillna(0).astype("int64")
    return out


def label_amount_snapshot(
    cust: pd.DataFrame,
    act: pd.DataFrame,
    ok: pd.DataFrame,
    snapshot: pd.Timestamp,
) -> tuple[pd.DataFrame, dict]:
    labeled, funnel = label_snapshot(cust, act, snapshot, N)
    spend = horizon_spend(ok, labeled["customer_id"], snapshot, snapshot + pd.Timedelta(days=N))
    df = labeled.merge(spend, on="customer_id", how="left")
    df["horizon_amount_uzs"] = df["horizon_amount_uzs"].fillna(0).astype("int64")
    df["horizon_n_txn"] = df["horizon_n_txn"].fillna(0).astype("int64")
    df["monthly_min_uzs"] = MONTHLY_MIN_UZS
    df["window_min_uzs"] = WINDOW_MIN_UZS
    df["monthly_equiv_uzs"] = (df["horizon_amount_uzs"] * 30 / N).round().astype("int64")
    df["silence_target"] = df["target"]
    in_c = df["in_cohort"]
    df["spent_below_threshold"] = pd.NA
    df.loc[in_c, "spent_below_threshold"] = (
        (df.loc[in_c, "horizon_n_txn"] > 0)
        & (df.loc[in_c, "horizon_amount_uzs"] < WINDOW_MIN_UZS)
    ).astype(int)
    # alive only if approved sum in the window meets the monthly floor
    df.loc[in_c, "target"] = (df.loc[in_c, "horizon_amount_uzs"] < WINDOW_MIN_UZS).astype(int)

    extra = int(df.loc[in_c, "spent_below_threshold"].sum()) if in_c.any() else 0
    silence_n = int(df.loc[in_c, "silence_target"].sum()) if in_c.any() else 0
    amount_n = int(df.loc[in_c, "target"].sum()) if in_c.any() else 0
    funnel_amt = {
        "snapshot_date": snapshot.date().isoformat(),
        "horizon_closed": funnel["horizon_closed"],
        "cohort": funnel["cohort"],
        "silence_churn_n": silence_n,
        "silence_churn_rate": float(df.loc[in_c, "silence_target"].mean()) if in_c.any() else np.nan,
        "spent_below_threshold_n": extra,
        "spent_below_threshold_rate": extra / funnel["cohort"] if funnel["cohort"] else np.nan,
        "amount_churn_n": amount_n,
        "amount_churn_rate": float(df.loc[in_c, "target"].mean()) if in_c.any() else np.nan,
        "monthly_min_uzs": MONTHLY_MIN_UZS,
        "window_min_uzs": WINDOW_MIN_UZS,
    }
    return df, funnel_amt


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cust, act = load()
    ok = load_approved_amounts()

    stats = monthly_spend_stats(ok)
    stats.to_csv(OUT / "amount_monthly_stats.csv", index=False)

    funnels = []
    parts = []
    for snap in SNAPSHOTS:
        labeled, funnel = label_amount_snapshot(cust, act, ok, snap)
        funnels.append(funnel)
        if funnel["horizon_closed"]:
            parts.append(labeled.loc[labeled["in_cohort"]].copy())

    cohort = pd.concat(parts, ignore_index=True)
    cohort["target"] = cohort["target"].astype(int)
    cohort["silence_target"] = cohort["silence_target"].astype(int)
    cohort["spent_below_threshold"] = cohort["spent_below_threshold"].astype(int)
    keep = [
        "customer_id",
        "snapshot_date",
        "silence_days",
        "segment",
        "signup_date",
        "first_txn_date",
        "last_txn_date",
        "days_silent",
        "tenure_days",
        "horizon_end",
        "horizon_n_txn",
        "horizon_amount_uzs",
        "monthly_equiv_uzs",
        "monthly_min_uzs",
        "window_min_uzs",
        "silence_target",
        "spent_below_threshold",
        "target",
        "returned_after_horizon",
    ]
    cohort[keep].to_csv(OUT / "target_60d_min_amount.csv", index=False)
    print(f"target_60d_min_amount.csv  rows={len(cohort)}")

    funnel_df = pd.DataFrame(funnels)
    funnel_df.to_csv(OUT / "funnel_60d_min_amount.csv", index=False)

    closed = funnel_df[funnel_df["horizon_closed"]].copy()
    jul = closed.loc[closed["snapshot_date"] == TRAIN_SNAP].iloc[0]
    sep = closed.loc[closed["snapshot_date"] == TEST_SNAP].iloc[0]
    p10 = float(stats.loc[stats["scope"] == "all_active_months", "p10_uzs"].iloc[0])
    p25 = float(stats.loc[stats["scope"] == "all_active_months", "p25_uzs"].iloc[0])
    p50 = float(stats.loc[stats["scope"] == "all_active_months", "p50_uzs"].iloc[0])

    cmp = pd.DataFrame(
        [
            {
                "definition": "silence_60d",
                "monthly_min_uzs": pd.NA,
                "window_min_uzs": pd.NA,
                "cohort_jul": int(jul["cohort"]),
                "cohort_sep": int(sep["cohort"]),
                "churn_rate_jul": round(float(jul["silence_churn_rate"]), 4),
                "churn_rate_sep": round(float(sep["silence_churn_rate"]), 4),
                "spent_below_threshold_jul": 0,
                "spent_below_threshold_sep": 0,
                "monthly_p10_uzs": round(p10),
                "monthly_p25_uzs": round(p25),
                "monthly_p50_uzs": round(p50),
            },
            {
                "definition": "silence_or_below_500k_per_month",
                "monthly_min_uzs": MONTHLY_MIN_UZS,
                "window_min_uzs": WINDOW_MIN_UZS,
                "cohort_jul": int(jul["cohort"]),
                "cohort_sep": int(sep["cohort"]),
                "churn_rate_jul": round(float(jul["amount_churn_rate"]), 4),
                "churn_rate_sep": round(float(sep["amount_churn_rate"]), 4),
                "spent_below_threshold_jul": int(jul["spent_below_threshold_n"]),
                "spent_below_threshold_sep": int(sep["spent_below_threshold_n"]),
                "monthly_p10_uzs": round(p10),
                "monthly_p25_uzs": round(p25),
                "monthly_p50_uzs": round(p50),
            },
        ]
    )
    cmp.to_csv(OUT / "compare_60d_min_amount.csv", index=False)
    print(cmp.to_string(index=False))
    print("monthly stats:")
    print(stats.to_string(index=False))
    print("funnel (closed snapshots):")
    print(closed.to_string(index=False))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
