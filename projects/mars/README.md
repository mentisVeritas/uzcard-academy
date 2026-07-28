# Команда Mars

Командный проект Uzcard Academy.

## Проекты

| Проект | Описание | Репозиторий |
|--------|----------|-------------|
| **MerchantHub** | Анализ экономики эквайринга (трек C) | [github.com/mentisVeritas/uzcard-merchanthub](https://github.com/mentisVeritas/uzcard-merchanthub) |

## MerchantHub

Отдельный git-репозиторий, подключённый как submodule:

```bash
cd merchanthub
uv sync
jupyter notebook merchanthub_track_c.ipynb
```

Если папка `merchanthub` пуста после клонирования:

```bash
git submodule update --init --recursive
```

Клонирование отдельно:

```bash
git clone git@github.com:mentisVeritas/uzcard-merchanthub.git
```
