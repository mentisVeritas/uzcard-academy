# 100 вопросов для защиты — Credit Scoring
Все ответы основаны на SQL-исследовании `academy_db`.

### 1. Сколько scoring_ таблиц в базе?

17 таблиц (подтверждено pg_tables).

### 2. Какая дата среза выгрузки?

2025-05-31 (указано в задании; подтверждено max датами payments и txn).

### 3. Есть ли PRIMARY KEY в таблицах?

Нет — ни одной объявленной PK в information_schema.

### 4. Есть ли FOREIGN KEY?

Нет — связи логические, восстановлены через JOIN.

### 5. Сколько строк в scoring_applications?

18 000.

### 6. Сколько уникальных application_id?

18 000 — дубликатов нет.

### 7. Сколько уникальных client_id в заявках?

11 328 (клиенты подают несколько заявок).

### 8. Какой период decision_date?

2023-06-01 — 2025-04-30.

### 9. Сколько заявок approved?

11 277 (62.65%).

### 10. Сколько rejected?

6 723 (37.35%).

### 11. Совпадает ли число contracts и approved?

Да, 11 277 = 11 277, 100% match.

### 12. Какая самая большая таблица?

scoring_card_transactions — 1 044 743 строк, 138 MB.

### 13. Какая таблица пустая?

scoring_temp — 0 строк.

### 14. Что такое client_id vs customer_id?

client_id в заявках; customer_id в customers/cards — логически один субъект, но покрытие customers только ~52%.

### 15. Зачем approved_by_old_policy?

Флаг смены кредитной политики: 612 rejected были бы одобрены старой политикой.

### 16. Опишите путь клиента от заявки до взыскания.

Заявка → решение → договор → платежи → DPD → collection_actions.

### 17. Когда появляется contract_id?

После одобрения, при выдаче кредита.

### 18. Есть ли договоры у rejected?

Нет — 0.

### 19. Средний лаг decision_date → issue_date?

1–5 дней (визуально по sample; issue >= decision).

### 20. Сколько платежей на договор в среднем?

103 150 / 11 277 ≈ 9.2 инсталмента.

### 21. Что такое installment_no?

Номер платежа в графике.

### 22. Когда начинается просрочка?

Когда paid_date > due_date или paid_date IS NULL после due_date.

### 23. Что такое scoring_collection_actions?

Действия взыскания (sms, call) — post-delinquency.

### 24. Связаны ли disputes с transactions?

Да, через txn_id.

### 25. Роль scoring_bureau_snapshots?

Исторические снимки bureau score и долга.

### 26. Роль scoring_bureau_inquiries?

Запросы кредиторов в КБ — credit hunger signal.

### 27. Роль scoring_bureau_loans?

Внешние кредиты клиента; осторожно с current status.

### 28. Можно ли по rejected построить target?

Нет — нет платежей и outcome.

### 29. Что хранит scoring_model_v1_scores?

Скор v1 и рекомендация на все 18 000 заявок.

### 30. Сколько этапов в жизненном цикле в нашей БД?

7: клиент, заявка, решение, договор, платежи, просрочка, взыскание.

### 31. Почему scoring_temp не нужна?

Пустая служебная таблица.

### 32. Почему scoring_payments_backup забракована?

73 421 строк vs 103 150 — неполная копия.

### 33. Почему scoring_clients_old устарела?

Заменена scoring_customers; устаревшие поля segment_2022.

### 34. Почему scoring_txn_sample — мусор?

5 000 строк — сэмпл; полные данные в card_transactions.

### 35. Почему applications_full опасна?

Содержит dpd_max, collection_calls, contract_status_now — leakage.

### 36. Можно ли использовать collection_actions?

Только для пост-анализа, не для фичей.

### 37. Чем payments отличается от payments_backup?

На 29 729 платежей больше в основной таблице.

### 38. Есть ли дубли между applications и applications_full?

11 277 overlap — full это подмножество approved с post-factum полями.

### 39. Нужны ли обе таблицы клиентов?

Нет — только scoring_customers.

### 40. Сколько таблиц в итоговом пайплайне?

10 рабочих из 17.

### 41. Что такое data leakage?

Использование информации, недоступной на момент decision_date.

### 42. Почему dpd_max — leakage?

Просрочка накапливается после выдачи.

### 43. Почему bureau_score_latest — leakage?

Берёт последний скор, не as-of decision.

### 44. Почему contract_status_now — leakage?

Статус на дату выгрузки 2025-05-31.

### 45. Почему collection_calls_cnt — leakage?

Звонки после дефолта.

### 46. Можно ли использовать paid_amount из payments как фичу?

Нет — платежи после issue_date.

### 47. Можно ли current_dpd_bucket из bureau_loans?

Нет — срез на выгрузку.

### 48. Можно ли final_decision как фичу для PD на approved?

Нет — это результат политики, не причина default.

### 49. Можно ли score_v1 при обучении с нуля?

Нет — это output существующей модели / политики.

### 50. Как безопасно использовать bureau_loans?

Фильтр open_date <= decision_date; без current status.

### 51. Как безопасно использовать bureau_snapshots?

As-of: snapshot_date <= decision_date, последний снимок.

### 52. Как безопасно использовать card_transactions?

txn_ts < decision_date, окно 3–6 месяцев.

### 53. Назовите 2 колонки-ловушки.

dpd_max и collection_calls_cnt из applications_full.

### 54. Что будет если обучить на applications_full?

Завышенный AUC — модель «подглядывает» в target.

### 55. Как проверить leakage?

Для каждой фичи: timestamp поля <= decision_date?

### 56. Что такое Reference Date?

decision_date — момент кредитного решения.

### 57. Что такое Performance Window?

[issue_date, issue_date + 12 months] для target.

### 58. Что такое Observation Window для фичей?

[decision_date - 6m, decision_date - 1d] для карт.

### 59. Почему as-of join важен для бюро?

Иначе берём будущий snapshot.

### 60. Сколько незрелых договоров?

5 364 (issue + 12m > 2025-05-31).

### 61. Можно ли маркировать Good незрелый договор?

Нет — окно performance не закрыто.

### 62. Когда target = NULL?

Незрелый и max_dpd < 90.

### 63. Когда target = 1 без закрытого окна?

Если max_dpd >= 90 — уже default.

### 64. Минимальная дата card txn?

2023-01-01.

### 65. Максимальная due_date в payments?

Проверено в date_ranges — до среза выгрузки.

### 66. Какой порог BAD выбран?

max DPD >= 90 дней.

### 67. Почему не 30 DPD?

22.8% bad — много краткосрочных задержек, шум.

### 68. Почему не 60 DPD?

15.9% — промежуточный; 90 — банковский стандарт default.

### 69. Bad rate 90+ на зрелых когортах?

7.4% – 14.3% по месяцам; среднее ~11%.

### 70. Сколько размеченных наблюдений?

6 561 с target_90 NOT NULL.

### 71. Как считается DPD для неоплаченного платежа?

2025-05-31 - due_date.

### 72. Как считается DPD если paid late?

paid_date - due_date.

### 73. На каком уровне агрегируется target?

Договор (contract), 1:1 с application.

### 74. Росла ли просрочка по когортам?

Монотонного роста нет на 90+ mature.

### 75. Почему bad_rate 100% для 2024-06+?

Артефакт: immature + early 90+; mature_n=0.

### 76. Какие краевые случаи target?

Частичная оплата, NULL paid_date, незрелые когорты.

### 77. Горизонт performance?

12 месяцев от issue_date.

### 78. Файл с target?

data/target_dataset.csv.

### 79. Колонки target dataset?

application_id, client_id, decision_date, issue_date, contract_id, max_dpd, window_closed, target_30/60/90.

### 80. SQL target?

sql/02_target.sql.

### 81. Что такое reject inference?

Оценка PD отклонённых заявок без наблюдаемого outcome.

### 82. Почему нельзя без допущений?

Нет платежей у rejected — target неизвестен.

### 83. Сколько rejected с bureau?

Большинство — есть snapshots (проверять as-of).

### 84. Чем rejected отличаются от approved?

Ниже доход, сумма, bureau score.

### 85. Что такое selection bias?

Approved — не случайная выборка из всех заявок.

### 86. Можно ли Heckman model?

Теоретически да, но нужны exclusion restrictions и validated assumptions.

### 87. Как использовать rejected в проекте?

Анализ смещения политики, не обучение PD.

### 88. Сколько rejected одобрила бы старая политика?

612.

### 89. Сколько фичей в датасете?

22+ в features_pre_decision.csv.

### 90. Как верифицировать доход?

salary_in_6m / declared_income_uzs.

### 91. Bad rate по каналам?

mobile 21.4%, agent 20.8%, branch 19.2%.

### 92. Bad rate по сумме?

Растёт с суммой: <5M 15.9%, 20M+ 23.7%.

### 93. Пропуски employment_months?

1 402 (7.8%).

### 94. Покрытие card transactions?

37% клиентов заявок.

### 95. Какой split для валидации?

Out-of-time по issue_date.

### 96. Метрики модели?

AUC/Gini + bad rate by decile + profit.

### 97. Что дороже: FN или FP?

FN (одобрили bad) — потери ~6M vs упущенная маржа ~1.8M.

### 98. Итоговый modeling dataset?

data/modeling_dataset.csv — target + features.

### 99. Как воспроизвести анализ?

uv run python projects/credit_scoring/scripts/run_analysis.py.

### 100. Где полный отчёт?

projects/credit_scoring/REPORT.md.

