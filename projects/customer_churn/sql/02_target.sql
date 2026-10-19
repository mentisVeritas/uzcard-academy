-- Шаблон target для оттока.
-- Заполните после выбора: inactivity_days, snapshot_date, prediction_horizon_days.
--
-- Идея:
--   активный на snapshot  → смотрим, будет ли тишина >= N дней в горизонте
--   уже молчащий          → исключаем (ушёл раньше)
--   слишком новый         → исключаем (мало истории)
--   горизонт не закрыт    → target = NULL

-- Пример каркаса (подставить реальные имена таблиц после разведки):
/*
WITH params AS (
    SELECT
        DATE '2025-06-30' AS snapshot_date,   -- пример
        60 AS silence_days,                   -- порог тишины
        90 AS horizon_days                    -- горизонт наблюдения
),
base AS (
    SELECT
        c.customer_id,
        p.snapshot_date,
        -- last_txn_date до snapshot
        -- days_since_last_txn
        -- first_seen_date / registration_date
        1 AS placeholder
    FROM churn_customers c
    CROSS JOIN params p
    -- JOIN activity ...
)
SELECT
    customer_id,
    snapshot_date,
    CASE
        -- WHEN already_silent THEN NULL
        -- WHEN too_new THEN NULL
        -- WHEN horizon_not_closed THEN NULL
        -- WHEN silent_in_horizon THEN 1
        ELSE 0
    END AS target_churn
FROM base;
*/
