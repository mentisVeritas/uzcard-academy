# Сырые таблицы churn_*

Выгрузки: CSV. Обоснование отбора — `../TABLES.md`.

```
data_raw/
├── useful/     # берём: target и фичи
├── junk/       # не берём: старые копии, пустые, NPS
└── leakage/    # не берём: витрина с готовым оттоком
```

Перескачать:

```bash
uv run python projects/customer_churn/scripts/download_raw.py
```
