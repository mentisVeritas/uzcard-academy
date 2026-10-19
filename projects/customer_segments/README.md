# Customer Segments — Типология клиентской базы

Домашнее задание 6 (unsupervised): построить типологию ~20 000 клиентов для перестройки тарифной линейки.

## Контекст

«У нас 20 тысяч клиентов и один тариф на всех. Нужна типология: сколько типов, чем отличаются, как назвать и что предлагать».

Готового «правильного» сегмента в базе нет — тип клиента вы **конструируете** и **защищаете**.

## Данные

- PostgreSQL `academy_db`, таблицы `seg_*`
- Период: **2024–2025**, срез до 2025-12-31
- Карточные операции, остатки, продукты, доходность по месяцам, текущий тариф `standard` (15 000 UZS/мес)

Не используем: `seg_customers_360` (готовый crm-сегмент), `seg_rfm_old`, `seg_transactions_archive`.

## Быстрый старт

```bash
cd projects/customer_segments
uv sync                          # создаёт .venv
source .venv/bin/activate
uv run python scripts/explore.py
uv run python scripts/build_features.py
uv run python scripts/cluster.py
jupyter notebook notebooks/segments.ipynb
```

Ядро Jupyter: **customer_segments**  
(`uv run python -m ipykernel install --user --name customer-segments --display-name customer_segments`)

Подключение к БД — `.env` в корне репозитория (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`).

## Окно наблюдения

| Параметр | Значение |
|----------|----------|
| Snapshot (`as_of`) | 2025-11-30 |
| Lookback | 6 месяцев |
| Мин. стаж | 90 дней |
| Персональное окно | `max(window_start, signup_date)` |

Декабрь обрезан (txn до 2025-12-28) — в признаки не берём. Клиентов без операций в окне не кластеризуем: отдельный тип «спящие».

## Структура

| Папка / файл | Содержание |
|--------------|------------|
| `docs/ZADANIE_SEGMENTS.pdf` | Оригинал задания |
| `ASSIGNMENT.md` | Текст задания |
| `TABLES.md` | Карта таблиц |
| `WINDOW.md` | Обоснование окна |
| `FEATURES.md` | Оси и признаки |
| `notebooks/segments.ipynb` | Рабочий ноутбук |
| `sql/` | Разведка и сборка признаков |
| `scripts/` | Пайплайны |
| `data/` | Feature matrix |
| `outputs/` | Кластеры, ARI, экономика, графики |
| `presentation/` | Слайды |

## Чеклист задания

- [x] Окно наблюдения + учёт разной длины истории
- [x] Оси сегментации (не все колонки подряд)
- [x] Типология + обоснование числа классов
- [x] Сравнение с квартилями по обороту
- [x] Таблица устойчивости (ARI)
- [x] Правило для нового клиента
- [x] Названия сегментов + экономика (люди, доход, предложение)
