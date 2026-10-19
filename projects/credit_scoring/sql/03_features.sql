-- Фичи, доступные на decision_date (as-of join)

-- Бюро: последний снимок НЕ ПОЗЖЕ decision_date
WITH bureau_asof AS (
    SELECT DISTINCT ON (a.application_id)
        a.application_id,
        s.bureau_score,
        s.existing_debt_uzs,
        s.active_loans_cnt,
        s.snapshot_date
    FROM scoring_applications a
    JOIN scoring_bureau_snapshots s
        ON a.client_id = s.client_id
        AND s.snapshot_date <= a.decision_date
    WHERE a.final_decision = 'approved'
    ORDER BY a.application_id, s.snapshot_date DESC
),
-- Запросы в бюро за 6 месяцев до решения
inq_6m AS (
    SELECT
        a.application_id,
        COUNT(*) AS inq_cnt_6m
    FROM scoring_applications a
    JOIN scoring_bureau_inquiries i
        ON a.client_id = i.client_id
        AND i.inquiry_date BETWEEN a.decision_date - INTERVAL '6 months' AND a.decision_date
    WHERE a.final_decision = 'approved'
    GROUP BY 1
),
-- Карточное поведение за 6 месяцев ДО decision_date (не включая день решения)
card_6m AS (
    SELECT
        a.application_id,
        COUNT(*) FILTER (WHERE t.status = 'approved') AS txn_approved_6m,
        COUNT(*) FILTER (WHERE t.status = 'declined') AS txn_declined_6m,
        SUM(CASE WHEN t.status = 'approved' THEN t.amount_uzs ELSE 0 END) AS spend_6m,
        SUM(CASE WHEN t.txn_type = 'salary_in' AND t.status = 'approved'
            THEN t.amount_uzs ELSE 0 END) AS salary_in_6m
    FROM scoring_applications a
    JOIN scoring_card_transactions t
        ON a.client_id = t.client_id
        AND t.txn_ts::date BETWEEN a.decision_date - INTERVAL '6 months'
                               AND a.decision_date - INTERVAL '1 day'
    WHERE a.final_decision = 'approved'
    GROUP BY 1
)
SELECT
    a.application_id,
    a.client_id,
    a.decision_date,
    a.channel,
    a.purpose,
    a.requested_amount_uzs,
    a.term_months,
    a.declared_income_uzs,
    a.employment_months,
    cu.gender,
    cu.region,
    cu.customer_segment,
    EXTRACT(YEAR FROM age(a.decision_date, cu.birth_date))::int AS age_at_decision,
    b.bureau_score,
    b.existing_debt_uzs,
    b.active_loans_cnt,
    COALESCE(i.inq_cnt_6m, 0) AS inq_cnt_6m,
    COALESCE(c.txn_approved_6m, 0) AS txn_approved_6m,
    COALESCE(c.txn_declined_6m, 0) AS txn_declined_6m,
    COALESCE(c.spend_6m, 0) AS spend_6m,
    COALESCE(c.salary_in_6m, 0) AS salary_in_6m
FROM scoring_applications a
LEFT JOIN scoring_customers cu ON a.client_id = cu.customer_id
LEFT JOIN bureau_asof b ON a.application_id = b.application_id
LEFT JOIN inq_6m i ON a.application_id = i.application_id
LEFT JOIN card_6m c ON a.application_id = c.application_id
WHERE a.final_decision = 'approved';
