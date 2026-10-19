"""Build three silence-based churn targets: 30 / 45 / 60 days.

Amount-floor target (4th definition) is scripts/build_target_amount.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data_raw" / "useful"
OUT = PROJECT / "data" / "targets"

DUMP = pd.Timestamp("2025-12-31")
NS = (30, 45, 60)
MIN_TENURE = 60  # days since first approved, not since signup
SNAPSHOTS = pd.to_datetime(
    [
        "2025-03-31",
        "2025-04-30",
        "2025-05-31",
        "2025-06-30",
        "2025-07-31",
        "2025-08-31",
        "2025-09-30",
        "2025-10-31",
        "2025-11-30",
    ]
)


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    cust = pd.read_csv(RAW / "churn_customers.csv", parse_dates=["signup_date"])
    txn = pd.read_csv(RAW / "churn_transactions.csv", parse_dates=["txn_ts"])
    ok = txn.loc[txn["status"] == "approved", ["customer_id", "txn_ts"]].copy()
    ok["d"] = ok["txn_ts"].dt.normalize()
    act = ok.groupby(["customer_id", "d"], as_index=False).size()
    return cust, act


def gap_stats(act: pd.DataFrame) -> pd.DataFrame:
    s = act.sort_values(["customer_id", "d"])
    s["prev"] = s.groupby("customer_id")["d"].shift(1)
    s["gap"] = (s["d"] - s["prev"]).dt.days
    gaps = s["gap"].dropna()
    mx = s.dropna(subset=["gap"]).groupby("customer_id")["gap"].max()
    rows = []
    for n in NS:
        rows.append(
            {
                "silence_days": n,
                "share_gaps_gt_N": float((gaps > n).mean()),
                "share_customers_returned_after_pause_gt_N": float((mx > n).mean()),
                "gap_p50": float(gaps.median()),
                "gap_p95": float(gaps.quantile(0.95)),
                "gap_p99": float(gaps.quantile(0.99)),
            }
        )
    return pd.DataFrame(rows)


def label_snapshot(
    cust: pd.DataFrame,
    act: pd.DataFrame,
    snapshot: pd.Timestamp,
    n: int,
) -> tuple[pd.DataFrame, dict]:
    horizon_end = snapshot + pd.Timedelta(days=n)
    closed = horizon_end <= DUMP

    pre = act[act["d"] <= snapshot]
    last = pre.groupby("customer_id")["d"].max()
    first = pre.groupby("customer_id")["d"].min()
    post = act[(act["d"] > snapshot) & (act["d"] <= horizon_end)]
    later = act[act["d"] > horizon_end]
    has_post = set(post["customer_id"].unique())
    has_later = set(later["customer_id"].unique())

    df = cust[["customer_id", "signup_date", "segment"]].copy()
    df["snapshot_date"] = snapshot
    df["silence_days"] = n
    df["horizon_end"] = horizon_end
    df["last_txn_date"] = df["customer_id"].map(last)
    df["first_txn_date"] = df["customer_id"].map(first)
    df["days_silent"] = (snapshot - df["last_txn_date"]).dt.days
    # Tenure = how long they have actually used the card, not how long they sit in CRM.
    df["tenure_days"] = (snapshot - df["first_txn_date"]).dt.days
    df["has_txn_in_horizon"] = df["customer_id"].isin(has_post)
    df["returned_after_horizon"] = df["customer_id"].isin(has_later)

    not_yet = df["signup_date"] > snapshot
    no_hist = df["last_txn_date"].isna()
    too_new = (~no_hist) & (df["tenure_days"] < MIN_TENURE)
    already = (~no_hist) & (df["days_silent"] > n)
    horizon_open = not closed
    in_cohort = (
        closed
        & (~not_yet)
        & (~no_hist)
        & (~too_new)
        & (~already)
    )

    reason = np.full(len(df), "in_cohort", dtype=object)
    reason[not_yet.to_numpy()] = "signup_after_snapshot"
    reason[no_hist.to_numpy()] = "no_history"
    reason[too_new.to_numpy()] = "too_new"
    reason[already.to_numpy()] = "already_silent"
    if horizon_open:
        reason[:] = "horizon_not_closed"
    df["exclude_reason"] = reason
    df.loc[in_cohort, "exclude_reason"] = "in_cohort"
    df["in_cohort"] = in_cohort
    df["target"] = pd.NA
    df.loc[in_cohort, "target"] = (~df.loc[in_cohort, "has_txn_in_horizon"]).astype(int)

    funnel = {
        "silence_days": n,
        "snapshot_date": snapshot.date().isoformat(),
        "horizon_closed": closed,
        "n_customers": int(len(df)),
        "signup_after_snapshot": int(not_yet.sum()),
        "no_history": int(no_hist.sum()),
        "too_new": int(too_new.sum()),
        "already_silent": int(already.sum()),
        "cohort": int(in_cohort.sum()),
        "churn_n": int(df.loc[in_cohort, "target"].sum()) if in_cohort.any() else 0,
        "churn_rate": float(df.loc[in_cohort, "target"].mean()) if in_cohort.any() else np.nan,
    }
    if in_cohort.any():
        y1 = df["in_cohort"] & (df["target"] == 1)
        funnel["churn_then_returned"] = int((y1 & df["returned_after_horizon"]).sum())
        funnel["churn_then_returned_rate"] = (
            float((y1 & df["returned_after_horizon"]).sum() / y1.sum()) if y1.any() else np.nan
        )
        for seg, g in df.loc[in_cohort].groupby("segment"):
            funnel[f"rate_{seg}"] = float(g["target"].mean())
    return df, funnel


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cust, act = load()
    gaps = gap_stats(act)
    gaps.to_csv(OUT / "gap_stats.csv", index=False)

    funnels = []
    for n in NS:
        parts = []
        for snap in SNAPSHOTS:
            labeled, funnel = label_snapshot(cust, act, snap, n)
            funnels.append(funnel)
            if funnel["horizon_closed"]:
                parts.append(labeled.loc[labeled["in_cohort"]].copy())
        cohort = pd.concat(parts, ignore_index=True)
        cohort["target"] = cohort["target"].astype(int)
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
            "target",
            "returned_after_horizon",
        ]
        cohort[keep].to_csv(OUT / f"target_{n}d.csv", index=False)
        print(f"target_{n}d.csv  rows={len(cohort)}")

    funnel_df = pd.DataFrame(funnels)
    funnel_df.to_csv(OUT / "funnel_by_snapshot.csv", index=False)

    # compact comparison on shared snapshots (horizon closed for 60d too)
    shared = funnel_df[funnel_df["horizon_closed"]].copy()
    cmp_rows = []
    for n, g in shared.groupby("silence_days"):
        g = g.sort_values("snapshot_date")
        jul = g.loc[g["snapshot_date"] == "2025-07-31"].iloc[0]
        sep = g.loc[g["snapshot_date"] == "2025-09-30"].iloc[0]
        jun = g.loc[g["snapshot_date"] == "2025-06-30"].iloc[0]
        gap = gaps.loc[gaps["silence_days"] == n].iloc[0]
        cmp_rows.append(
            {
                "silence_days": n,
                "gap_p99_days": round(gap["gap_p99"], 1),
                "share_usual_gaps_gt_N": round(gap["share_gaps_gt_N"], 4),
                "share_clients_ever_paused_gt_N_and_returned": round(
                    gap["share_customers_returned_after_pause_gt_N"], 4
                ),
                "cohort_jul": int(jul["cohort"]),
                "churn_rate_jun": round(jun["churn_rate"], 4),
                "churn_rate_jul": round(jul["churn_rate"], 4),
                "churn_rate_sep": round(sep["churn_rate"], 4),
                "already_silent_jul": int(jul["already_silent"]),
                "labeled_churn_then_returned_jul": round(jul["churn_then_returned_rate"], 4),
                "labeled_churn_then_returned_sep": round(sep["churn_then_returned_rate"], 4),
            }
        )
    cmp = pd.DataFrame(cmp_rows)
    cmp.to_csv(OUT / "compare_30_45_60.csv", index=False)
    print(cmp.to_string(index=False))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
