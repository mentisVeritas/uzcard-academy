# Датасеты сегментации

Сборка: `uv run python scripts/build_features.py`

| Файл | Что внутри |
|------|------------|
| `features_all_eligible.csv` | Все клиенты со стажем ≥ 90 дней на snapshot |
| `features_active.csv` | Из них — хотя бы одна операция в персональном окне (кластеризация) |
| `features_inactive.csv` | Нет операций в окне: отдельный тип «спящие», не кластеризуем |
| `features_summary.json` | Размеры выборок и параметры окна |
