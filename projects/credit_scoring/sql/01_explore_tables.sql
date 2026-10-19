-- Этап 1-2: обзор всех scoring_ таблиц
SELECT tablename,
       (xpath('/row/cnt/text()', query_to_xml(format('SELECT COUNT(*) AS cnt FROM %I', tablename), false, true,
                                              '')))[1]::text::int AS row_count
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE 'scoring\_%'
ORDER BY tablename;

-- Структура колонок
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name LIKE 'scoring\_%'
ORDER BY table_name, ordinal_position;

-- Решения по заявкам
SELECT final_decision,
       COUNT(*)                                           cnt,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) pct
FROM scoring_applications
GROUP BY 1;

-- Связь заявка → договор
SELECT COUNT(*)                                             AS approved,
       (SELECT COUNT(*) FROM scoring_contracts)             AS contracts,
       COUNT(*) FILTER (WHERE c.application_id IS NOT NULL) AS matched
FROM scoring_applications a
         LEFT JOIN scoring_contracts c ON a.application_id = c.application_id
WHERE a.final_decision = 'approved';

-- Диапазоны дат
SELECT 'applications' AS src, MIN(decision_date), MAX(decision_date)
FROM scoring_applications
UNION ALL
SELECT 'contracts', MIN(issue_date), MAX(issue_date)
FROM scoring_contracts
UNION ALL
SELECT 'payments_due', MIN(due_date), MAX(due_date)
FROM scoring_payments
UNION ALL
SELECT 'payments_paid', MIN(paid_date), MAX(paid_date)
FROM scoring_payments
UNION ALL
SELECT 'bureau_snapshots', MIN(snapshot_date), MAX(snapshot_date)
FROM scoring_bureau_snapshots
UNION ALL
SELECT 'card_txn', MIN(txn_ts::date), MAX(txn_ts::date)
FROM scoring_card_transactions;

-- Покрытие клиентов картами
SELECT COUNT(DISTINCT a.client_id) AS all_app_clients,
       COUNT(DISTINCT a.client_id) FILTER (
           WHERE EXISTS (SELECT 1 FROM scoring_card_transactions t WHERE t.client_id = a.client_id)
           )                       AS with_card_txn,
       COUNT(DISTINCT a.client_id) FILTER (
           WHERE EXISTS (SELECT 1 FROM scoring_customers c WHERE c.customer_id = a.client_id)
           )                       AS in_customers
FROM scoring_applications a;
