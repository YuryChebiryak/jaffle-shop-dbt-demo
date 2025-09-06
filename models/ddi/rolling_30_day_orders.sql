{{ config(
    materialized='table',
    schema='ddi'
) }}

WITH completed_orders AS (
    -- Get completed orders with their payment amounts
    SELECT
        CAST(o.order_date AS DATE) AS order_date,
        CAST(p.amount AS DECIMAL(10,2)) AS amount
    FROM {{ ref('stg_orders') }} o
    INNER JOIN {{ ref('stg_payments') }} p
        ON o.order_id = p.order_id
    WHERE o.status = 'completed'
),

daily_totals AS (
    -- Aggregate total amount per day
    SELECT
        order_date,
        CAST(SUM(amount) AS DECIMAL(12,2)) AS total_amount,
        CAST(COUNT(*) AS DECIMAL(10,0)) AS order_count
    FROM completed_orders
    GROUP BY order_date
),

rolling_30_day AS (
    -- Calculate rolling 30-day aggregations
    SELECT
        order_date,
        total_amount,
        order_count,
        -- Rolling sum of total_amount over 30 days
        CAST(SUM(total_amount) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS DECIMAL(15,2)) AS rolling_30_day_amount,
        -- Rolling count of orders over 30 days
        CAST(SUM(order_count) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS DECIMAL(15,0)) AS rolling_30_day_orders,
        -- Rolling average daily amount over 30 days
        CAST(AVG(total_amount) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS DECIMAL(12,2)) AS rolling_30_day_avg_daily
    FROM daily_totals
)

-- Get the last 50 data points ordered by most recent date first
SELECT
    order_date,
    total_amount,
    order_count,
    rolling_30_day_amount,
    rolling_30_day_orders,
    rolling_30_day_avg_daily
FROM rolling_30_day
ORDER BY order_date DESC
FETCH FIRST 50 ROWS ONLY