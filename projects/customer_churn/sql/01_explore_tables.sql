-- Разведка: все таблицы задания churn_*
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE 'churn\_%' ESCAPE '\'
ORDER BY 1;

-- Размеры и примерный объём
SELECT
    relname AS table_name,
    n_live_tup AS approx_rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
  AND relname LIKE 'churn\_%' ESCAPE '\'
ORDER BY n_live_tup DESC;

-- Колонки по таблицам
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name LIKE 'churn\_%' ESCAPE '\'
ORDER BY table_name, ordinal_position;
