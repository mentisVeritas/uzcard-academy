# Определения таргета

| Файл | Что внутри |
|------|------------|
| `target_30d.csv` | когорта + `target` при N=30 (тишина) |
| `target_45d.csv` | то же, N=45 |
| `target_60d.csv` | то же, N=60 |
| `target_60d_min_amount.csv` | та же когорта, что N=60; `target=1`, если нет approved **или** сумма за 60 дней < 1 000 000 сум (500 тыс./мес) |
| `funnel_by_snapshot.csv` | кого исключили, доля оттока по месяцам (тишина 30/45/60) |
| `funnel_60d_min_amount.csv` | тишина-60 vs порог оборота по срезам |
| `compare_30_45_60.csv` | сводка для выбора порога тишины |
| `compare_60d_min_amount.csv` | тишина-60 vs порог 500 тыс. сум/мес (июль / сентябрь) |
| `amount_monthly_stats.csv` | перцентили месячного оборота, из которых взят порог |
| `target_60d_usage.csv` | **основной таргет:** жив = (≥3 ops и ≥ p5 суммы) **или** ≥20 ops |
| `funnel_60d_usage.csv` | доля оттока usage vs тишина по месяцам |
| `compare_60d_usage.csv` | июль / сентябрь |
| `gap_stats.csv` | паузы между операциями |

Сборка тишины: `uv run python scripts/build_targets.py` (из папки проекта, после `uv sync`).

Сборка порога оборота: `uv run python scripts/build_target_amount.py`

Стаж когорты — дни от **первой approved** до snapshot, не от регистрации.

Смысл цифр — в `../TARGET.md`.
