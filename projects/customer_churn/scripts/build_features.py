"""Features for the usage target, snapshots 2025-07-31 and 2025-09-30.

Lag is only 30d vs previous 30d, plus recency. No 7d / 60d lag zoo.
Everything is cut at snapshot (inclusive). No churn_customers_360.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data_raw" / "useful"
TARGETS = PROJECT / "data" / "targets"
OUT = PROJECT / "data" / "model"

SNAPSHOTS = (pd.Timestamp("2025-07-31"), pd.Timestamp("2025-09-30"))


def _between(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, col: str = "d") -> pd.DataFrame:
    return df.loc[(df[col] > start) & (df[col] <= end)]


def _size(df: pd.DataFrame, name: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="int64", name=name)
    return df.groupby("customer_id").size().rename(name)


def _sum(df: pd.DataFrame, col: str, name: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="float64", name=name)
    return df.groupby("customer_id")[col].sum().rename(name)


def _last(df: pd.DataFrame, col: str, name: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="datetime64[ns]", name=name)
    return df.groupby("customer_id")[col].max().rename(name)


def txn_features(txn: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    pre = txn.loc[txn["d"] <= snapshot]
    ok = pre.loc[pre["approved"]]
    declined = pre.loc[~pre["approved"]]

    last30 = _between(ok, snapshot - pd.Timedelta(days=30), snapshot)
    prev30 = _between(ok, snapshot - pd.Timedelta(days=60), snapshot - pd.Timedelta(days=30))
    dec30 = _between(declined, snapshot - pd.Timedelta(days=30), snapshot)
    all30 = _between(pre, snapshot - pd.Timedelta(days=30), snapshot)

    last_d = _last(ok, "d", "last_txn_date")
    out = last_d.to_frame()
    out["days_since_last_txn"] = (snapshot - out["last_txn_date"]).dt.days

    pieces = [
        _size(last30, "txn_cnt_30d"),
        _size(prev30, "txn_cnt_prev_30d"),
        _sum(last30, "amount_uzs", "spend_30d"),
        _sum(prev30, "amount_uzs", "spend_prev_30d"),
        _size(dec30, "declined_cnt_30d"),
        _size(all30, "txn_all_cnt_30d"),
        _size(_between(ok.loc[ok["txn_type"] == "salary_in"], snapshot - pd.Timedelta(days=30), snapshot), "salary_in_30d"),
    ]
    for s in pieces:
        out = out.join(s, how="outer")

    out["avg_ticket_30d"] = out["spend_30d"] / out["txn_cnt_30d"].replace(0, np.nan)
    out["txn_ratio_30d"] = out["txn_cnt_30d"] / (out["txn_cnt_prev_30d"] + 1)
    out["spend_ratio_30d"] = out["spend_30d"] / (out["spend_prev_30d"] + 1)
    out["decline_rate_30d"] = out["declined_cnt_30d"] / (out["txn_all_cnt_30d"] + 1)
    return out.drop(columns=["last_txn_date"])


def app_features(app: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    pre = app.loc[app["d"] <= snapshot]
    last30 = _between(pre, snapshot - pd.Timedelta(days=30), snapshot)
    last_d = _last(pre, "d", "last_app_date")
    out = last_d.to_frame()
    out["days_since_last_app"] = (snapshot - out["last_app_date"]).dt.days
    for s in (
        _size(last30, "app_cnt_30d"),
        _size(last30.loc[last30["event_type"] == "login"], "app_login_30d"),
        _size(last30.loc[last30["event_type"] == "support_chat"], "app_support_chat_30d"),
    ):
        out = out.join(s, how="outer")
    return out.drop(columns=["last_app_date"])


def card_features(cards: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    issued = cards.loc[cards["issue_date"] <= snapshot].copy()
    known = issued["status_changed_at"].isna() | (issued["status_changed_at"] <= snapshot)
    issued["status_at_t0"] = np.where(known, issued["status"], "active")
    g = issued.groupby("customer_id")
    out = pd.DataFrame(
        {
            "cards_cnt": g.size(),
            "cards_blocked_cnt": g["status_at_t0"].apply(lambda s: int((s == "blocked").sum())),
            "cards_credit_cnt": g["card_type"].apply(lambda s: int((s == "credit").sum())),
        }
    )
    return out


def product_features(products: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    opened = products["opened_at"] <= snapshot
    still = products["closed_at"].isna() | (products["closed_at"] > snapshot)
    live = products.loc[opened & still]
    closed = products.loc[opened & products["closed_at"].notna() & (products["closed_at"] <= snapshot)]
    closed_90 = closed.loc[closed["closed_at"] > snapshot - pd.Timedelta(days=90)]
    out = _size(live, "products_open_cnt").to_frame()
    out = out.join(_size(closed_90, "products_closed_90d"), how="outer")
    return out


def product_event_features(pe: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    last30 = _between(pe.loc[pe["d"] <= snapshot], snapshot - pd.Timedelta(days=30), snapshot)
    return _size(last30, "product_events_30d").to_frame()


def support_features(tickets: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    pre = tickets.loc[tickets["opened_at"] <= snapshot]
    last90 = pre.loc[pre["opened_at"] > snapshot - pd.Timedelta(days=90)]
    last30 = pre.loc[pre["opened_at"] > snapshot - pd.Timedelta(days=30)]
    fee = last90.loc[last90["topic"] == "fee_complaint"]
    unresolved = pre.loc[pre["resolved_at"].isna() | (pre["resolved_at"] > snapshot)]
    csat = pre.loc[pre["satisfaction"].notna()].groupby("customer_id")["satisfaction"].mean().rename("csat_mean")
    out = _size(last90, "tickets_90d").to_frame()
    out = out.join(_size(last30, "tickets_30d"), how="outer")
    out = out.join(_size(fee, "fee_complaint_90d"), how="outer")
    out = out.join(_size(unresolved, "tickets_open_cnt"), how="outer")
    out = out.join(csat, how="outer")
    return out


def sub_features(
    subs: pd.DataFrame,
    charges: pd.DataFrame,
    snapshot: pd.Timestamp,
) -> pd.DataFrame:
    started = subs.loc[subs["started_at"] <= snapshot].copy()
    canceled = started["canceled_at"].notna() & (started["canceled_at"] <= snapshot)
    started["active_at_t0"] = ~canceled
    g = started.groupby("customer_id")
    out = pd.DataFrame(
        {
            "has_active_sub": g["active_at_t0"].any().astype(int),
            "sub_canceled": g["active_at_t0"].apply(lambda s: int((~s).any())),
        }
    )
    pre = charges.loc[charges["charged_at"] <= snapshot]
    last90 = pre.loc[pre["charged_at"] > snapshot - pd.Timedelta(days=90)]
    failed = last90.loc[last90["status"] == "failed"]
    out = out.join(_size(failed, "failed_charges_90d"), how="outer")
    out = out.join(_size(last90, "charges_90d"), how="outer")
    out["charge_fail_rate_90d"] = out["failed_charges_90d"] / (out["charges_90d"] + 1)
    return out


def tariff_features(tariff: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    hit = tariff.loc[tariff["effective_date"] <= snapshot].copy()
    hit["tariff_hike"] = 1
    hit["fee_hike_uzs"] = hit["new_monthly_fee_uzs"] - hit["old_monthly_fee_uzs"]
    return hit.set_index("customer_id")[["tariff_hike", "fee_hike_uzs"]]


def campaign_features(camp: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    pre = camp.loc[camp["contacted_at"] <= snapshot]
    last90 = pre.loc[pre["contacted_at"] > snapshot - pd.Timedelta(days=90)]
    out = _size(pre, "campaigns_ever").to_frame()
    out = out.join(_size(last90, "campaigns_90d"), how="outer")
    return out


def customer_features(cust: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    out = cust.set_index("customer_id")[
        ["gender", "region", "acq_channel", "segment", "is_payroll", "declared_income_uzs", "signup_date", "birth_date"]
    ].copy()
    out["tenure_days"] = (snapshot - out["signup_date"]).dt.days
    out["age_years"] = (snapshot - out["birth_date"]).dt.days / 365.25
    out["log_income"] = np.log1p(out["declared_income_uzs"].clip(lower=0))
    return out.drop(columns=["signup_date", "birth_date", "declared_income_uzs"])


def fill_counts(df: pd.DataFrame, count_cols: list[str]) -> pd.DataFrame:
    for c in count_cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)
    return df


def features_for_snapshot(
    snapshot: pd.Timestamp,
    base: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    ids = base["customer_id"]
    out = customer_features(tables["cust"], snapshot)
    out = out.loc[out.index.isin(ids)]

    blocks = [
        txn_features(tables["txn"], snapshot),
        app_features(tables["app"], snapshot),
        card_features(tables["cards"], snapshot),
        product_features(tables["products"], snapshot),
        product_event_features(tables["pe"], snapshot),
        support_features(tables["tickets"], snapshot),
        sub_features(tables["subs"], tables["charges"], snapshot),
        tariff_features(tables["tariff"], snapshot),
        campaign_features(tables["camp"], snapshot),
    ]
    for b in blocks:
        out = out.join(b, how="left")

    count_cols = [
        "txn_cnt_30d",
        "txn_cnt_prev_30d",
        "spend_30d",
        "spend_prev_30d",
        "declined_cnt_30d",
        "txn_all_cnt_30d",
        "salary_in_30d",
        "app_cnt_30d",
        "app_login_30d",
        "app_support_chat_30d",
        "cards_cnt",
        "cards_blocked_cnt",
        "cards_credit_cnt",
        "products_open_cnt",
        "products_closed_90d",
        "product_events_30d",
        "tickets_90d",
        "tickets_30d",
        "fee_complaint_90d",
        "tickets_open_cnt",
        "has_active_sub",
        "sub_canceled",
        "failed_charges_90d",
        "charges_90d",
        "tariff_hike",
        "fee_hike_uzs",
        "campaigns_ever",
        "campaigns_90d",
    ]
    out = fill_counts(out, count_cols)
    out["txn_ratio_30d"] = out["txn_cnt_30d"] / (out["txn_cnt_prev_30d"] + 1)
    out["spend_ratio_30d"] = out["spend_30d"] / (out["spend_prev_30d"] + 1)
    out["decline_rate_30d"] = out["declined_cnt_30d"] / (out["txn_all_cnt_30d"] + 1)
    out["charge_fail_rate_90d"] = out["failed_charges_90d"] / (out["charges_90d"] + 1)
    out["avg_ticket_30d"] = out["spend_30d"] / out["txn_cnt_30d"].replace(0, np.nan)
    out["avg_ticket_30d"] = out["avg_ticket_30d"].fillna(0)
    # never used the app by t0 → recency = tenure (already a customer, just no app)
    out["days_since_last_app"] = out["days_since_last_app"].fillna(out["tenure_days"])
    out["days_since_last_txn"] = out["days_since_last_txn"].fillna(out["tenure_days"])
    out["csat_mean"] = out["csat_mean"].fillna(-1)
    out["snapshot_date"] = snapshot
    return out.reset_index(names="customer_id")


def load_tables() -> dict[str, pd.DataFrame]:
    print("loading CSVs…")
    cust = pd.read_csv(
        RAW / "churn_customers.csv",
        parse_dates=["signup_date", "birth_date"],
        usecols=[
            "customer_id",
            "birth_date",
            "gender",
            "region",
            "signup_date",
            "acq_channel",
            "segment",
            "is_payroll",
            "declared_income_uzs",
        ],
    )
    txn = pd.read_csv(
        RAW / "churn_transactions.csv",
        parse_dates=["txn_ts"],
        usecols=["customer_id", "txn_ts", "txn_type", "amount_uzs", "status"],
    )
    txn["d"] = txn["txn_ts"].dt.normalize()
    txn["approved"] = txn["status"] == "approved"
    txn = txn.drop(columns=["txn_ts", "status"])

    app = pd.read_csv(
        RAW / "churn_app_events.csv",
        parse_dates=["event_ts"],
        usecols=["customer_id", "event_ts", "event_type"],
    )
    app["d"] = app["event_ts"].dt.normalize()
    app = app.drop(columns=["event_ts"])

    cards = pd.read_csv(
        RAW / "churn_cards.csv",
        parse_dates=["issue_date", "status_changed_at"],
        usecols=["customer_id", "card_type", "issue_date", "status", "status_changed_at"],
    )
    products = pd.read_csv(
        RAW / "churn_products.csv",
        parse_dates=["opened_at", "closed_at"],
        usecols=["customer_id", "opened_at", "closed_at"],
    )
    pe = pd.read_csv(
        RAW / "churn_product_events.csv",
        parse_dates=["event_date"],
        usecols=["customer_id", "event_date"],
    )
    pe["d"] = pe["event_date"].dt.normalize()
    pe = pe.drop(columns=["event_date"])

    tickets = pd.read_csv(
        RAW / "churn_support_tickets.csv",
        parse_dates=["opened_at", "resolved_at"],
        usecols=["customer_id", "opened_at", "topic", "resolved_at", "satisfaction"],
    )
    subs = pd.read_csv(
        RAW / "churn_subscriptions.csv",
        parse_dates=["started_at", "canceled_at"],
        usecols=["customer_id", "started_at", "canceled_at"],
    )
    charges = pd.read_csv(
        RAW / "churn_subscription_charges.csv",
        parse_dates=["charged_at"],
        usecols=["customer_id", "charged_at", "status"],
    )
    tariff = pd.read_csv(
        RAW / "churn_tariff_changes.csv",
        parse_dates=["effective_date"],
        usecols=["customer_id", "effective_date", "old_monthly_fee_uzs", "new_monthly_fee_uzs"],
    )
    camp = pd.read_csv(
        RAW / "churn_retention_campaigns.csv",
        parse_dates=["contacted_at"],
        usecols=["customer_id", "contacted_at"],
    )
    return {
        "cust": cust,
        "txn": txn,
        "app": app,
        "cards": cards,
        "products": products,
        "pe": pe,
        "tickets": tickets,
        "subs": subs,
        "charges": charges,
        "tariff": tariff,
        "camp": camp,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    y = pd.read_csv(TARGETS / "target_60d_usage.csv", parse_dates=["snapshot_date"])
    y = y.loc[y["snapshot_date"].isin(SNAPSHOTS), ["customer_id", "snapshot_date", "target"]].copy()
    tables = load_tables()
    parts = []
    for snap in SNAPSHOTS:
        base = y.loc[y["snapshot_date"] == snap]
        print(f"features {snap.date()}  cohort={len(base)}")
        feat = features_for_snapshot(snap, base, tables)
        feat = feat.merge(base, on=["customer_id", "snapshot_date"], how="inner")
        parts.append(feat)
    df = pd.concat(parts, ignore_index=True)
    path = OUT / "features_60d.csv"
    df.to_csv(path, index=False)
    print("wrote", path, "rows=", len(df), "cols=", df.shape[1])
    print(df.groupby("snapshot_date")["target"].agg(["count", "mean"]))


if __name__ == "__main__":
    main()
