# ДЗ 2. Сервис курсов валют (ООП + Web/API)

**Дедлайн:** 05.06.2026, 23:59 · **Попытки:** 1 / 3 · **Результат:** 6 / 6 авто

Сервис конвертации валют: классы, наследование, dunder-методы, HTTP-запрос и парсинг JSON.

- Стартер: [`starter/week02_uzcard_currency_service.ipynb`](starter/week02_uzcard_currency_service.ipynb)
- Ваше решение: [`lessons/week02-uzcard-currency/week02_uzcard_currency_service.ipynb`](../../lessons/week02-uzcard-currency/week02_uzcard_currency_service.ipynb)

## Вопросы и ваши ответы

| # | Вопрос | Тип | Ответ | Итог |
|---|--------|-----|-------|------|
| Q1 | Курс EUR (`book['EUR'].rate`) | число | 0.91366 | ✅ |
| Q2 | Сколько EUR дадут за 1000 USD (2 знака) | число | 913.66 | ✅ |
| Q3 | Сколько GBP из 1000 EUR (кросс через USD, 2 знака) | число | 860.75 | ✅ |
| Q4 | Сколько валют в RateBook (`len(book)`) | число | 30 | ✅ |
| Q5 | Что выводит `str(book['EUR'])`? | точный текст | `EUR: 0.9137 per USD` | ✅ |
| Q6 | MRO для `TurboBook(CachedRateBook, ObservableMixin)` | текст | TurboBook, CachedRateBook, RateBook, ObservableMixin, object | ✅ |
| Q7 | Почему `Currency.__eq__` сравнивает только `code`, а не `rate`? Что было бы плохо, если бы сравнивали и курс? | ручная | **не отвечен** | — |
