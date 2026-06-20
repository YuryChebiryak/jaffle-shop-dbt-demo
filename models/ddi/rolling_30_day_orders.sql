{{ config(
    materialized='external',
    format='iceberg',
    schema='ddi'
) }}

WITH completed_orders AS (
    SELECT
        CAST(o.order_date AS DATE) AS order_date,
        p.amount  -- cents, BIGINT
    FROM {{ ref('stg_orders') }} o
    INNER JOIN {{ ref('stg_payments') }} p
        ON o.order_id = p.order_id
    WHERE o.status = 'completed'
),

daily_totals AS (
    SELECT
        order_date,
        SUM(amount) AS total_amount_cents,
        COUNT(*) AS order_count
    FROM completed_orders
    GROUP BY order_date
),

rolling_30_day AS (
    SELECT
        order_date,
        total_amount_cents,
        order_count,
        SUM(total_amount_cents) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS rolling_30_day_amount_cents,
        SUM(order_count) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS rolling_30_day_orders,
        AVG(total_amount_cents) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS rolling_30_day_avg_daily_cents
    FROM daily_totals
)

SELECT
    order_date,
    CAST(total_amount_cents / 100.0 AS DECIMAL(18,2))          AS total_amount,
    order_count,
    CAST(rolling_30_day_amount_cents / 100.0 AS DECIMAL(18,2)) AS rolling_30_day_amount,
    CAST(rolling_30_day_orders AS BIGINT) AS rolling_30_day_orders,
    CAST(rolling_30_day_avg_daily_cents / 100.0 AS DECIMAL(18,2)) AS rolling_30_day_avg_daily
FROM rolling_30_day
ORDER BY order_date DESC
FETCH FIRST 50 ROWS ONLY
