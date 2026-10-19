"""Tariff slide: peak sits on the June snapshot because its 60-day window already sees 1 July."""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT / "presentation" / "assets"
SLIDE, INK, MUTED, DIM = "#e6e2da", "#2d3038", "#5c616b", "#7a7f88"
ACCENT, WARN, LINE = "#355f8c", "#9a3b36", "#cfcbc4"

f = pd.read_csv(PROJECT / "data" / "targets" / "funnel_60d_usage.csv", parse_dates=["snapshot_date"])
f = f.loc[f["horizon_closed"]].copy()
months = ["мар", "апр", "май", "июнь", "июль", "авг", "сен", "окт"]
x = np.arange(len(f))
usage = f["usage_churn_rate"] * 100
silence = f["silence_churn_rate"] * 100

plt.rcParams.update({
    "font.size": 12, "text.color": INK, "axes.labelcolor": MUTED,
    "axes.edgecolor": LINE, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.facecolor": SLIDE, "figure.facecolor": SLIDE, "axes.linewidth": 0.9,
    "axes.titlesize": 14, "axes.titlelocation": "left", "axes.titlecolor": INK, "axes.titlepad": 10,
})
fig, ax = plt.subplots(figsize=(12.8, 5.0))
ax.axvspan(2.55, 3.45, color=WARN, alpha=0.12, zorder=0)
ax.plot(x, usage, color=ACCENT, lw=2.8, marker="o", ms=7, label="наш отток", zorder=3)
ax.plot(x, silence, color=DIM, lw=1.6, ls="--", marker="o", ms=4.5, label="просто 60 дней без операций", zorder=2)
ax.annotate(
    f"{usage.iloc[3]:.1f}%\nв эти 60 дней уже был новый тариф".replace(".", ","),
    xy=(3, usage.iloc[3]),
    xytext=(0.35, 20.2),
    fontsize=12,
    color=ACCENT,
    fontweight="bold",
    arrowprops=dict(arrowstyle="-", color=ACCENT, lw=1),
)
ax.set_xticks(x)
ax.set_xticklabels(months)
for tick, lab in zip(ax.get_xticklabels(), months):
    if lab == "июнь":
        tick.set_color(WARN)
        tick.set_fontweight("bold")
ax.set_ylabel("доля оттока")
ax.set_ylim(0, 24)
ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(frameon=False, loc="upper left", fontsize=11, labelcolor=MUTED)
ax.set_title("Пик в июне: срез 30 июня смотрит вперёд — и уже видит тариф 1 июля")
fig.savefig(ASSETS / "tariff.png", facecolor=SLIDE, bbox_inches="tight", pad_inches=0.22, dpi=180)
print("wrote", ASSETS / "tariff.png")
