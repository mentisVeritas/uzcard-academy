# Учебные проекты Uzcard Academy

Домашние задания по ML и аналитике. Каждый проект — отдельная папка с ноутбуком, SQL, data и презентацией.

| ДЗ | Папка | Тема | Тип |
|----|-------|------|-----|
| 4 | [`credit_scoring/`](credit_scoring/) | Кредитный скоринг | supervised |
| 5 | [`customer_churn/`](customer_churn/) | Отток клиентов | supervised |
| 6 | [`customer_segments/`](customer_segments/) | Типология клиентской базы | unsupervised |

Командный проект: [`mars/merchanthub/`](mars/merchanthub/) (git submodule).

Условия заданий, вопросы формы и ваши ответы с баллами — в [`../homework/`](../homework/).

> **Что не лежит в git.** Сырые выгрузки `data_raw/` (до 130 МБ на файл) и промежуточные CSV оттока `customer_churn/data/` исключены через `.gitignore`. Восстановить: `uv run python scripts/download_raw.py` (churn, segments) или выгрузить таблицы `scoring_*` из БД по описанию в `credit_scoring/data_raw/README.md`; затем перезапустить ноутбуки.

## Общая структура проекта

```
project_name/
├── README.md           # обзор и быстрый старт
├── ASSIGNMENT.md       # текст задания (markdown)
├── docs/               # PDF задания и доп. материалы
├── notebooks/          # рабочие ноутбуки
├── sql/                # разведка, сборка признаков
├── scripts/            # воспроизводимые пайплайны
├── data/               # датасеты после обработки
├── data_raw/           # сырые выгрузки (useful / junk / leakage)
├── outputs/            # графики, метрики
└── presentation/       # слайды для защиты
```

## Подключение к БД

Из корня репозитория:

```bash
cp .env.example .env   # один раз
```

Параметры `DB_*` общие для всех проектов.
