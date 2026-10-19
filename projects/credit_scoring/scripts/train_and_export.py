"""Train models with v2 FE and export figures for presentation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import RocCurveDisplay, roc_auc_score, roc_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

optuna.logging.set_verbosity(optuna.logging.WARNING)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
FIG = ROOT / "presentation" / "figures"
OUT.mkdir(exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

TARGET = "target_90"
N_OPTUNA_TRIALS = 25
BG, FG = "#0f1117", "white"


def style_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    ax.figure.patch.set_facecolor(BG)
    ax.title.set_color(FG)
    ax.xaxis.label.set_color(FG)
    ax.yaxis.label.set_color(FG)
    ax.tick_params(colors=FG)
    for spine in ax.spines.values():
        spine.set_color("#333")
    leg = ax.get_legend()
    if leg:
        leg.get_frame().set_facecolor(BG)
        for t in leg.get_texts():
            t.set_color(FG)


def metrics(y_true, y_score):
    auc = roc_auc_score(y_true, y_score)
    fpr, tpr, _ = roc_curve(y_true, y_score)
    return {"auc": round(auc, 4), "gini": round(2 * auc - 1, 4), "ks": round((tpr - fpr).max(), 4)}


def engineer_features(d: pd.DataFrame) -> pd.DataFrame:
    out = d.copy()
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
        debt > 0, debt / out["requested_amount_uzs"].replace(0, np.nan), np.nan
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


CAT = ["channel", "purpose", "gender", "region", "customer_segment"]
NUM_BASE = [
    "requested_amount_uzs", "term_months", "declared_income_uzs", "employment_months",
    "age_at_decision", "bureau_score", "existing_debt_uzs", "active_loans_cnt",
    "inq_cnt_6m", "txn_approved_6m", "txn_declined_6m", "spend_6m",
    "salary_in_6m", "salary_to_declared_ratio",
]
NUM_ENG = [
    "amount_to_income", "payment_to_income", "debt_to_income", "total_burden", "log_amount",
    "employment_years", "amount_per_job_year", "inq_per_loan", "debt_share",
    "income_verified_ratio", "spend_to_income", "decline_rate",
    "is_mobile_app", "high_risk_region", "is_premium", "non_payroll_mobile",
    "burden_x_mobile", "burden_in_hot_region",
]
NUM = NUM_BASE + NUM_ENG


def make_prep(cat_cols, num_cols):
    return ColumnTransformer([
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_cols),
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), num_cols),
    ])


def make_xy(part, num_cols):
    return part[CAT + num_cols], part[TARGET].astype(int)


def eval_model(model, x_train, y_train, x_valid, y_valid, x_test, y_test, name):
    model.fit(x_train, y_train)
    preds = {
        s: model.predict_proba(x)[:, 1]
        for s, x in [("train", x_train), ("valid", x_valid), ("test", x_test)]
    }
    rows = []
    for split, y in [("train", y_train), ("valid", y_valid), ("test", y_test)]:
        rows.append({"model": name, "split": split, **metrics(y, preds[split])})
    return model, preds, rows


def decile_table(y, score):
    d = pd.DataFrame({"y": y, "score": score})
    d["decile"] = pd.qcut(d["score"], 10, labels=False, duplicates="drop") + 1
    return d.groupby("decile").agg(n=("y", "count"), bad_rate=("y", "mean")).reset_index()


def main() -> None:
    df = engineer_features(
        pd.read_csv(DATA / "modeling_dataset.csv", parse_dates=["decision_date", "issue_date"])
    )
    df = df[df["window_closed_12m"] == 1].copy()

    train = df[df["issue_date"] <= "2024-02-29"]
    valid = df[(df["issue_date"] > "2024-02-29") & (df["issue_date"] <= "2024-04-30")]
    test = df[df["issue_date"] > "2024-04-30"]

    num_baseline = NUM_BASE + ["amount_to_income"]
    X_train_b, y_train = make_xy(train, num_baseline)
    X_valid_b, y_valid = make_xy(valid, num_baseline)
    X_test_b, y_test = make_xy(test, num_baseline)
    X_train, _ = make_xy(train, NUM)
    X_valid, _ = make_xy(valid, NUM)
    X_test, _ = make_xy(test, NUM)

    baseline = Pipeline([
        ("prep", make_prep(CAT, num_baseline)),
        ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
    ])
    _, _, rows = eval_model(
        baseline, X_train_b, y_train, X_valid_b, y_valid, X_test_b, y_test, "Baseline LogReg"
    )

    logreg = Pipeline([
        ("prep", make_prep(CAT, NUM)),
        ("model", LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced", random_state=42)),
    ])
    logreg, pred_lr, rows_lr = eval_model(
        logreg, X_train, y_train, X_valid, y_valid, X_test, y_test, "LogReg + FE"
    )

    histgb = Pipeline([
        ("prep", make_prep(CAT, NUM)),
        ("model", HistGradientBoostingClassifier(
            max_depth=5, learning_rate=0.05, max_iter=500, random_state=42,
        )),
    ])
    histgb, pred_hgb, rows_hgb = eval_model(
        histgb, X_train, y_train, X_valid, y_valid, X_test, y_test, "HistGB + FE"
    )

    prep_lgb = make_prep(CAT, NUM)
    Xtr = prep_lgb.fit_transform(X_train, y_train)
    Xva = prep_lgb.transform(X_valid)
    Xte = prep_lgb.transform(X_test)

    def objective(trial):
        params = dict(
            n_estimators=1500,
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
            num_leaves=trial.suggest_int("num_leaves", 8, 48),
            min_child_samples=trial.suggest_int("min_child_samples", 30, 150),
            subsample=trial.suggest_float("subsample", 0.7, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
            reg_lambda=trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
            reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            class_weight="balanced", random_state=42, verbose=-1,
        )
        m = LGBMClassifier(**params)
        m.fit(Xtr, y_train, eval_set=[(Xva, y_valid)], callbacks=[early_stopping(40, verbose=False)])
        return roc_auc_score(y_valid, m.predict_proba(Xva)[:, 1])

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=N_OPTUNA_TRIALS, show_progress_bar=False)

    lgbm_best = LGBMClassifier(
        n_estimators=1500, class_weight="balanced", random_state=42, verbose=-1, **study.best_params
    )
    lgbm_best.fit(Xtr, y_train, eval_set=[(Xva, y_valid)], callbacks=[early_stopping(40, verbose=False)])
    pred_lgb = {
        "train": lgbm_best.predict_proba(Xtr)[:, 1],
        "valid": lgbm_best.predict_proba(Xva)[:, 1],
        "test": lgbm_best.predict_proba(Xte)[:, 1],
    }
    rows_lgb = []
    for split, y in [("train", y_train), ("valid", y_valid), ("test", y_test)]:
        rows_lgb.append({"model": "LightGBM tuned", "split": split, **metrics(y, pred_lgb[split])})

    all_metrics = pd.DataFrame(rows + rows_lr + rows_hgb + rows_lgb)
    all_metrics.to_csv(OUT / "model_metrics.csv", index=False)

    best_row = all_metrics[all_metrics["split"] == "test"].sort_values("auc", ascending=False).iloc[0]
    best_name = best_row["model"]
    pred_best = (
        pred_lr if "LogReg" in best_name
        else pred_lgb if "LightGBM" in best_name
        else pred_hgb
    )

    # ROC
    fig, ax = plt.subplots(figsize=(7, 5))
    RocCurveDisplay.from_predictions(y_test, pred_lr["test"], name="LogReg + FE", ax=ax)
    RocCurveDisplay.from_predictions(y_test, pred_lgb["test"], name="LightGBM tuned", ax=ax)
    RocCurveDisplay.from_predictions(y_test, pred_hgb["test"], name="HistGB + FE", ax=ax)
    ax.set_title("ROC — test (май 2024)")
    style_ax(ax)
    plt.tight_layout()
    fig.savefig(OUT / "nb_roc_test.png", dpi=150, facecolor=BG)
    fig.savefig(FIG / "model_roc_test.png", dpi=150, facecolor=BG)
    plt.close(fig)

    # Deciles
    dec = decile_table(y_test, pred_best["test"])
    dec.to_csv(OUT / "model_deciles_test.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(dec["decile"].astype(str), dec["bad_rate"] * 100, color="#7c5cff")
    ax.set_xlabel("Дециль (1 = низкий риск)")
    ax.set_ylabel("Bad rate 90+, %")
    ax.set_title(f"Bad rate по децилям — {best_name}, test")
    style_ax(ax)
    plt.tight_layout()
    fig.savefig(OUT / "nb_deciles_test.png", dpi=150, facecolor=BG)
    fig.savefig(FIG / "model_deciles_test.png", dpi=150, facecolor=BG)
    plt.close(fig)

    # Feature importance (OHE-expanded names from preprocessor)
    feat_names = prep_lgb.get_feature_names_out()
    imp = pd.Series(lgbm_best.feature_importances_, index=feat_names).sort_values(ascending=False)
    imp.head(15).to_csv(OUT / "feature_importance.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    imp.head(15).iloc[::-1].plot(kind="barh", ax=ax, color="#36cfc9")
    ax.set_title("Топ-15 признаков — LightGBM")
    style_ax(ax)
    plt.tight_layout()
    fig.savefig(OUT / "nb_feature_importance.png", dpi=150, facecolor=BG)
    fig.savefig(FIG / "model_feature_importance.png", dpi=150, facecolor=BG)
    plt.close(fig)

    # Profit curve
    avg_loan, lgd, margin = 12_000_000, 0.50, 0.15
    fn_cost, fp_cost = avg_loan * lgd, avg_loan * margin
    profits = []
    for thr in np.linspace(0.05, 0.95, 19):
        approve = pred_best["test"] <= thr
        tp = ((approve) & (y_test == 0)).sum()
        fn = ((approve) & (y_test == 1)).sum()
        fp = ((~approve) & (y_test == 0)).sum()
        profits.append({
            "threshold": thr,
            "profit_mln": (tp * fp_cost - fn * fn_cost - fp * fp_cost) / 1e6,
        })
    profit_df = pd.DataFrame(profits)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(profit_df["threshold"], profit_df["profit_mln"], color="#ffc53d", lw=2)
    ax.set_xlabel("Порог одобрения (PD ≤ threshold)")
    ax.set_ylabel("Прибыль, млн UZS")
    ax.set_title(f"Экономика по порогу — {best_name}, test")
    style_ax(ax)
    plt.tight_layout()
    fig.savefig(OUT / "nb_profit_curve.png", dpi=150, facecolor=BG)
    fig.savefig(FIG / "model_profit_curve.png", dpi=150, facecolor=BG)
    plt.close(fig)

    summary = {
        "best_model": best_name,
        "metrics_test": all_metrics[all_metrics["split"] == "test"].set_index("model").to_dict(),
        "deciles": dec.to_dict(orient="records"),
        "top_importance": imp.head(10).to_dict(),
        "baseline_test_auc": float(all_metrics[
            (all_metrics["model"] == "Baseline LogReg") & (all_metrics["split"] == "test")
        ]["auc"].iloc[0]),
        "best_test_auc": float(best_row["auc"]),
    }
    (OUT / "model_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(all_metrics.pivot(index="model", columns="split", values="auc").round(4))
    print(f"\nBest on test: {best_name} AUC={best_row['auc']}")
    print(f"Top importance: {list(imp.head(6).index)}")
    print(f"Decile 1 bad={dec.iloc[0]['bad_rate']*100:.1f}%  Decile 10 bad={dec.iloc[-1]['bad_rate']*100:.1f}%")


if __name__ == "__main__":
    main()
