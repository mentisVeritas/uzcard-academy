"""Main usage target.

Alive if either:
  A) ≥3 approved txns AND spend ≥ p5 (~800k UZS / 60 days), or
  B) ≥20 approved txns (amount ignored — frequent small payer is still ours).

Same cohort as silence N=60.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_target_amount import horizon_spend, load_approved_amounts
from build_targets import SNAPSHOTS, label_snapshot, load

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "data" / "targets"

N = 60
MIN_TXN = 3
HIGH_TXN = 20  # frequent use: skip the amount floor
# p5 of horizon spend among July cohort with ≥3 approved txns: 794_165
WINDOW_MIN_UZS = 800_000
TRAIN_SNAP = "2025-07-31"
TEST_SNAP = "2025-09-30"


def label_usage(cust, act, ok, snapshot: pd.Timestamp):
    labeled, funnel = label_snapshot(cust, act, snapshot, N)
    spend = horizon_spend(ok, labeled["customer_id"], snapshot, snapshot + pd.Timedelta(days=N))
    df = labeled.merge(spend, on="customer_id", how="left")
    df["horizon_amount_uzs"] = df["horizon_amount_uzs"].fillna(0).astype("int64")
    df["horizon_n_txn"] = df["horizon_n_txn"].fillna(0).astype("int64")
    df["min_txn"] = MIN_TXN
    df["high_txn"] = HIGH_TXN
    df["window_min_uzs"] = WINDOW_MIN_UZS
    df["silence_target"] = df["target"]
    in_c = df["in_cohort"]

    n = df["horizon_n_txn"]
    spend = df["horizon_amount_uzs"]
    path_a = (n >= MIN_TXN) & (spend >= WINDOW_MIN_UZS)
    path_b = n >= HIGH_TXN
    alive = path_a | path_b
    few = n < MIN_TXN
    # modest frequency but crumbs (not saved by 20-ops rule)
    poor_mid = (n >= MIN_TXN) & (n < HIGH_TXN) & (spend < WINDOW_MIN_UZS)
    saved_by_freq = path_b & ~path_a

    df.loc[in_c, "target"] = (~alive.loc[in_c]).astype(int)
    df["few_ops"] = pd.NA
    df["poor_only"] = pd.NA
    df["saved_by_freq"] = pd.NA
    df.loc[in_c, "few_ops"] = few.loc[in_c].astype(int)
    df.loc[in_c, "poor_only"] = poor_mid.loc[in_c].astype(int)
    df.loc[in_c, "saved_by_freq"] = saved_by_freq.loc[in_c].astype(int)

    extra = {
        "snapshot_date": snapshot.date().isoformat(),
        "horizon_closed": funnel["horizon_closed"],
        "cohort": funnel["cohort"],
        "silence_churn_rate": float(df.loc[in_c, "silence_target"].mean()) if in_c.any() else np.nan,
        "usage_churn_rate": float(df.loc[in_c, "target"].mean()) if in_c.any() else np.nan,
        "usage_churn_n": int(df.loc[in_c, "target"].sum()) if in_c.any() else 0,
        "few_ops_n": int(df.loc[in_c, "few_ops"].sum()) if in_c.any() else 0,
        "poor_only_n": int(df.loc[in_c, "poor_only"].sum()) if in_c.any() else 0,
        "saved_by_freq_n": int(df.loc[in_c, "saved_by_freq"].sum()) if in_c.any() else 0,
        "min_txn": MIN_TXN,
        "high_txn": HIGH_TXN,
        "window_min_uzs": WINDOW_MIN_UZS,
    }
    return df, extra


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cust, act = load()
    ok = load_approved_amounts()
    funnels = []
    parts = []
    for snap in SNAPSHOTS:
        labeled, funnel = label_usage(cust, act, ok, snap)
        funnels.append(funnel)
        if funnel["horizon_closed"]:
            parts.append(labeled.loc[labeled["in_cohort"]].copy())

    cohort = pd.concat(parts, ignore_index=True)
    for c in ("target", "silence_target", "few_ops", "poor_only", "saved_by_freq"):
        cohort[c] = cohort[c].astype(int)
    keep = [
        "customer_id",
        "snapshot_date",
        "segment",
        "signup_date",
        "first_txn_date",
        "last_txn_date",
        "days_silent",
        "tenure_days",
        "horizon_end",
        "horizon_n_txn",
        "horizon_amount_uzs",
        "min_txn",
        "high_txn",
        "window_min_uzs",
        "silence_target",
        "few_ops",
        "poor_only",
        "saved_by_freq",
        "target",
    ]
    cohort[keep].to_csv(OUT / "target_60d_usage.csv", index=False)
    funnel_df = pd.DataFrame(funnels)
    funnel_df.to_csv(OUT / "funnel_60d_usage.csv", index=False)

    closed = funnel_df[funnel_df["horizon_closed"]]
    jul = closed.loc[closed["snapshot_date"] == TRAIN_SNAP].iloc[0]
    sep = closed.loc[closed["snapshot_date"] == TEST_SNAP].iloc[0]
    cmp = pd.DataFrame(
        [
            {
                "definition": "silence_60d",
                "churn_rate_jul": round(float(jul["silence_churn_rate"]), 4),
                "churn_rate_sep": round(float(sep["silence_churn_rate"]), 4),
            },
            {
                "definition": "usage_3ops_p5_OR_20ops",
                "churn_rate_jul": round(float(jul["usage_churn_rate"]), 4),
                "churn_rate_sep": round(float(sep["usage_churn_rate"]), 4),
                "few_ops_jul": int(jul["few_ops_n"]),
                "poor_only_jul": int(jul["poor_only_n"]),
                "saved_by_20ops_jul": int(jul["saved_by_freq_n"]),
                "few_ops_sep": int(sep["few_ops_n"]),
                "poor_only_sep": int(sep["poor_only_n"]),
                "saved_by_20ops_sep": int(sep["saved_by_freq_n"]),
            },
        ]
    )
    cmp.to_csv(OUT / "compare_60d_usage.csv", index=False)
    print(f"target_60d_usage.csv rows={len(cohort)}")
    print(cmp.to_string(index=False))
    print(closed.to_string(index=False))


if __name__ == "__main__":
    main()
