-- Сборка признаков. Окно: as_of = 2025-11-30, lookback = 6 мес., min tenure = 90 дней.
-- Персональное окно: feat_start = GREATEST(window_start, signup_date).
-- Источник правды: scripts/build_features.py (этот файл — копия SQL для сдачи).

WITH params AS (
    SELECT
        DATE '2025-11-30' AS as_of_date,
        (DATE '2025-11-30' - INTERVAL '6 months')::date AS window_start
),
eligible AS (
    SELECT
        c.customer_id,
        c.region,
        c.gender,
        DATE_PART('year', AGE(p.as_of_date, c.birth_date))::int AS age_years,
        c.signup_date,
        (p.as_of_date - c.signup_date)::int AS tenure_days,
        p.as_of_date,
        p.window_start,
        GREATEST(p.window_start, c.signup_date) AS feat_start
    FROM seg_customers c
    CROSS JOIN params p
    WHERE c.signup_date <= p.as_of_date - INTERVAL '90 days'
),
txn_feats AS (
    SELECT
        e.customer_id,
        COUNT(*) AS txn_cnt_all,
        COUNT(*) FILTER (WHERE t.direction = 'out') AS txn_cnt,
        COUNT(*) FILTER (WHERE t.direction = 'in') AS credit_cnt,
        COALESCE(SUM(t.amount_uzs) FILTER (WHERE t.direction = 'out'), 0) AS spend_uzs,
        COALESCE(SUM(t.amount_uzs) FILTER (WHERE t.direction = 'in'), 0) AS inflow_uzs,
        COUNT(DISTINCT t.channel) AS channel_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'pos') AS pos_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'ecom') AS ecom_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'p2p') AS p2p_cnt,
        COUNT(*) FILTER (WHERE t.channel = 'atm') AS atm_cnt,
        COUNT(DISTINCT t.mcc_group) AS mcc_cnt,
        MAX(t.txn_ts) AS last_txn_ts
    FROM eligible e
    JOIN seg_transactions t
        ON t.customer_id = e.customer_id
       AND t.txn_ts >= e.feat_start
       AND t.txn_ts < e.as_of_date + INTERVAL '1 day'
    GROUP BY 1
),
bal_feats AS (
    SELECT
        e.customer_id,
        AVG(b.avg_balance_uzs) AS avg_balance_uzs,
        STDDEV(b.avg_balance_uzs) AS balance_volatility
    FROM eligible e
    LEFT JOIN seg_balances b
        ON b.customer_id = e.customer_id
       AND b.month_start >= DATE_TRUNC('month', e.feat_start)::date
       AND b.month_start <= DATE_TRUNC('month', e.as_of_date)::date
    GROUP BY 1
),
rev_feats AS (
    SELECT
        e.customer_id,
        SUM(r.net_revenue_uzs) AS net_revenue_uzs,
        AVG(r.net_revenue_uzs) AS avg_monthly_revenue_uzs,
        SUM(r.interchange_uzs) AS interchange_uzs,
        SUM(r.float_income_uzs) AS float_income_uzs,
        SUM(r.transfer_fee_uzs) AS transfer_fee_uzs,
        SUM(r.atm_cost_uzs) AS atm_cost_uzs
    FROM eligible e
    LEFT JOIN seg_revenue_monthly r
        ON r.customer_id = e.customer_id
       AND r.month_start >= DATE_TRUNC('month', e.feat_start)::date
       AND r.month_start <= DATE_TRUNC('month', e.as_of_date)::date
    GROUP BY 1
),
prod_feats AS (
    SELECT
        e.customer_id,
        COUNT(DISTINCT p.product_code) AS product_cnt
    FROM eligible e
    LEFT JOIN seg_products p
        ON p.customer_id = e.customer_id
       AND p.opened_at <= e.as_of_date
    GROUP BY 1
)
SELECT
    e.customer_id,
    e.region,
    e.gender,
    e.age_years,
    e.tenure_days,
    e.as_of_date,
    e.window_start,
    e.feat_start,
    (e.as_of_date - e.feat_start)::int + 1 AS window_days,
    COALESCE(t.txn_cnt_all, 0) AS txn_cnt_all,
    COALESCE(t.txn_cnt, 0) AS txn_cnt,
    COALESCE(t.credit_cnt, 0) AS credit_cnt,
    COALESCE(t.spend_uzs, 0) AS spend_uzs,
    COALESCE(t.inflow_uzs, 0) AS inflow_uzs,
    COALESCE(t.channel_cnt, 0) AS channel_cnt,
    COALESCE(t.pos_cnt, 0) AS pos_cnt,
    COALESCE(t.ecom_cnt, 0) AS ecom_cnt,
    COALESCE(t.p2p_cnt, 0) AS p2p_cnt,
    COALESCE(t.atm_cnt, 0) AS atm_cnt,
    COALESCE(t.mcc_cnt, 0) AS mcc_cnt,
    t.last_txn_ts,
    COALESCE(b.avg_balance_uzs, 0) AS avg_balance_uzs,
    COALESCE(b.balance_volatility, 0) AS balance_volatility,
    COALESCE(r.net_revenue_uzs, 0) AS net_revenue_uzs,
    COALESCE(r.avg_monthly_revenue_uzs, 0) AS avg_monthly_revenue_uzs,
    COALESCE(r.interchange_uzs, 0) AS interchange_uzs,
    COALESCE(r.float_income_uzs, 0) AS float_income_uzs,
    COALESCE(r.transfer_fee_uzs, 0) AS transfer_fee_uzs,
    COALESCE(r.atm_cost_uzs, 0) AS atm_cost_uzs,
    COALESCE(p.product_cnt, 0) AS product_cnt,
    CASE WHEN COALESCE(t.txn_cnt_all, 0) >= 1 THEN 1 ELSE 0 END AS active_in_window
FROM eligible e
LEFT JOIN txn_feats t ON t.customer_id = e.customer_id
LEFT JOIN bal_feats b ON b.customer_id = e.customer_id
LEFT JOIN rev_feats r ON r.customer_id = e.customer_id
LEFT JOIN prod_feats p ON p.customer_id = e.customer_id;
