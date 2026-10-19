"""Generate EDA figures for credit scoring presentation."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIG = Path(__file__).resolve().parent / "figures"

BG = "#0f1117"
FG = "white"


def style_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    ax.title.set_color(FG)
    ax.xaxis.label.set_color(FG)
    ax.yaxis.label.set_color(FG)
    ax.tick_params(colors=FG)
    for spine in ax.spines.values():
        spine.set_color("#333")


def save(fig: plt.Figure, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / name
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"saved {path}")


def bad_rate_by_month() -> None:
    """Vintage chart: 90+ DPD within first 6 months — shows recent deterioration."""
    df = pd.read_csv(DATA / "bad_rate_by_month_6m.csv")
    df = df[df["n_6m"] > 0].copy()
    df["issue_dt"] = pd.to_datetime(df["issue_month"])
    df["month"] = df["issue_dt"].dt.strftime("%m.%y")
    rates = df["bad_rate_90_6m" if "bad_rate_90_6m" in df.columns else "bad90_6m"] * 100
    spike = pd.Timestamp("2024-06-01")
    colors = ["#ff6b6b" if d >= spike else "#4f8cff" for d in df["issue_dt"]]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    bars = ax.bar(df["month"], rates, color=colors, edgecolor="none")
    pre = rates[df["issue_dt"] < spike]
    post = rates[df["issue_dt"] >= spike]
    if len(pre):
        ax.axhline(pre.mean(), color="#4f8cff", ls="--", lw=1.2, alpha=0.7, label=f"до июн 24: {pre.mean():.1f}%")
    if len(post):
        ax.axhline(post.mean(), color="#ff6b6b", ls="--", lw=1.2, alpha=0.7, label=f"с июн 24: {post.mean():.1f}%")
    spike_idx = int((df["issue_dt"] >= spike).values.argmax())
    ax.axvspan(spike_idx - 0.5, len(df) - 0.5, color="#ff6b6b", alpha=0.08)
    ax.text(spike_idx + 0.2, rates.max() * 0.95, "июнь 2024 —\nрезкий рост", color="#ff6b6b", fontsize=9, fontweight="bold")
    ax.set_ylabel("Bad rate 90+ DPD, %")
    ax.set_xlabel("Месяц выдачи")
    ax.set_title("Просрочка по когортам: 90+ DPD за первые 6 месяцев")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(facecolor=BG, edgecolor="#333", labelcolor=FG, fontsize=8)
    for bar, val in zip(bars, rates):
        if val >= 15:
            ax.text(bar.get_x() + bar.get_width() / 2, val + 0.4, f"{val:.1f}%", ha="center", fontsize=7, color="#ff9f9f")
    fig.patch.set_facecolor(BG)
    style_ax(ax)
    save(fig, "bad_rate_by_month.png")


def bad_rate_thresholds_by_month() -> None:
    path = DATA / "bad_rate_by_month_thresholds.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    df["month"] = pd.to_datetime(df["issue_month"]).dt.strftime("%Y-%m")
    x = np.arange(len(df))
    w = 0.25

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(x - w, df["bad30"] * 100, width=w, label="30+ дней", color="#ffc53d")
    ax.bar(x, df["bad60"] * 100, width=w, label="60+ дней", color="#ff9f43")
    ax.bar(x + w, df["bad90"] * 100, width=w, label="90+ дней", color="#4f8cff")
    for col, color in [("bad30", "#ffc53d"), ("bad60", "#ff9f43"), ("bad90", "#4f8cff")]:
        ax.axhline(df[col].mean() * 100, color=color, ls="--", lw=1, alpha=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(df["month"], rotation=45, ha="right")
    ax.set_ylabel("Доля плохих, %")
    ax.set_xlabel("Месяц выдачи (зрелые когорты)")
    ax.set_title("Сравнение порогов просрочки: 30+ vs 60+ vs 90+")
    ax.legend(facecolor=BG, edgecolor="#333", labelcolor=FG, ncol=3, loc="upper center")
    fig.patch.set_facecolor(BG)
    style_ax(ax)
    save(fig, "bad_rate_thresholds_by_month.png")


AMOUNT_BAND_ORDER = ["<5M", "5-10M", "10-20M", "20M+"]
CHANNEL_ORDER = ["branch", "agent", "mobile_app"]
BUREAU_BAND_ORDER = ["<500", "500-650", "650-750", "750-850", "850+"]
DTI_BAND_ORDER = ["<1x", "1-2x", "2-3x", "3x+"]


def eda_bar(csv_name: str, x_col: str, title: str, out_name: str, order: list[str] | None = None) -> None:
    df = pd.read_csv(DATA / csv_name)
    if order is not None:
        df[x_col] = pd.Categorical(df[x_col], categories=order, ordered=True)
        df = df.sort_values(x_col)
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(df[x_col], df["bad_rate_90"] * 100, color="#7c5cff")
    for bar, n in zip(bars, df["n"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, f"n={n}", ha="center", fontsize=8, color="#ccc")
    ax.set_ylabel("Bad rate 90+ DPD, %")
    ax.set_title(title)
    fig.patch.set_facecolor(BG)
    style_ax(ax)
    save(fig, out_name)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    income = out["declared_income_uzs"].replace(0, np.nan)
    term = out["term_months"].replace(0, np.nan)
    debt = out["existing_debt_uzs"].fillna(0)

    out["amount_to_income"] = out["requested_amount_uzs"] / income
    out["payment_to_income"] = (out["requested_amount_uzs"] / term) / income
    out["debt_to_income"] = debt / income
    out["total_burden"] = (out["requested_amount_uzs"] + debt) / income
    out["log_amount"] = np.log1p(out["requested_amount_uzs"])
    out["employment_years"] = out["employment_months"].fillna(0) / 12
    out["amount_per_job_year"] = out["requested_amount_uzs"] / (out["employment_years"] + 0.5)
    out["inq_per_loan"] = out["inq_cnt_6m"] / (out["active_loans_cnt"].fillna(0) + 1)
    out["debt_share"] = np.where(
        debt > 0,
        debt / out["requested_amount_uzs"].replace(0, np.nan),
        np.nan,
    )
    salary = out["salary_in_6m"].fillna(0)
    spend = out["spend_6m"].fillna(0)
    out["income_verified_ratio"] = np.where(salary > 0, salary / income, np.nan)
    out["spend_to_income"] = np.where(spend > 0, spend / income, np.nan)
    tx_total = out["txn_approved_6m"].fillna(0) + out["txn_declined_6m"].fillna(0)
    out["decline_rate"] = np.where(
        tx_total > 0, out["txn_declined_6m"].fillna(0) / tx_total, np.nan
    )
    high_risk_regions = ["Andijan", "Jizzakh"]
    out["is_mobile_app"] = (out["channel"] == "mobile_app").astype(int)
    out["high_risk_region"] = out["region"].isin(high_risk_regions).astype(int)
    out["is_premium"] = (out["customer_segment"] == "premium").astype(int)
    out["non_payroll_mobile"] = (
        (out["customer_segment"] != "payroll") & (out["channel"] == "mobile_app")
    ).astype(int)
    out["burden_x_mobile"] = out["amount_to_income"] * out["is_mobile_app"]
    out["burden_in_hot_region"] = out["amount_to_income"] * out["high_risk_region"]
    return out


NUM_FEATURES = [
    "requested_amount_uzs", "term_months", "declared_income_uzs", "employment_months",
    "age_at_decision", "bureau_score", "existing_debt_uzs", "active_loans_cnt",
    "inq_cnt_6m", "txn_approved_6m", "txn_declined_6m", "spend_6m",
    "salary_in_6m", "salary_to_declared_ratio",
    "amount_to_income", "payment_to_income", "debt_to_income", "total_burden", "log_amount",
    "employment_years", "amount_per_job_year", "inq_per_loan", "debt_share",
    "income_verified_ratio", "spend_to_income", "decline_rate",
    "is_mobile_app", "high_risk_region", "is_premium", "non_payroll_mobile",
    "burden_x_mobile", "burden_in_hot_region",
]


def correlation_with_target() -> None:
    """Bar chart: Pearson correlation of every numeric feature with target."""
    df = pd.read_csv(DATA / "modeling_dataset.csv")
    df = engineer_features(df[df["window_closed_12m"] == 1].copy())
    target = df["target_90"]
    corrs = {col: df[col].corr(target) for col in NUM_FEATURES}
    series = pd.Series(corrs).sort_values(key=lambda s: s.abs(), ascending=False)

    fig, ax = plt.subplots(figsize=(14, 5))
    colors = ["#ff6b6b" if v > 0 else "#4f8cff" for v in series.values]
    bars = ax.bar(range(len(series)), series.values, color=colors, width=0.75)
    ax.axhline(0, color="#666", lw=0.8)
    ax.set_xticks(range(len(series)))
    ax.set_xticklabels(series.index, rotation=90, ha="center", fontsize=7.5)
    ax.set_ylabel("Корреляция Пирсона с target")
    ax.set_ylim(-0.25, 0.25)
    ax.set_title("Корреляция всех числовых признаков с target (5 874 зрелых)")
    for bar, val in zip(bars, series.values):
        y = val + (0.008 if val >= 0 else -0.012)
        ax.text(bar.get_x() + bar.get_width() / 2, y, f"{val:.2f}", ha="center", va="bottom" if val >= 0 else "top", fontsize=6.5, color="#ccc")
    fig.patch.set_facecolor(BG)
    style_ax(ax)
    save(fig, "correlation_target.png")


def funnel_chart() -> None:
    labels = ["Заявки", "Одобрено", "Зрелое окно", "BAD 90+"]
    values = [18000, 11277, 5874, 656]
    fig, ax = plt.subplots(figsize=(6, 4))
    y = np.arange(len(labels))
    ax.barh(y, values, color=["#4f8cff", "#36cfc9", "#ffc53d", "#ff6b6b"])
    for i, (v, _) in enumerate(zip(values, labels)):
        ax.text(v + 200, i, f"{v:,}", va="center", color="white", fontsize=10)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title("Воронка данных")
    ax.set_xlabel("Количество")
    fig.patch.set_facecolor(BG)
    style_ax(ax)
    save(fig, "data_funnel.png")


def main() -> None:
    bad_rate_by_month()
    bad_rate_thresholds_by_month()
    eda_bar("eda_bad_by_channel.csv", "channel", "Bad rate по каналу", "bad_rate_by_channel.png", CHANNEL_ORDER)
    eda_bar("eda_bad_by_amount.csv", "amount_band", "Bad rate по сумме кредита", "bad_rate_by_amount.png", AMOUNT_BAND_ORDER)
    eda_bar("eda_bad_by_bureau.csv", "bureau_band", "Bad rate по скору бюро", "bad_rate_by_bureau.png", BUREAU_BAND_ORDER)
    eda_bar("eda_bad_by_dti.csv", "dti_band", "Bad rate по нагрузке (сумма ÷ доход)", "bad_rate_by_dti.png", DTI_BAND_ORDER)
    funnel_chart()
    correlation_with_target()
    print("done")


if __name__ == "__main__":
    main()
