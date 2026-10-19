# data_raw — сырые выгрузки scoring_*

PostgreSQL `academy_db`, срез **2025-05-31**.

## Структура папок

```
data_raw/
├── useful/     # 10 таблиц — ядро проекта
├── junk/       # 4 таблицы — не использовать
├── leakage/    # 3 таблицы — post-decision / утечка
└── README.md
```

## useful/ — Полезные — ядро для target, фичей и EDA

### scoring_applications

**Файл:** `useful/scoring_applications.csv`  

**Строк:** 18,000  

**Назначение:** Заявки на кредит (анкета + решение)

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `application_id` | `bigint` | ID заявки |
| `client_id` | `bigint` | ID клиента |
| `decision_date` | `date` | Дата решения по заявке |
| `channel` | `text` | Канал: mobile_app, branch, agent |
| `purpose` | `text` | Цель кредита |
| `requested_amount_uzs` | `bigint` | Запрошенная сумма, сум |
| `term_months` | `integer` | Срок в месяцах |
| `declared_income_uzs` | `bigint` | Заявленный доход, сум |
| `employment_months` | `integer` | Стаж работы, месяцы |
| `final_decision` | `text` | approved / rejected |
| `approved_by_old_policy` | `boolean` | Одобрила бы старая политика (bool) |

### scoring_bureau_inquiries

**Файл:** `useful/scoring_bureau_inquiries.csv`  

**Строк:** 31,383  

**Назначение:** Запросы в кредитное бюро

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `inquiry_id` | `bigint` | ID запроса в КБ |
| `client_id` | `bigint` | ID клиента |
| `inquiry_date` | `date` | Дата запроса в КБ |
| `creditor_name` | `text` | Название банка-кредитора |
| `inquiry_type` | `text` | Тип запроса в КБ |

### scoring_bureau_loans

**Файл:** `useful/scoring_bureau_loans.csv`  

**Строк:** 34,684  

**Назначение:** Кредиты клиента в других банках (КБ)

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `bureau_loan_id` | `bigint` | ID кредита в КБ |
| `client_id` | `bigint` | ID клиента |
| `creditor_name` | `text` | Название банка-кредитора |
| `open_date` | `date` | Дата открытия кредита в другом банке |
| `planned_close_date` | `date` | Плановая дата закрытия кредита |
| `close_date` | `date` | Фактическая дата закрытия |
| `loan_amount_uzs` | `bigint` | Сумма кредита при открытии |
| `monthly_payment_uzs` | `bigint` | Ежемесячный платёж, сум |
| `outstanding_uzs` | `bigint` | Остаток долга на срез (leakage) |
| `status` | `text` | Статус |
| `current_dpd_bucket` | `text` | Текущая просрочка (leakage) |
| `worst_dpd_ever` | `integer` | Худшая просрочка за всё время |

### scoring_bureau_snapshots

**Файл:** `useful/scoring_bureau_snapshots.csv`  

**Строк:** 86,161  

**Назначение:** Снимки КБ (score, долг) по датам

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `client_id` | `bigint` | ID клиента |
| `snapshot_date` | `date` | Дата снимка КБ |
| `bureau_score` | `integer` | Кредитный скор КБ |
| `existing_debt_uzs` | `bigint` | Долг в других банках на дату снимка |
| `active_loans_cnt` | `integer` | Число активных кредитов на дату снимка |

### scoring_card_disputes

**Файл:** `useful/scoring_card_disputes.csv`  

**Строк:** 2,467  

**Назначение:** Споры по карточным операциям

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `dispute_id` | `bigint` | ID спора |
| `txn_id` | `bigint` | ID транзакции |
| `opened_date` | `date` | Дата открытия спора |
| `reason_code` | `text` | Причина спора |
| `dispute_amount_uzs` | `bigint` | Сумма спора |
| `status` | `text` | Статус |

### scoring_card_transactions

**Файл:** `useful/scoring_card_transactions.csv`  

**Строк:** 1,044,743  

**Назначение:** Карточные транзакции

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `txn_id` | `bigint` | ID транзакции |
| `card_id` | `bigint` | ID карты |
| `client_id` | `bigint` | ID клиента |
| `txn_ts` | `timestamp without time zone` | Дата и время транзакции |
| `txn_type` | `text` | Тип операции: purchase, salary_in, ... |
| `mcc_group` | `text` | Категория траты |
| `amount_uzs` | `bigint` | Сумма, сум |
| `status` | `text` | Статус |
| `decline_reason` | `text` | Причина отклонения операции |

### scoring_cards

**Файл:** `useful/scoring_cards.csv`  

**Строк:** 12,614  

**Назначение:** Карты клиентов

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `card_id` | `bigint` | ID карты |
| `customer_id` | `bigint` | ID клиента в справочнике |
| `card_type` | `text` | debit / credit |
| `scheme` | `text` | Uzcard, Visa, Humo |
| `issue_date` | `date` | Дата выдачи кредита |
| `expiry_date` | `date` | Срок действия карты |
| `status` | `text` | Статус |
| `credit_limit_uzs` | `bigint` | Кредитный лимит карты |

### scoring_contracts

**Файл:** `useful/scoring_contracts.csv`  

**Строк:** 11,277  

**Назначение:** Выданные договоры (только approved)

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `contract_id` | `bigint` | ID договора |
| `application_id` | `bigint` | ID заявки |
| `client_id` | `bigint` | ID клиента |
| `issue_date` | `date` | Дата выдачи кредита |
| `issued_amount_uzs` | `bigint` | Выданная сумма, сум |
| `term_months` | `integer` | Срок в месяцах |
| `annual_rate_pct` | `numeric` | Годовая ставка, % |
| `monthly_payment_uzs` | `bigint` | Ежемесячный платёж, сум |

### scoring_customers

**Файл:** `useful/scoring_customers.csv`  

**Строк:** 8,000  

**Назначение:** Справочник клиентов банка

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `customer_id` | `bigint` | ID клиента в справочнике |
| `full_name` | `text` | ФИО |
| `birth_date` | `date` | Дата рождения |
| `gender` | `text` | Пол: M / F |
| `region` | `text` | Регион |
| `customer_segment` | `text` | Сегмент: mass, payroll, premium, affluent |
| `onboarding_date` | `date` | Дата регистрации клиента в банке |
| `income_band` | `text` | Диапазон дохода в профиле |

### scoring_payments

**Файл:** `useful/scoring_payments.csv`  

**Строк:** 103,150  

**Назначение:** График платежей — основа target

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `payment_id` | `bigint` | ID платежа |
| `contract_id` | `bigint` | ID договора |
| `installment_no` | `integer` | Номер платежа в графике |
| `due_date` | `date` | Плановая дата платежа |
| `due_amount_uzs` | `bigint` | Сумма к оплате по графику |
| `paid_date` | `date` | Фактическая дата оплаты (NULL = не оплатил) |
| `paid_amount_uzs` | `bigint` | Фактически уплаченная сумма |

## junk/ — Мусор — устаревшие, бэкапы, сэмплы, пустые

### scoring_clients_old

**Файл:** `junk/scoring_clients_old.csv`  

**Строк:** 6,000  

**Назначение:** Устаревший справочник (заменён customers)

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `client_id` | `bigint` | ID клиента |
| `full_name` | `text` | ФИО |
| `birthdate` | `date` | Дата рождения (старое поле) |
| `oblast` | `text` | Область (устар.) |
| `segment_2022` | `text` | Сегмент 2022 (устар.) |
| `income_band_old` | `text` | Диапазон дохода (устар.) |

### scoring_payments_backup

**Файл:** `junk/scoring_payments_backup.csv`  

**Строк:** 73,421  

**Назначение:** Неполный бэкап payments

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `payment_id` | `bigint` | ID платежа |
| `contract_id` | `bigint` | ID договора |
| `installment_no` | `integer` | Номер платежа в графике |
| `due_date` | `date` | Плановая дата платежа |
| `due_amount_uzs` | `bigint` | Сумма к оплате по графику |
| `paid_date` | `date` | Фактическая дата оплаты (NULL = не оплатил) |
| `paid_amount_uzs` | `bigint` | Фактически уплаченная сумма |

### scoring_temp

**Файл:** `junk/scoring_temp.csv`  

**Строк:** 0  

**Назначение:** Пустая служебная таблица

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `id` | `bigint` | Служебный ID |
| `val` | `text` | Служебное значение |
| `note` | `text` | Комментарий |

### scoring_txn_sample

**Файл:** `junk/scoring_txn_sample.csv`  

**Строк:** 5,000  

**Назначение:** Сэмпл транзакций (есть полная таблица)

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `transaction_id` | `bigint` | ID транзакции (sample) |
| `card_id` | `bigint` | ID карты |
| `merchant_id` | `bigint` | ID мерчанта |
| `terminal_id` | `bigint` | ID терминала |
| `txn_ts` | `timestamp without time zone` | Дата и время транзакции |
| `amount_uzs` | `bigint` | Сумма, сум |
| `txn_status` | `text` | Статус транзакции (sample) |
| `decline_reason` | `text` | Причина отклонения операции |
| `is_recurring` | `boolean` | Регулярный платёж |
| `entry_mode` | `text` | Способ оплаты |
| `is_disputed` | `boolean` | Был ли спор |

## leakage/ — Leakage / post-decision — не для фичей новой модели

### scoring_applications_full

**Файл:** `leakage/scoring_applications_full.csv`  

**Строк:** 11,277  

**Назначение:** Витрина с dpd_max, collection — leakage

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `application_id` | `bigint` | ID заявки |
| `client_id` | `bigint` | ID клиента |
| `decision_date` | `date` | Дата решения по заявке |
| `requested_amount_uzs` | `bigint` | Запрошенная сумма, сум |
| `term_months` | `integer` | Срок в месяцах |
| `declared_income_uzs` | `bigint` | Заявленный доход, сум |
| `bureau_score_latest` | `integer` | Последний скор КБ (leakage) |
| `dpd_max` | `integer` | Макс. DPD по договору (leakage) |
| `collection_calls_cnt` | `integer` | Число звонков взыскания (leakage) |
| `contract_status_now` | `text` | Текущий статус договора (leakage) |

### scoring_collection_actions

**Файл:** `leakage/scoring_collection_actions.csv`  

**Строк:** 9,135  

**Назначение:** Взыскание после просрочки

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `contract_id` | `bigint` | ID договора |
| `action_date` | `date` | Дата действия взыскания |
| `action_type` | `text` | Тип взыскания: sms, call, visit |
| `contact_result` | `text` | Результат контакта |

### scoring_model_v1_scores

**Файл:** `leakage/scoring_model_v1_scores.csv`  

**Строк:** 18,000  

**Назначение:** Скоры существующей модели v1

| Колонка | Тип (PostgreSQL) | Описание |
|---------|------------------|----------|
| `application_id` | `bigint` | ID заявки |
| `score_v1` | `integer` | Скор модели v1 |
| `decision_recommend` | `text` | Рекомендация модели: approve / decline |

---
*Сгенерировано из PostgreSQL + CSV в data_raw.*
