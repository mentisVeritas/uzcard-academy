# Credit Scoring — Кредитный скоринг

Исследование базы `academy_db` (таблицы `scoring_*`, срез на **2025-05-31**).

## Быстрый старт

```bash
# Target + features + EDA → CSV в data/
uv run python projects/credit_scoring/scripts/run_analysis.py
```

Обучение модели — в блокноте `notebooks/model_training.ipynb` (Run All).

## Что есть в проекте

| Папка / файл | Содержание |
|--------------|------------|
| `sql/` | Запросы: разведка, target, features |
| `scripts/run_analysis.py` | Автоматический пайплайн анализа |
| `notebooks/model_training.ipynb` | **Обучение PD-модели + графики** |
| `data/` | CSV: target, features, modeling_dataset, EDA |
| `outputs/` | Графики из блокнота (`nb_*.png`) |
| `notebooks/eda.ipynb` | Разбор шагов EDA |
| `presentation/` | Слайды для защиты |

## Модель

Открой `notebooks/model_training.ipynb` и запусти все ячейки.

- **Таргет:** `target_90`, только зрелые когорты
- **Split:** train ≤ 2024-02, valid 2024-03—04, test 2024-05
- **Модели:** LogReg (baseline) + LightGBM
- **Графики:** ROC, децили, важность признаков, калибровка, profit curve

Подробности — [REPORT.md](REPORT.md), вопросы по анализу — [DEFENSE_QA.md](DEFENSE_QA.md).
