# Research Log — Credit Scoring

Формат: **Гипотеза → SQL → Результат → Вывод → Следующий вопрос**

---

## RL-001: Все scoring_ таблицы найдены

**Гипотеза:** В `public` есть только таблицы с префиксом `scoring_`, относящиеся к заданию.

**SQL:**
```sql
SELECT tablename FROM pg_tables
WHERE schemaname='public' AND tablename LIKE 'scoring\_%'
ORDER BY 1;
```

**Результат:** 17 таблиц (см. `data/table_metadata.json`).

**Вывод:** Полный список получен. Дальше — профилирование каждой.

**Следующий вопрос:** Есть ли PK/FK в схеме?

---

## RL-002: В БД нет объявленных PK/FK

**Гипотеза:** Связи нужно восстанавливать вручную.

**SQL:**
```sql
SELECT tc.table_name, tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema='public' AND tc.table_name LIKE 'scoring\_%';
```

**Результат:** 0 FOREIGN KEY, 0 PRIMARY KEY.

**Вывод:** Целостность не enforced; проверять join-ами.

**Следующий вопрос:** Сколько заявок approved vs rejected?

---

## RL-003: Распределение решений

**Гипотеза:** Примерно 60/40 approve/reject.

**SQL:**
```sql
SELECT final_decision, COUNT(*) FROM scoring_applications GROUP BY 1;
```

**Результат:** approved 11 277 (62.65%), rejected 6 723 (37.35%).

**Вывод:** Данные сбалансированы для анализа политики; rejected существенная доля.

**Следующий вопрос:** Каждой approved заявке соответствует договор?

---

## RL-004: Approved = Contracts 1:1

**Гипотеза:** `scoring_contracts` — только одобренные заявки.

**SQL:**
```sql
SELECT
  (SELECT COUNT(*) FROM scoring_applications WHERE final_decision='approved') a,
  (SELECT COUNT(*) FROM scoring_contracts) c;
```

**Результат:** 11 277 = 11 277, matched 11 277, approved_no_contract 0.

**Вывод:** Идеальное соответствие. Target строим через contracts → payments.

**Следующий вопрос:** Как считать DPD?

---

## RL-005: DPD на срез 2025-05-31

**Гипотеза:** DPD = days between due_date and paid_date (or as-of if unpaid).

**SQL:** см. `scripts/run_analysis.py`, CTE `payment_dpd`.

**Результат:** На уровне инсталмента: 90+ DPD у 8 935 платежей; на уровне договора max_dpd ≥ 90 у ~12% договоров.

**Вывод:** Методология DPD корректна. Используем max по договору.

**Следующий вопрос:** Какой порог BAD выбрать — 30, 60 или 90?

---

## RL-006: Сравнение порогов 30/60/90

**Гипотеза:** 90+ — стандартный default для retail.

**SQL:**
```sql
-- contract-level bad rates в run_analysis.py
```

**Результат:** bad30=22.8%, bad60=15.9%, bad90=12.0%.

**Вывод:** 90+ даёт стабильное бизнес-определение default; 30+ слишком шумный (краткосрочные задержки).

**Следующий вопрос:** Сколько договоров незрелые?

---

## RL-007: Незрелые договоры

**Гипотеза:** Договоры с issue_date + 12m > 2025-05-31 нельзя маркировать Good.

**SQL:**
```sql
SELECT COUNT(*) FILTER (
  WHERE (issue_date + interval '12 months')::date > '2025-05-31'
) FROM scoring_contracts;
```

**Результат:** 5 364 незрелых (47.7%).

**Вывод:** Target NULL для незрелых без 90+ DPD. EDA только на mature когортах.

**Следующий вопрос:** Почему bad_rate=100% для когорт 2024-06+?

---

## RL-008: Артефакт 100% bad в свежих когортах

**Гипотеза:** Это не реальный bad rate, а смесь immature + early 90+ DPD.

**SQL:** `bad_rate_by_month.csv` vs `bad_rate_by_month_mature_only.csv`.

**Результат:** mature_n=0 для 2024-06+; в полном файле bad_rate=1.0 из-за max_dpd≥90 без закрытого окна.

**Вывод:** Для отчётности использовать **mature-only** файл. В target: Good только при window_closed=1.

**Следующий вопрос:** Есть ли leakage в applications_full?

---

## RL-009: scoring_applications_full — leakage

**Гипотеза:** Колонки dpd_max, collection_calls_cnt — post-decision.

**SQL:**
```sql
SELECT AVG(dpd_max), AVG(collection_calls_cnt), contract_status_now
FROM scoring_applications_full LIMIT 5;
```

**Результат:** dpd_max avg > 0, collection_calls_cnt avg > 0, status = active/closed.

**Вывод:** Таблица забракована для фичей. Это денормализованная витрина с текущим состоянием.

**Следующий вопрос:** payments_backup отличается от payments?

---

## RL-010: payments_backup неполный

**Гипотеза:** Backup — старая версия до догрузки.

**SQL:**
```sql
SELECT (SELECT COUNT(*) FROM scoring_payments) p,
       (SELECT COUNT(*) FROM scoring_payments_backup) b;
```

**Результат:** 103 150 vs 73 421.

**Вывод:** Использовать только `scoring_payments`.

**Следующий вопрос:** client_id = customer_id?

---

## RL-011: Покрытие customers

**Гипотеза:** Не все client_id есть в scoring_customers.

**SQL:**
```sql
SELECT COUNT(DISTINCT a.client_id) total,
       COUNT(DISTINCT c.customer_id) matched
FROM scoring_applications a
LEFT JOIN scoring_customers c ON a.client_id=c.customer_id;
```

**Результат:** 11 328 клиентов в заявках, 5 891 в customers (~52%).

**Вывод:** Демография доступна не для всех; нужен флаг `has_customer_profile`.

**Следующий вопрос:** У кого нет карточных транзакций?

---

## RL-012: Карточное покрытие

**Гипотеза:** Только клиенты банка с картами имеют txn.

**SQL:**
```sql
SELECT COUNT(DISTINCT client_id) FROM scoring_applications; -- 11328
-- apps_with_card_txn: 4164, without: 7164
```

**Результат:** 37% заявок с карточными данными.

**Вывод:** Card-фичи с missing indicator; не dropna.

**Следующий вопрос:** Reject inference возможен?

---

## RL-013: Reject inference

**Гипотеза:** Без outcome rejected нельзя обучать на полной популяции.

**SQL:**
```sql
SELECT COUNT(*) FROM scoring_contracts c
JOIN scoring_applications a ON c.application_id=a.application_id
WHERE a.final_decision='rejected';
```

**Результат:** 0 договоров у rejected.

**Вывод:** Target для rejected неопределён. PD-модель на approved; rejected — policy analysis only.

**Следующий вопрос:** Смещение approved vs rejected?

---

## RL-014: Selection bias

**Гипотеза:** Approved «лучше» по доходу и bureau.

**SQL:** bureau as-of join + GROUP BY final_decision.

**Результат:** approved выше по amount, income, bureau_score.

**Вывод:** Положительная селекция подтверждена. Модель на approved не переносится на full population без reject inference.

**Следующий вопрос:** Росла ли просрочка?

---

## RL-015: Тренд bad rate по когортам

**Гипотеза:** Бизнес прав — просрочка выросла.

**SQL:** `bad_rate_by_month_mature_only.csv`

**Результат:** 2023-06: 13.2% → 2023-09: 7.4% → 2024-05: 12.7%. Нет монотонного роста.

**Вывод:** На 90+ DPD в 12m окне «рост» **не подтверждается** однозначно. Возможно бизнес смотрит 30+ DPD или другой период.

**Следующий вопрос:** —

---

## Сводная таблица: источник → фичи

| Источник | Ключ | Момент | В фичи? | Причина отказа |
|----------|------|--------|---------|----------------|
| scoring_applications | application_id | decision | ✅ анкета | final_decision — не фича |
| scoring_contracts | contract_id | post-issue | ❌ | после решения |
| scoring_payments | payment_id | post-issue | ❌ | target only |
| scoring_customers | customer_id | static | ✅ частично | 48% без матча |
| scoring_bureau_snapshots | client_id+date | as-of | ✅ | — |
| scoring_bureau_inquiries | inquiry_id | historical | ✅ | — |
| scoring_bureau_loans | bureau_loan_id | mixed | ⚠️ | status/dpd — leakage |
| scoring_cards | card_id | static | ✅ | — |
| scoring_card_transactions | txn_id | historical | ✅ | окно до decision |
| scoring_card_disputes | dispute_id | historical | ✅ | opened_date ≤ decision |
| scoring_collection_actions | contract_id | post-default | ❌ | leakage |
| scoring_model_v1_scores | application_id | decision | ❌ | текущая модель |
| scoring_applications_full | application_id | current | ❌ | leakage |
| scoring_payments_backup | — | — | ❌ | дубль |
| scoring_clients_old | — | — | ❌ | устарело |
| scoring_txn_sample | — | — | ❌ | сэмпл |
| scoring_temp | — | — | ❌ | пусто |
