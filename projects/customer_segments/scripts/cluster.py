"""Customer typology: preprocess, choose K, cluster, stability, economics.

Axes (not all columns):
  1. Intensity — txn and spend per month (personal window, so short history
     is not punished).
  2. Channel mix — POS / ecom / ATM shares (P2P omitted: shares sum to 1).
  3. Bank money — average balance and monthly net revenue.
  4. Depth — number of products.

Not used as clustering axes: age, gender, region, tenure (those would
split by who the person is / how long they have been a client, not by
how they use the card).
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
MODELS = ROOT / "models"
ASSETS = ROOT / "presentation" / "assets"
for p in (OUT, MODELS, ASSETS):
    p.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
K_RANGE = range(2, 9)
MIN_SHARE = 0.08  # a tariff line needs a real audience
CHOSEN_K = 4  # default; run() may override after metrics

CLUSTER_FEATURES = [
    "txn_per_month",
    "spend_per_month",
    "pos_share",
    "ecom_share",
    "atm_share",
    "avg_balance_uzs",
    "avg_monthly_revenue_uzs",
    "product_cnt",
    "recency_days",
]
LOG_COLS = ["txn_per_month", "spend_per_month", "avg_balance_uzs"]
WINSOR_COLS = LOG_COLS + ["avg_monthly_revenue_uzs", "recency_days"]

PROFILE_COLS = [
    "txn_per_month",
    "spend_per_month",
    "avg_ticket",
    "pos_share",
    "ecom_share",
    "p2p_share",
    "atm_share",
    "avg_balance_uzs",
    "avg_monthly_revenue_uzs",
    "net_revenue_uzs",
    "interchange_uzs",
    "float_income_uzs",
    "transfer_fee_uzs",
    "atm_cost_uzs",
    "product_cnt",
    "recency_days",
    "tenure_days",
    "window_days",
    "age_years",
]

MONTHLY_FEE = 15_000
WINDOW_MONTHS = 6


def load_active(path: Path | None = None) -> pd.DataFrame:
    path = path or (DATA / "features_active.csv")
    df = pd.read_csv(path)
    return df


def winsorize(s: pd.Series, p_low: float = 0.01, p_high: float = 0.99) -> pd.Series:
    lo, hi = s.quantile(p_low), s.quantile(p_high)
    return s.clip(lo, hi)


def make_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Log + winsorize. Returns transformed frame and clip bounds for new clients."""
    x = df[CLUSTER_FEATURES].copy()
    bounds = {}
    for col in WINSOR_COLS:
        lo, hi = float(x[col].quantile(0.01)), float(x[col].quantile(0.99))
        bounds[col] = {"lo": lo, "hi": hi}
        x[col] = x[col].clip(lo, hi)
    for col in LOG_COLS:
        x[col] = np.log1p(x[col].clip(lower=0))
    return x, bounds


def scale(x: pd.DataFrame, scaler: StandardScaler | None = None):
    if scaler is None:
        scaler = StandardScaler()
        z = scaler.fit_transform(x)
    else:
        z = scaler.transform(x)
    return z, scaler


def k_metrics(z: np.ndarray, seed: int = RANDOM_STATE) -> pd.DataFrame:
    rows = []
    n = len(z)
    sample = min(8000, n)
    rng = np.random.RandomState(seed)
    idx = rng.choice(n, size=sample, replace=False)
    for k in K_RANGE:
        km = KMeans(n_clusters=k, n_init=20, random_state=seed)
        labels = km.fit_predict(z)
        sizes = pd.Series(labels).value_counts()
        sil = silhouette_score(z[idx], labels[idx], metric="euclidean")
        rows.append(
            {
                "k": k,
                "inertia": float(km.inertia_),
                "silhouette": float(sil),
                "calinski_harabasz": float(calinski_harabasz_score(z, labels)),
                "davies_bouldin": float(davies_bouldin_score(z, labels)),
                "min_share": float(sizes.min() / n),
                "max_share": float(sizes.max() / n),
                "tiny": int((sizes / n < MIN_SHARE).sum()),
            }
        )
    return pd.DataFrame(rows)


def choose_k(metrics: pd.DataFrame) -> int:
    """Business first: every class large enough for a tariff. Then silhouette."""
    ok = metrics[metrics["tiny"] == 0]
    if ok.empty:
        ok = metrics.copy()
    # Prefer 4–5: enough types for a line, still explainable to a PM
    preferred = ok[ok["k"].isin([4, 5])]
    pool = preferred if len(preferred) else ok
    return int(pool.sort_values("silhouette", ascending=False).iloc[0]["k"])


def fit_kmeans(z: np.ndarray, k: int, seed: int = RANDOM_STATE) -> KMeans:
    km = KMeans(n_clusters=k, n_init=30, random_state=seed)
    km.fit(z)
    return km


def profiles(df: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    out = df.copy()
    out["cluster"] = labels
    med = out.groupby("cluster")[PROFILE_COLS].median()
    med["n"] = out.groupby("cluster").size()
    med["share"] = med["n"] / med["n"].sum()
    med["rev_sum"] = out.groupby("cluster")["net_revenue_uzs"].sum()
    return med.sort_index()


def auto_names(prof: pd.DataFrame) -> dict[int, str]:
    """Имена по отличию, не по номеру кластера.

    Порядок важен: сначала редкие и киты, иначе idxmax оборота заберёт
    не тот тип.
    """
    names: dict[int, str] = {}
    left = set(prof.index.astype(int))

    def take(col: str, how: str, name: str) -> None:
        if not left:
            return
        s = prof.loc[list(left), col]
        c = int(s.idxmin() if how == "min" else s.idxmax())
        names[c] = name
        left.remove(c)

    take("txn_per_month", "min", "Редкая карта")
    take("spend_per_month", "max", "Крупный оборот")
    take("ecom_share", "max", "Онлайн")
    take("avg_balance_uzs", "max", "Хранят деньги")
    for c in list(left):
        names[c] = "Повседневные"
    return names


def plot_k_metrics(metrics: pd.DataFrame, chosen: int) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    axes[0].plot(metrics["k"], metrics["inertia"], marker="o", color="#355f8c")
    axes[0].set_title("Inertia (локоть — не решение)")
    axes[0].set_xlabel("K")
    axes[1].plot(metrics["k"], metrics["silhouette"], marker="o", color="#355f8c")
    axes[1].axvline(chosen, color="#9a3b36", ls="--", lw=1)
    axes[1].set_title("Silhouette")
    axes[1].set_xlabel("K")
    axes[2].bar(metrics["k"], metrics["min_share"], color="#355f8c")
    axes[2].axhline(MIN_SHARE, color="#9a3b36", ls="--", lw=1)
    axes[2].set_title("Доля самого маленького класса")
    axes[2].set_xlabel("K")
    fig.tight_layout()
    fig.savefig(OUT / "k_metrics.png", dpi=140)
    fig.savefig(ASSETS / "k_metrics.png", dpi=140)
    plt.close(fig)


def plot_pca(z: np.ndarray, labels: np.ndarray, names: dict[int, str]) -> None:
    xy = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(z)
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    colors = ["#355f8c", "#2f6b64", "#9a3b36", "#8a6d3b", "#5c616b", "#6b4c7a"]
    for i, name in names.items():
        m = labels == i
        ax.scatter(
            xy[m, 0],
            xy[m, 1],
            s=8,
            alpha=0.45,
            c=colors[i % len(colors)],
            label=name,
            linewidths=0,
        )
    ax.set_xlabel("PCA-1 (смесь интенсивности и каналов)")
    ax.set_ylabel("PCA-2")
    ax.set_title("Активные клиенты в пространстве признаков")
    ax.legend(markerscale=3, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "pca_clusters.png", dpi=140)
    fig.savefig(ASSETS / "pca_clusters.png", dpi=140)
    plt.close(fig)


def plot_channels(prof: pd.DataFrame, names: dict[int, str]) -> None:
    shares = prof[["pos_share", "ecom_share", "p2p_share", "atm_share"]].copy()
    shares.index = [names[i] for i in shares.index]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    shares.plot(kind="barh", stacked=True, ax=ax, color=["#355f8c", "#2f6b64", "#8a6d3b", "#9a3b36"])
    ax.set_xlabel("Доля операций")
    ax.set_title("Каналы по типам")
    ax.legend(frameon=False, ncols=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "channel_mix.png", dpi=140)
    fig.savefig(ASSETS / "channel_mix.png", dpi=140)
    plt.close(fig)


def quartile_compare(df: pd.DataFrame, labels: np.ndarray, z: np.ndarray) -> pd.DataFrame:
    q = pd.qcut(df["spend_uzs"], 4, labels=["Q1", "Q2", "Q3", "Q4"])
    q_codes = pd.qcut(df["spend_uzs"], 4, labels=False).astype(int)
    n = min(8000, len(z))
    rng = np.random.RandomState(RANDOM_STATE)
    idx = rng.choice(len(z), size=n, replace=False)
    sil_ours = silhouette_score(z[idx], labels[idx])
    sil_q = silhouette_score(z[idx], q_codes.to_numpy()[idx])
    ct = pd.crosstab(pd.Series(labels, name="cluster"), q, normalize="index")
    # Inside top spend quartile, do channel mixes still differ?
    top = df.loc[q == "Q4"].copy()
    top["cluster"] = labels[q == "Q4"]
    mix = top.groupby("cluster")[["atm_share", "ecom_share", "pos_share", "avg_balance_uzs"]].median()
    mix.to_csv(OUT / "quartile_q4_mix.csv")
    summary = pd.DataFrame(
        [
            {"metric": "silhouette_our_types", "value": sil_ours},
            {"metric": "silhouette_spend_quartiles", "value": sil_q},
            {"metric": "ARI_types_vs_quartiles", "value": adjusted_rand_score(labels, q_codes)},
        ]
    )
    ct.to_csv(OUT / "quartile_crosstab.csv")
    summary.to_csv(OUT / "quartile_compare.csv", index=False)
    return summary


def stability(
    df: pd.DataFrame,
    x: pd.DataFrame,
    z: np.ndarray,
    labels: np.ndarray,
    k: int,
    scaler: StandardScaler,
    bounds: dict,
) -> pd.DataFrame:
    rows = []

    km_alt = fit_kmeans(z, k, seed=7)
    rows.append(
        {
            "check": "другой random_state (7 vs 42)",
            "ari": adjusted_rand_score(labels, km_alt.labels_),
            "n": len(labels),
        }
    )

    rng = np.random.RandomState(0)
    half = rng.choice(len(z), size=len(z) // 2, replace=False)
    km_half = fit_kmeans(z[half], k, seed=RANDOM_STATE)
    rows.append(
        {
            "check": "половина выборки (кластер vs исходные метки)",
            "ari": adjusted_rand_score(labels[half], km_half.labels_),
            "n": len(half),
        }
    )

    alt_cols = [c for c in CLUSTER_FEATURES if c not in ("avg_balance_uzs", "avg_monthly_revenue_uzs")]
    x_alt = x[alt_cols]
    z_alt, _ = scale(x_alt)
    km_feat = fit_kmeans(z_alt, k, seed=RANDOM_STATE)
    rows.append(
        {
            "check": "без баланса и дохода банка",
            "ari": adjusted_rand_score(labels, km_feat.labels_),
            "n": len(labels),
        }
    )

    alt_cols3 = [c for c in CLUSTER_FEATURES if c not in ("recency_days", "product_cnt")]
    x_alt3 = x[alt_cols3]
    z_alt3, _ = scale(x_alt3)
    km_feat3 = fit_kmeans(z_alt3, k, seed=RANDOM_STATE)
    rows.append(
        {
            "check": "без recency и числа продуктов",
            "ari": adjusted_rand_score(labels, km_feat3.labels_),
            "n": len(labels),
        }
    )

    alt_cols2 = [c for c in CLUSTER_FEATURES if c not in ("pos_share", "ecom_share", "atm_share")]
    z_alt2, _ = scale(x[alt_cols2])
    km_feat2 = fit_kmeans(z_alt2, k, seed=RANDOM_STATE)
    rows.append(
        {
            "check": "без долей каналов",
            "ari": adjusted_rand_score(labels, km_feat2.labels_),
            "n": len(labels),
        }
    )

    no_last = DATA / "features_active_no_last.csv"
    if no_last.exists():
        other = pd.read_csv(no_last)
        both = df[["customer_id"]].merge(
            other[["customer_id"] + CLUSTER_FEATURES],
            on="customer_id",
            suffixes=("", "_o"),
        )
        # rebuild matrix for the other window with its own scaler
        x2, _ = make_matrix(other.set_index("customer_id").loc[both["customer_id"]].reset_index())
        z2, _ = scale(x2)
        km2 = fit_kmeans(z2, k, seed=RANDOM_STATE)
        left = df.set_index("customer_id").loc[both["customer_id"]]
        # original labels aligned
        orig = pd.Series(labels, index=df["customer_id"]).loc[both["customer_id"]].to_numpy()
        rows.append(
            {
                "check": "окно без последнего месяца (as_of=2025-10-31)",
                "ari": adjusted_rand_score(orig, km2.labels_),
                "n": len(both),
            }
        )
    else:
        rows.append(
            {
                "check": "окно без последнего месяца (as_of=2025-10-31)",
                "ari": np.nan,
                "n": 0,
            }
        )

    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "stability_ari.csv", index=False)
    return tab


def holdout_rule(
    z: np.ndarray, labels: np.ndarray, k: int, x_model: pd.DataFrame, x_raw: pd.DataFrame
) -> dict:
    z_tr, z_te, y_tr, y_te, raw_tr, raw_te = train_test_split(
        z, labels, x_raw, test_size=0.2, random_state=RANDOM_STATE, stratify=labels
    )
    km = fit_kmeans(z_tr, k, seed=RANDOM_STATE)
    pred = km.predict(z_te)
    km_ind = fit_kmeans(z_te, k, seed=RANDOM_STATE)
    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, random_state=RANDOM_STATE)
    tree.fit(raw_tr, y_tr)
    rules = export_text(tree, feature_names=list(x_raw.columns), decimals=3)
    out = {
        "holdout_n": int(len(y_te)),
        "ari_nearest_centroid_vs_train_labels": float(adjusted_rand_score(y_te, pred)),
        "ari_independent_kmeans_on_holdout": float(adjusted_rand_score(pred, km_ind.labels_)),
        "tree_accuracy_holdout": float((tree.predict(raw_te) == y_te).mean()),
        "tree_rules": rules,
    }
    (OUT / "holdout.json").write_text(
        json.dumps({k2: v for k2, v in out.items() if k2 != "tree_rules"}, indent=2)
    )
    (OUT / "assignment_rules.txt").write_text(
        "Правило для нового клиента: те же 9 признаков за его персональное "
        "окно → winsorize 1–99% (границы с обучения) → log1p на тратах/операциях/остатке "
        "→ StandardScaler → ближайший центроид KMeans.\n\n"
        "Дерево ниже — шпаргалка для PM (глубина 3), не замена центроиду. "
        "Признаки в исходных единицах.\n\n"
        + rules
    )
    return out


def economics(df: pd.DataFrame, labels: np.ndarray, names: dict[int, str], inactive_n: int) -> pd.DataFrame:
    out = df.copy()
    out["cluster"] = labels
    out["segment"] = out["cluster"].map(names)
    g = out.groupby("segment", sort=False)
    fee_now = MONTHLY_FEE * WINDOW_MONTHS
    rows = []
    for name, part in g:
        n = len(part)
        rows.append(
            {
                "segment": name,
                "n": n,
                "share": n / (len(out) + inactive_n),
                "median_spend_month": part["spend_per_month"].median(),
                "median_balance": part["avg_balance_uzs"].median(),
                "median_txn_month": part["txn_per_month"].median(),
                "pos_share": part["pos_share"].median(),
                "ecom_share": part["ecom_share"].median(),
                "atm_share": part["atm_share"].median(),
                "net_revenue_6m": part["net_revenue_uzs"].sum(),
                "interchange_6m": part["interchange_uzs"].sum(),
                "float_6m": part["float_income_uzs"].sum(),
                "transfer_fee_6m": part["transfer_fee_uzs"].sum(),
                "atm_cost_6m": part["atm_cost_uzs"].sum(),
                "fee_revenue_6m": n * fee_now,
                "rev_per_client_6m": part["net_revenue_uzs"].mean(),
            }
        )
    rows.append(
        {
            "segment": "Спящие",
            "n": inactive_n,
            "share": inactive_n / (len(out) + inactive_n),
            "median_spend_month": 0,
            "median_balance": np.nan,
            "median_txn_month": 0,
            "pos_share": np.nan,
            "ecom_share": np.nan,
            "atm_share": np.nan,
            "net_revenue_6m": 0,
            "interchange_6m": 0,
            "float_6m": 0,
            "transfer_fee_6m": 0,
            "atm_cost_6m": 0,
            "fee_revenue_6m": inactive_n * fee_now,
            "rev_per_client_6m": 0,
        }
    )
    eco = pd.DataFrame(rows)
    eco.to_csv(OUT / "economics.csv", index=False)
    return eco


def propose_tariffs(eco: pd.DataFrame, names: dict[int, str], prof: pd.DataFrame) -> pd.DataFrame:
    """Офер по имени типа — не эвристика «кто больше ATM»."""
    by_name = {
        "Повседневные": (
            "Стандарт",
            15_000,
            "Оставить 15 000. Кэшбэк в grocery/POS. Это 42% базы — новый прайс их ломает.",
        ),
        "Онлайн": (
            "Онлайн",
            19_000,
            "Чуть выше плата и кэшбэк в ecom. Interchange с маркетплейсов уже кормит этот тип.",
        ),
        "Крупный оборот": (
            "Премиум",
            30_000,
            "Абонентка 15к для них копейки (медиана дохода банка ~350 тыс./мес.). Премиум-сервис, высокий лимит ATM, кэшбэк. Не пугать дешёвым «наличным» тарифом.",
        ),
        "Хранят деньги": (
            "Остаток",
            20_000,
            "Плата чуть выше плюс ставка/пакет на остаток. Основной доход — float, не операции.",
        ),
        "Редкая карта": (
            "Лайт",
            5_000,
            "Сейчас абонентка 15к при ~1 операции в месяц. Либо уйдут, либо карта мёртвая. Лайт без кэшбэка.",
        ),
        "Спящие": (
            "Пауза",
            0,
            "Не брать 15 000 с карты без операций. Раз в квартал одно сообщение, что карта жива.",
        ),
    }
    rows = []
    for _, row in eco.iterrows():
        seg = row["segment"]
        tariff, fee, hook = by_name.get(seg, ("Стандарт", 15_000, "Оставить как есть."))
        n = int(row["n"])
        fee_now_year = n * MONTHLY_FEE * 12
        fee_new_year = n * fee * 12
        rows.append(
            {
                "segment": seg,
                "tariff": tariff,
                "monthly_fee_uzs": fee,
                "n": n,
                "fee_now_year_uzs": fee_now_year,
                "fee_new_year_uzs": fee_new_year,
                "fee_delta_year_uzs": fee_new_year - fee_now_year,
                "net_revenue_6m": row["net_revenue_6m"],
                "hook": hook,
            }
        )
    off = pd.DataFrame(rows)
    off.to_csv(OUT / "tariff_offers.csv", index=False)
    return off


def run(chosen_k: int | None = None) -> dict:
    df = load_active()
    inactive_n = 0
    inactive_path = DATA / "features_inactive.csv"
    if inactive_path.exists():
        inactive_n = len(pd.read_csv(inactive_path))

    x, bounds = make_matrix(df)
    z, scaler = scale(x)
    metrics = k_metrics(z)
    metrics.to_csv(OUT / "k_metrics.csv", index=False)
    k = chosen_k or choose_k(metrics)
    plot_k_metrics(metrics, k)

    km = fit_kmeans(z, k)
    labels = km.labels_
    lab4 = fit_kmeans(z, 4).labels_
    (OUT / "k_choice.json").write_text(
        json.dumps(
            {
                "chosen_k": k,
                "ari_vs_k4": float(adjusted_rand_score(labels, lab4)),
                "why_not_k6": "K=6 даёт класс < 3% — под него нельзя заводить тариф",
                "why_not_k4": (
                    "На K=4 «хранят деньги» (мало операций, большой остаток) "
                    "сливаются с «крупным оборотом». Это разные продукты."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    prof = profiles(df, labels)
    names = auto_names(prof)
    prof.insert(0, "segment", [names[i] for i in prof.index])
    prof.to_csv(OUT / "cluster_profiles.csv")

    plot_pca(z, labels, names)
    plot_channels(prof, names)

    qtab = quartile_compare(df, labels, z)
    stab = stability(df, x, z, labels, k, scaler, bounds)
    hold = holdout_rule(z, labels, k, x, df[CLUSTER_FEATURES])
    eco = economics(df, labels, names, inactive_n)
    offers = propose_tariffs(eco, names, prof)

    assign = df[["customer_id"]].copy()
    assign["cluster"] = labels
    assign["segment"] = assign["cluster"].map(names)
    assign.to_csv(OUT / "assignments.csv", index=False)

    joblib.dump(
        {
            "k": k,
            "features": CLUSTER_FEATURES,
            "log_cols": LOG_COLS,
            "bounds": bounds,
            "scaler": scaler,
            "kmeans": km,
            "names": names,
        },
        MODELS / "segment_pipeline.joblib",
    )

    summary = {
        "n_active": int(len(df)),
        "n_inactive": int(inactive_n),
        "k": int(k),
        "names": names,
        "silhouette": float(metrics.loc[metrics["k"] == k, "silhouette"].iloc[0]),
        "min_share": float(metrics.loc[metrics["k"] == k, "min_share"].iloc[0]),
        "quartile": qtab.to_dict(orient="records"),
        "stability": stab.to_dict(orient="records"),
        "holdout": {kk: vv for kk, vv in hold.items() if kk != "tree_rules"},
    }
    (OUT / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str)
    )
    print(f"K={k} names={names}")
    print(metrics.to_string(index=False))
    print(stab.to_string(index=False))
    return summary


if __name__ == "__main__":
    run()
