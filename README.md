# Uzcard Academy

Внутренняя учебная программа по data science и аналитике для сотрудников Uzcard.

## Структура репозитория

```
uzcard-academy/
├── lessons/                    # учебные материалы по неделям и темам
│   ├── week01-python-basics/
│   ├── week02-uzcard-currency/
│   ├── pandas/
│   ├── matplotlib/
│   ├── sql/
│   └── ml-scoring/
├── projects/                   # командные проекты академии
│   └── mars/
│       └── merchanthub/        # git submodule → отдельный репозиторий
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

## Уроки

| Папка | Тема |
|-------|------|
| `lessons/week01-python-basics` | Основы Python |
| `lessons/week02-uzcard-currency` | Сервис валют Uzcard |
| `lessons/pandas` | Работа с данными в Pandas |
| `lessons/matplotlib` | Визуализация |
| `lessons/sql` | SQL и работа с БД |
| `lessons/ml-scoring` | Логистическая регрессия, Decision Tree, скоринг |

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
