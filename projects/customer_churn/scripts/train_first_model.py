"""Fit a first LightGBM on July, evaluate September OOT, save importance plot."""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.inspection import permutation_importance

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data" / "model"
ASSETS = PROJECT / "presentation" / "assets"

JUL = pd.Timestamp("2025-07-31")
SEP = pd.Timestamp("2025-09-30")

CAT = ["gender", "region", "acq_channel", "segment"]
DROP = ["customer_id", "snapshot_date", "target"]

# Human labels for the deck (not raw column names).
LABELS = {
    "days_since_last_txn": "Дней без успешной операции",
    "txn_cnt_30d": "Операций за 30 дней",
    "txn_cnt_prev_30d": "Операций в предыдущие 30 дней",
    "txn_ratio_30d": "Динамика операций 30д",
    "spend_30d": "Оборот за 30 дней",
    "spend_prev_30d": "Оборот в предыдущие 30 дней",
    "spend_ratio_30d": "Динамика оборота 30д",
    "avg_ticket_30d": "Средний чек 30д",
    "txn_all_cnt_30d": "Операций за 30 дней (все)",
    "declined_cnt_30d": "Отклонений за 30 дней",
    "decline_rate_30d": "Доля отказов за 30 дней",
    "salary_in_30d": "Зарплатных зачислений за 30д",
    "app_cnt_30d": "Событий в приложении за 30д",
    "app_login_30d": "Входов в приложение за 30д",
    "app_support_chat_30d": "Чат поддержки в приложении",
    "days_since_last_app": "Дней без приложения",
    "cards_cnt": "Число карт",
    "cards_blocked_cnt": "Заблокированных карт",
    "cards_credit_cnt": "Кредитных карт",
    "products_open_cnt": "Открытых продуктов",
    "products_closed_90d": "Закрытых продуктов за 90д",
    "product_events_30d": "Событий по продуктам за 30д",
    "tickets_90d": "Тикетов за 90 дней",
    "tickets_30d": "Тикетов за 30 дней",
    "fee_complaint_90d": "Жалоб на комиссию за 90д",
    "tickets_open_cnt": "Незакрытых тикетов",
    "csat_mean": "Оценка поддержки",
    "has_active_sub": "Активная подписка",
    "sub_canceled": "Подписка уже отменена",
    "failed_charges_90d": "Неуспешных списаний за 90д",
    "charge_fail_rate_90d": "Доля фейлов списаний",
    "tariff_hike": "Попал под повышение тарифа",
    "fee_hike_uzs": "На сколько выросла комиссия",
    "campaigns_ever": "Кампании удержания ранее",
    "campaigns_90d": "Кампании за 90 дней",
    "tenure_days": "Стаж в банке",
    "age_years": "Возраст",
    "is_payroll": "Зарплатный клиент",
    "log_income": "Лог заявленного дохода",
    "segment": "Сегмент",
    "region": "Регион",
    "acq_channel": "Канал привлечения",
    "gender": "Пол",
}

# Light muted palette (matches presentation).
BG = "#f2f2f0"
INK = "#3a3a38"
MUTED = "#6e6e68"
SLATE = "#5c6b78"
BAR = "#6a7a88"


def split_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = df.drop(columns=[c for c in DROP if c in df.columns]).copy()
    for c in CAT:
        X[c] = X[c].astype("category")
    y = df["target"].astype(int)
    return X, y


def cv_scores(X: pd.DataFrame, y: pd.Series, params: dict) -> dict:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    aucs, aps = [], []
    for tr, va in skf.split(X, y):
        m = lgb.LGBMClassifier(**params)
        m.fit(X.iloc[tr], y.iloc[tr], categorical_feature=CAT)
        p = m.predict_proba(X.iloc[va])[:, 1]
        aucs.append(roc_auc_score(y.iloc[va], p))
        aps.append(average_precision_score(y.iloc[va], p))
    return {
        "july_cv_auc_mean": float(np.mean(aucs)),
        "july_cv_auc_std": float(np.std(aucs)),
        "july_cv_ap_mean": float(np.mean(aps)),
        "july_cv_ap_std": float(np.std(aps)),
    }


def write_importance_svg(names: list[str], values: np.ndarray, path: Path, title: str) -> None:
    n = len(names)
    row_h = 28
    left, right, top, bot = 280, 36, 48, 28
    width = 720
    height = top + n * row_h + bot
    vmax = max(float(values.max()), 1e-9)
    bar_max = width - left - right

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        f'<text x="{left}" y="28" fill="{MUTED}" font-size="13" font-family="system-ui, sans-serif">{title}</text>',
    ]
    for i, (name, val) in enumerate(zip(names, values)):
        y = top + i * row_h
        w = bar_max * (float(val) / vmax)
        lab = LABELS.get(name, name)
        parts.append(
            f'<text x="{left - 12}" y="{y + 16}" text-anchor="end" fill="{INK}" '
            f'font-size="13" font-family="system-ui, sans-serif">{lab}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{w:.1f}" height="16" fill="{BAR}" rx="1"/>'
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")
    print("wrote", path)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA / "features_60d.csv", parse_dates=["snapshot_date"])
    jul = df.loc[df["snapshot_date"] == JUL].copy()
    sep = df.loc[df["snapshot_date"] == SEP].copy()
    Xj, yj = split_xy(jul)
    Xs, ys = split_xy(sep)

    pos = int(yj.sum())
    neg = int(len(yj) - pos)
    params = dict(
        n_estimators=250,
        learning_rate=0.05,
        num_leaves=24,
        min_child_samples=80,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=-1,
        scale_pos_weight=neg / max(pos, 1),
    )

    print("5-fold CV on July…")
    cv = cv_scores(Xj, yj, params)

    print("fit July, score September…")
    model = lgb.LGBMClassifier(**params)
    model.fit(Xj, yj, categorical_feature=CAT)
    pj = model.predict_proba(Xj)[:, 1]
    ps = model.predict_proba(Xs)[:, 1]

    gain = pd.Series(model.booster_.feature_importance(importance_type="gain"), index=Xj.columns)
    gain = gain.sort_values(ascending=False)

    print("permutation importance on September (OOT)…")
    perm = permutation_importance(
        model, Xs, ys, n_repeats=8, random_state=42, scoring="roc_auc", n_jobs=-1
    )
    perm_s = pd.Series(perm.importances_mean, index=Xs.columns).sort_values(ascending=False)

    metrics = {
        "july_n": int(len(yj)),
        "july_churn_rate": float(yj.mean()),
        "sep_n": int(len(ys)),
        "sep_churn_rate": float(ys.mean()),
        "july_insample_auc": float(roc_auc_score(yj, pj)),
        "july_insample_ap": float(average_precision_score(yj, pj)),
        "sep_oot_auc": float(roc_auc_score(ys, ps)),
        "sep_oot_ap": float(average_precision_score(ys, ps)),
        "sep_base_ap": float(ys.mean()),
        **cv,
        "top_gain": [{"feature": k, "label": LABELS.get(k, k), "gain": float(v)} for k, v in gain.head(12).items()],
        "top_perm_oot": [
            {"feature": k, "label": LABELS.get(k, k), "auc_drop": float(v)}
            for k, v in perm_s.head(12).items()
        ],
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    gain.reset_index().rename(columns={"index": "feature", 0: "gain"}).to_csv(DATA / "importance_gain.csv", index=False)
    perm_s.reset_index().rename(columns={"index": "feature", 0: "perm_auc"}).to_csv(
        DATA / "importance_perm.csv", index=False
    )

    top = perm_s.head(10)
    write_importance_svg(
        list(top.index),
        top.to_numpy(),
        ASSETS / "importance_perm.svg",
        "Permutation importance · сентябрь OOT · падение ROC-AUC",
    )
    top_g = gain.head(10)
    write_importance_svg(
        list(top_g.index),
        top_g.to_numpy(),
        ASSETS / "importance.svg",
        "LightGBM gain · обучение на июле",
    )
    print(json.dumps({k: metrics[k] for k in metrics if k not in ("top_gain", "top_perm_oot")}, indent=2))
    print("top perm OOT:")
    print(perm_s.head(8).to_string())
    print("wrote", DATA / "metrics.json")


if __name__ == "__main__":
    main()
