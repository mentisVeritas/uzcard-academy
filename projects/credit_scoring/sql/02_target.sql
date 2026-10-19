-- Target: ever 90+ DPD в 12-месячном performance window после issue_date
-- As-of date среза: 2025-05-31
-- Reference date для фичей: decision_date
-- Performance window: due_date <= issue_date + 12 months (и due_date <= as-of для наблюдаемых платежей)

-- Запрос 1: датасет target (application_id, client_id, decision_date, target)
WITH payment_dpd AS (
    SELECT
        p.contract_id,
        c.issue_date,
        p.installment_no,
        p.due_date,
        p.paid_date,
        (c.issue_date + INTERVAL '12 months')::date AS perf_end,
        CASE
            WHEN p.paid_date IS NULL THEN
                CASE
                    WHEN p.due_date <= DATE '2025-05-31'
                        THEN DATE '2025-05-31' - p.due_date
                    ELSE 0
                END
            ELSE GREATEST(0, p.paid_date - p.due_date)
        END AS dpd_days
    FROM scoring_payments p
    JOIN scoring_contracts c ON p.contract_id = c.contract_id
),
contract_perf AS (
    SELECT
        c.contract_id,
        c.application_id,
        c.client_id,
        c.issue_date,
        c.term_months,
        c.issued_amount_uzs,
        (c.issue_date + INTERVAL '12 months')::date AS perf_end,
        MAX(pd.dpd_days) FILTER (
            WHERE pd.due_date <= DATE '2025-05-31'
              AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
        ) AS max_dpd,
        COUNT(*) FILTER (
            WHERE pd.due_date <= DATE '2025-05-31'
              AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
        ) AS installments_in_window,
        CASE
            WHEN (c.issue_date + INTERVAL '12 months')::date <= DATE '2025-05-31'
             AND COUNT(*) FILTER (
                    WHERE pd.due_date <= DATE '2025-05-31'
                      AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
                 ) >= 1
                THEN 1
            ELSE 0
        END AS window_closed
    FROM scoring_contracts c
    LEFT JOIN payment_dpd pd ON c.contract_id = pd.contract_id
    GROUP BY 1, 2, 3, 4, 5, 6
)
SELECT
    a.application_id,
    a.client_id,
    a.decision_date,
    cp.issue_date,
    cp.contract_id,
    cp.max_dpd,
    cp.window_closed,
    cp.installments_in_window,
    CASE
        WHEN COALESCE(cp.max_dpd, 0) >= 90 THEN 1
        WHEN cp.window_closed = 1 AND COALESCE(cp.max_dpd, 0) < 90 THEN 0
        ELSE NULL
    END AS target
FROM scoring_applications a
JOIN contract_perf cp ON a.application_id = cp.application_id
WHERE a.final_decision = 'approved';


-- Запрос 2: bad rate по месяцам выдачи (только зрелые когорты)
WITH payment_dpd AS (
    SELECT
        p.contract_id,
        c.issue_date,
        p.due_date,
        CASE
            WHEN p.paid_date IS NULL THEN
                CASE
                    WHEN p.due_date <= DATE '2025-05-31'
                        THEN DATE '2025-05-31' - p.due_date
                    ELSE 0
                END
            ELSE GREATEST(0, p.paid_date - p.due_date)
        END AS dpd_days
    FROM scoring_payments p
    JOIN scoring_contracts c ON p.contract_id = c.contract_id
),
contract_perf AS (
    SELECT
        c.contract_id,
        c.issue_date,
        MAX(pd.dpd_days) FILTER (
            WHERE pd.due_date <= DATE '2025-05-31'
              AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
        ) AS max_dpd,
        CASE
            WHEN (c.issue_date + INTERVAL '12 months')::date <= DATE '2025-05-31'
             AND COUNT(*) FILTER (
                    WHERE pd.due_date <= DATE '2025-05-31'
                      AND pd.due_date <= (c.issue_date + INTERVAL '12 months')::date
                 ) >= 1
                THEN 1
            ELSE 0
        END AS window_closed
    FROM scoring_contracts c
    LEFT JOIN payment_dpd pd ON c.contract_id = pd.contract_id
    GROUP BY 1, 2
)
SELECT
    DATE_TRUNC('month', issue_date)::date AS issue_month,
    COUNT(*) FILTER (WHERE window_closed = 1) AS n_mature,
    ROUND(
        AVG(
            CASE
                WHEN window_closed = 1 AND COALESCE(max_dpd, 0) >= 90 THEN 1.0
                WHEN window_closed = 1 THEN 0.0
            END
        )::numeric,
        4
    ) AS bad_rate_90
FROM contract_perf
GROUP BY 1
ORDER BY 1;
