# Классные работы и решения

Ноутбуки с занятий и решения первых домашних заданий. Слайды к этим урокам — в [`../lectures/`](../lectures/), условия ДЗ — в [`../homework/`](../homework/).

| Папка | Урок | Что внутри | Данные |
|-------|------|------------|--------|
| [`week01-python-basics/`](week01-python-basics/) | ДЗ 1 — аналитика транзакций | решение: 6 функций над 25 транзакциями | внутри ноутбука |
| [`week02-uzcard-currency/`](week02-uzcard-currency/) | ДЗ 2 — сервис курсов валют | решение: ООП, dunder-методы, HTTP + JSON | API frankfurter.dev |
| [`pandas/`](pandas/) | Лекция 15 — чистка данных | разбор чистки транзакций + самостоятельная работа по билетам | `l13_transactions_raw.csv`, `concert_tickets.csv` |
| [`matplotlib/`](matplotlib/) | Лекция 17–18 — визуализация | проверка гипотез стримингового сервиса графиками | `tracks_v2.csv`, `artists_v2.csv` |
| [`sql/`](sql/) | Лекция 22 — SQL: подзапросы, CTE, окна | практика на наборе «Платежи» | PostgreSQL (`.env`) |
| [`ml-scoring/`](ml-scoring/) | Блок 3 — логистическая регрессия | скоринг: PD, time split, ROC-AUC | `credit_scoring_classwork.csv` |

## Запуск

```bash
uv sync
uv run jupyter notebook lessons/
```

Для SQL-урока нужен файл `.env` в корне репозитория (шаблон — `.env.example`).
