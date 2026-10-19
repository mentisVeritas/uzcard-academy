-- Фичи строго до snapshot_date.
-- Заполнить после выбора рабочих таблиц churn_*.
/*
SELECT
    b.customer_id,
    b.snapshot_date,
    -- txn_cnt_30d, txn_cnt_90d, spend_30d, days_since_last_txn,
    -- app_sessions_30d, support_tickets_90d, products_cnt, ...
    1 AS placeholder
FROM base b
-- LEFT JOIN ... ON ... AND event_ts < b.snapshot_date
;
*/
