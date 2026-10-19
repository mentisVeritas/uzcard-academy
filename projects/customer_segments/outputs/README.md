# Артефакты модели

Сборка: `uv run python scripts/cluster.py`

| Файл | Что внутри |
|------|------------|
| `k_metrics.csv` | silhouette / CH / DB / размеры для K=2..8 |
| `cluster_profiles.csv` | медианы по кластерам в исходных единицах |
| `stability_ari.csv` | таблица устойчивости |
| `quartile_compare.csv` | типология vs квартили оборота |
| `economics.csv` | люди, доход, предложение |
| `assignments.csv` | customer_id → сегмент |
| `*.png` | графики для ноутбука и слайдов |
| `pipeline.joblib` | scaler + KMeans для нового клиента |
