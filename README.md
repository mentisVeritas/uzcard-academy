# Uzcard Academy

Внутренняя учебная программа по data science и аналитике для сотрудников Uzcard.

## Структура репозитория

```
uzcard-academy/
├── homework/                        # все ДЗ 1–6: условие, вопросы, ответы/баллы, стартеры
├── lectures/                        # офлайн-копия слайдов всех лекций (откройте lectures/index.html)
├── materials/                       # мини-проект, методички по презентации, ресурсы
├── lessons/                         # классные работы и решения ДЗ1–2
│   ├── week01-python-basics/
│   ├── week02-uzcard-currency/
│   ├── pandas/
│   ├── matplotlib/
│   ├── sql/
│   └── ml-scoring/
├── projects/
│   ├── credit_scoring/              # ДЗ4 — кредитный скоринг
│   ├── customer_churn/              # ДЗ5 — отток клиентов
│   ├── customer_segments/           # ДЗ6 — типология клиентов
│   └── mars/
│       └── merchanthub/             # git submodule → отдельный репозиторий
├── pyproject.toml
└── uv.lock
```

## Быстрый старт

```bash
# Клонирование с подмодулями
git clone --recurse-submodules git@github.com:mentisVeritas/uzcard-academy.git
cd uzcard-academy
cp .env.example .env   # заполните параметры БД для SQL-уроков

uv sync
jupyter notebook
```

## Навигация

| Что | Где |
|-----|-----|
| Статус всех домашних заданий | [`homework/README.md`](homework/README.md) |
| Слайды лекций 1–45 (офлайн) | [`lectures/index.html`](lectures/index.html) · [`lectures/README.md`](lectures/README.md) |
| Командный мини-проект (трек C) | [`materials/mini_project.md`](materials/mini_project.md) |
| Как делать презентацию к защите | [`materials/golden_rules.md`](materials/golden_rules.md) · [`materials/presentation_principles.md`](materials/presentation_principles.md) |
| Книги, курсы, ML-разборы | [`materials/resources.md`](materials/resources.md) |

## Уроки

| Папка | Тема |
|-------|------|
| [`lessons/week01-python-basics`](lessons/week01-python-basics/) | ДЗ 1 — основы Python, аналитика транзакций |
| [`lessons/week02-uzcard-currency`](lessons/week02-uzcard-currency/) | ДЗ 2 — сервис валют (ООП + API) |
| [`lessons/pandas`](lessons/pandas/) | Чистка данных в pandas |
| [`lessons/matplotlib`](lessons/matplotlib/) | Визуализация |
| [`lessons/sql`](lessons/sql/) | SQL: подзапросы, CTE, окна |
| [`lessons/ml-scoring`](lessons/ml-scoring/) | Логистическая регрессия, скоринг |

Обзор всех классных работ: [`lessons/README.md`](lessons/README.md).

Список всех учебных проектов: [`projects/README.md`](projects/README.md).

## Учебные проекты

### Credit Scoring (ДЗ4)

Кредитный скоринг: таргет из платежей, фичи до решения, PD-модель.

```bash
uv run python projects/credit_scoring/scripts/run_analysis.py
uv run jupyter notebook projects/credit_scoring/notebooks/eda.ipynb
```

Подробности: [`projects/credit_scoring/README.md`](projects/credit_scoring/README.md)

### Customer Churn (ДЗ5)

Отток клиентов: своё определение тишины, snapshot/горизонт, out-of-time модель удержания.

```bash
uv run jupyter notebook projects/customer_churn/notebooks/churn.ipynb
```

Подробности: [`projects/customer_churn/README.md`](projects/customer_churn/README.md)

### Customer Segments (ДЗ6)

Типология клиентской базы (unsupervised): окно наблюдения, оси, кластеры, устойчивость, экономика сегментов.

```bash
uv run jupyter notebook projects/customer_segments/notebooks/segments.ipynb
```

Подробности: [`projects/customer_segments/README.md`](projects/customer_segments/README.md)

## Проекты команд

### Mars → MerchantHub

**Репозиторий:** [github.com/mentisVeritas/uzcard-merchanthub](https://github.com/mentisVeritas/uzcard-merchanthub) (подключён как submodule в `projects/mars/merchanthub`)

Анализ экономики эквайринга: концентрация оборота, задержки выплат, спорные операции.

```bash
cd projects/mars/merchanthub
uv sync
jupyter notebook merchanthub_track_c.ipynb
```

## Зависимости

Общее окружение описано в `pyproject.toml`. Для проектов команд — отдельные `pyproject.toml` внутри submodule.

## База данных

Для SQL-уроков нужно подключение к учебной PostgreSQL. Скопируйте `.env.example` → `.env` и укажите параметры, которые выдаёт преподаватель. Файл `.env` в репозиторий не попадает.
