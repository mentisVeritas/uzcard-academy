"""Charts for Part 1 (target) slides. Numbers come from data/targets and useful CSVs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data_raw" / "useful"
TARGETS = PROJECT / "data" / "targets"
ASSETS = PROJECT / "presentation" / "assets"

BG = "#0f172a"
CARD = "#1e293b"
TEXT = "#f1f5f9"
MUTED = "#94a3b8"
GRID = "#334155"
CYAN = "#38bdf8"
RED = "#f87171"
AMBER = "#fbbf24"
GREEN = "#34d399"
WHITE = "#e2e8f0"

N_COLORS = {30: RED, 45: AMBER, 60: GREEN}


def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": CARD,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT,
            "axes.titlecolor": TEXT,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": TEXT,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "grid.alpha": 0.85,
            "font.size": 16,
            "axes.titlesize": 20,
            "axes.labelsize": 16,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
            "legend.fontsize": 14,
            "figure.dpi": 140,
            "savefig.dpi": 160,
            "savefig.facecolor": BG,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": True,
            "axes.spines.bottom": True,
            "legend.frameon": False,
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    path = ASSETS / name
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


def chart_gaps(act: pd.DataFrame) -> dict:
    s = act.sort_values(["customer_id", "d"])
    s["prev"] = s.groupby("customer_id")["d"].shift(1)
    s["gap"] = (s["d"] - s["prev"]).dt.days
    gaps = s["gap"].dropna()
    gaps = gaps[gaps > 0]

    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    bins = np.arange(1, 81)
    ax.hist(gaps.clip(upper=80), bins=bins, color=CYAN, alpha=0.9, edgecolor=BG, linewidth=0.2)
    for n, c, lab in ((30, RED, "30"), (45, AMBER, "45"), (60, GREEN, "60")):
        ax.axvline(n, color=c, linewidth=2.4, linestyle="--", label=f"{lab} дней")
    med = float(gaps.median())
    p99 = float(gaps.quantile(0.99))
    ax.axvline(med, color=WHITE, linewidth=1.8, linestyle=":", label=f"медиана {med:.0f} дн.")
    ax.set_xlim(0, 80)
    ax.text(
        0.98,
        0.28,
        f"медиана  {med:.0f} дн.\n95-й перц.  {gaps.quantile(0.95):.0f}\n99-й перц.  {p99:.0f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=14,
        color=TEXT,
        linespacing=1.45,
        bbox=dict(boxstyle="round,pad=0.45", facecolor=BG, edgecolor=GRID),
    )
    ax.set_xlabel("Пауза между соседними успешными операциями, дни")
    ax.set_ylabel("Число пауз")
    ax.set_title("Обычная пауза короткая. 30 / 45 / 60 — уже хвост")
    ax.legend(loc="upper right", labelcolor=TEXT)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", " ")))
    save(fig, "gaps.png")
    return {"median": med, "p95": float(gaps.quantile(0.95)), "p99": p99, "n_gaps": int(len(gaps))}


def chart_returned(cmp_: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    ns = cmp_["silence_days"].astype(int).tolist()
    vals = (cmp_["labeled_churn_then_returned_jul"] * 100).tolist()
    colors = [N_COLORS[n] for n in ns]
    bars = ax.bar([f"{n} дней" for n in ns], vals, color=colors, width=0.62)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Доля, %")
    ax.set_title("Срез 31 июля: назвали «ушёл» — а человек снова платил")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=0))
    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 2.5,
            f"{v:.0f}%",
            ha="center",
            va="bottom",
            fontsize=22,
            fontweight="bold",
            color=TEXT,
        )
    ax.axhline(50, color=GRID, linewidth=1, linestyle=":")
    save(fig, "returned.png")


def chart_rates(funnel: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    closed = funnel[funnel["horizon_closed"]].copy()
    closed["snapshot_date"] = pd.to_datetime(closed["snapshot_date"])
    # Nov is closed only for 30d — compare on shared months Mar–Oct
    ok = closed.loc[closed["silence_days"] == 60, "snapshot_date"]
    closed = closed[closed["snapshot_date"].isin(ok)]
    month_ru = {3: "мар", 4: "апр", 5: "май", 6: "июн", 7: "июл", 8: "авг", 9: "сен", 10: "окт"}
    labels = {30: "30 дней", 45: "45 дней", 60: "60 дней"}
    x_ref = None
    for n, g in closed.groupby("silence_days"):
        g = g.sort_values("snapshot_date")
        x = np.arange(len(g))
        x_ref = g
        ax.plot(
            x,
            g["churn_rate"] * 100,
            marker="o",
            linewidth=2.6,
            markersize=8,
            color=N_COLORS[int(n)],
            label=labels[int(n)],
        )
    assert x_ref is not None
    ax.axvspan(2.5, 4.5, color=RED, alpha=0.12)
    ax.axvline(3.35, color=RED, linewidth=1.6, linestyle="--")
    ax.text(3.45, 11.6, "тариф 1 июля", color=RED, fontsize=13)
    ax.set_xticks(np.arange(len(x_ref)))
    ax.set_xticklabels([month_ru[d.month] for d in x_ref["snapshot_date"]])
    ax.set_ylabel("Доля оттока, %")
    ax.set_title("Отток по месяцам: рост в июне–июле на всех трёх порогах")
    ax.legend(loc="upper right", labelcolor=TEXT)
    ax.set_ylim(3, 13)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f"))
    save(fig, "churn_rate.png")


def chart_funnel() -> dict:
    # Sequential remaining counts for 2025-07-31, N=60.
    # signup_after ⊂ no_history, so 20_000 − 1_691 − 2_165 − 695 − 3_357 = 12_092
    rows = [
        ("Все клиенты", 20000, CYAN, ""),
        ("Зарегистрированы к срезу", 18309, MUTED, "−1 691 ещё не в банке"),
        ("Есть история операций", 16144, MUTED, "−2 165 без операций"),
        ("Стаж ≥ 60 дней", 15449, MUTED, "−695 новичков"),
        ("Когорта: не молчит > 60 дн.", 12092, GREEN, "−3 357 уже тишина"),
    ]
    fig, ax = plt.subplots(figsize=(11.2, 6.0))
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [r[2] for r in rows]
    bars = ax.barh(labels[::-1], vals[::-1], color=colors[::-1], height=0.68)
    ax.set_xlabel("Клиентов")
    ax.set_title("Срез 31 июля, N = 60: кого оставили в когорте")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", " ")))
    notes = [r[3] for r in rows]
    for bar, n, note in zip(bars, vals[::-1], notes[::-1]):
        ax.text(
            n + 280,
            bar.get_y() + bar.get_height() / 2,
            f"{n:,}".replace(",", " ") + (f"   {note}" if note else ""),
            va="center",
            fontsize=14,
            color=TEXT,
        )
    ax.set_xlim(0, 28000)
    save(fig, "funnel.png")
    return {"rows": rows}


def chart_tariff(tariff: pd.DataFrame) -> dict:
    old = float(tariff["old_monthly_fee_uzs"].mean())
    new = float(tariff["new_monthly_fee_uzs"].mean())
    n = int(len(tariff))
    fig, ax = plt.subplots(figsize=(11.2, 5.4))
    bars = ax.bar(["До 1 июля", "После 1 июля"], [old, new], color=[CYAN, RED], width=0.55)
    ax.set_ylabel("Средняя комиссия, сум / мес.")
    ax.set_title(f"tariff_revision_2025: комиссия выросла ~в 3 раза ({n:,} клиентов)".replace(",", " "))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", " ")))
    for bar, v in zip(bars, (old, new)):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 600,
            f"{v/1000:.1f} тыс.",
            ha="center",
            fontsize=22,
            fontweight="bold",
            color=TEXT,
        )
    ax.set_ylim(0, new * 1.25)
    save(fig, "tariff.png")
    return {"n": n, "old": old, "new": new, "ratio": new / old if old else np.nan}


def chart_volume(act: pd.DataFrame) -> dict:
    m = act.copy()
    m["month"] = m["d"].dt.to_period("M").dt.to_timestamp()
    m["year"] = m["d"].dt.year
    m["mon"] = m["d"].dt.month
    g = m.groupby(["year", "mon"], as_index=False)["size"].sum()
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    for year, c, lw in ((2024, MUTED, 2.2), (2025, CYAN, 2.8)):
        s = g[g["year"] == year].sort_values("mon")
        ax.plot(s["mon"], s["size"], marker="o", color=c, linewidth=lw, markersize=7, label=str(year))
    ax.axvline(7, color=RED, linestyle="--", linewidth=1.6)
    ax.text(7.12, g["size"].max() * 0.92, "июль", color=RED, fontsize=13)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"])
    ax.set_ylabel("Успешных операций")
    ax.set_title("Июльский провал есть и в 2024: не только тариф")
    ax.legend(loc="upper right", labelcolor=TEXT)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", " ")))
    save(fig, "volume.png")
    jul = g[(g["mon"] == 7)].set_index("year")["size"].to_dict()
    return {"july": jul}


def load_activity() -> pd.DataFrame:
    txn = pd.read_csv(RAW / "churn_transactions.csv", parse_dates=["txn_ts"], usecols=["customer_id", "txn_ts", "status"])
    ok = txn.loc[txn["status"] == "approved", ["customer_id", "txn_ts"]].copy()
    ok["d"] = ok["txn_ts"].dt.normalize()
    return ok.groupby(["customer_id", "d"], as_index=False).size()


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    style()
    print("loading transactions…")
    act = load_activity()
    cmp_ = pd.read_csv(TARGETS / "compare_30_45_60.csv")
    funnel = pd.read_csv(TARGETS / "funnel_by_snapshot.csv")
    tariff = pd.read_csv(RAW / "churn_tariff_changes.csv")

    gap = chart_gaps(act)
    chart_returned(cmp_)
    chart_rates(funnel)
    fun = chart_funnel()
    tar = chart_tariff(tariff)
    vol = chart_volume(act)
    print("gap", gap)
    print("tariff", tar)
    print("funnel", fun)
    print("volume july", vol)


if __name__ == "__main__":
    main()
