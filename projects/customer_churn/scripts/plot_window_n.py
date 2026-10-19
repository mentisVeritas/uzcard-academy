"""Usage churn by month for horizon 30 / 40 / 50 / 60 days. Same July-style cohort."""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT / "presentation" / "assets"
TARGETS = PROJECT / "data" / "targets"
RAW = PROJECT / "data_raw" / "useful"
DUMP = pd.Timestamp("2025-12-31")
NS = (30, 40, 50, 60)
MIN_TXN = 3
TRAIN = pd.Timestamp("2025-07-31")
SLIDE, INK, MUTED = "#e6e2da", "#2d3038", "#5c616b"
COLORS = {30: "#9a3b36", 40: "#8a6a32", 50: "#355f8c", 60: "#2f6b64"}


def main() -> None:
    cohort = pd.read_csv(TARGETS / "target_60d_usage.csv", parse_dates=["snapshot_date"])
    txn = pd.read_csv(RAW / "churn_transactions.csv", usecols=["customer_id", "txn_ts", "amount_uzs", "status"])
    ok = txn.loc[txn["status"] == "approved", ["customer_id", "txn_ts", "amount_uzs"]].copy()
    ok["d"] = pd.to_datetime(ok["txn_ts"]).dt.normalize()

    snaps = sorted(pd.to_datetime(cohort["snapshot_date"].unique()))
    floors = {}
    rows = []

    def window_frame(snap: pd.Timestamp, n: int) -> pd.DataFrame:
        ids = cohort.loc[cohort["snapshot_date"] == snap, "customer_id"]
        end = snap + pd.Timedelta(days=int(n))
        post = ok[(ok["d"] > snap) & (ok["d"] <= end) & ok["customer_id"].isin(ids)]
        g = post.groupby("customer_id").agg(cnt=("amount_uzs", "size"), spend=("amount_uzs", "sum"))
        df = pd.DataFrame({"customer_id": ids.unique()}).merge(g, on="customer_id", how="left")
        df["cnt"] = df["cnt"].fillna(0)
        df["spend"] = df["spend"].fillna(0)
        return df

    for n in NS:
        july = window_frame(TRAIN, n)
        floors[n] = float(july.loc[july["cnt"] >= MIN_TXN, "spend"].quantile(0.05))
        for snap in snaps:
            if snap + pd.Timedelta(days=int(n)) > DUMP:
                continue
            df = window_frame(snap, n)
            floor = floors[n]
            churn = ((df["cnt"] < MIN_TXN) | (df["spend"] < floor)).mean()
            rows.append(
                {
                    "n": n,
                    "snapshot": snap,
                    "churn": churn,
                    "floor": floor,
                    "cohort": len(df),
                }
            )

    out = pd.DataFrame(rows)
    print(out.pivot(index="snapshot", columns="n", values="churn").round(3).to_string())
    print("p5 floors:", {k: int(v) for k, v in floors.items()})

    months = ["мар", "апр", "май", "июн", "июл", "авг", "сен", "окт"]
    fig, ax = plt.subplots(figsize=(13.4, 5.1))
    plt.rcParams.update({"font.family": "Arial", "font.size": 12})
    fig.patch.set_facecolor(SLIDE)
    ax.set_facecolor(SLIDE)
    ax.axvspan(2.5, 4.5, color="#9a3b36", alpha=0.08, zorder=0)
    ax.text(3.5, 0.335, "тариф в горизонте", ha="center", color="#9a3b36", fontsize=11)
    for n in NS:
        sub = out.loc[out["n"] == n].sort_values("snapshot")
        y = sub["churn"].to_numpy() * 100
        x = np.arange(len(sub))
        lw = 2.8 if n == 60 else 1.8
        ax.plot(x, y, color=COLORS[n], lw=lw, marker="o", ms=6, label=f"{n} дней", zorder=3)
        if n == 60:
            ax.text(x[4], y[4] + 0.7, f"{y[4]:.1f}%", ha="center", fontsize=11, color=COLORS[n], fontweight="bold")
    ax.set_xticks(np.arange(len(months)))
    ax.set_xticklabels(months)
    ax.set_ylabel("доля оттока")
    ax.set_ylim(8, 36)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, ncol=4, loc="upper right", fontsize=11, labelcolor=MUTED)
    ax.set_title("Тот же ярлык (3 операции + p5), меняется только длина окна")
    ax.set_xlabel("срез t0  ·  когорта одна и та же")
    path = ASSETS / "window_n.png"
    fig.savefig(path, facecolor=SLIDE, bbox_inches="tight", pad_inches=0.22, dpi=180)
    print("wrote", path)


if __name__ == "__main__":
    main()
