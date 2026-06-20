{{ config(
    materialized='external',
    format='iceberg',
    schema='ddi'
) }}

WITH completed_orders AS (
    SELECT
        CAST(o.order_date AS DATE) AS order_date,
        CAST(p.amount AS DECIMAL(38,8)) AS amount
    FROM {{ ref('stg_orders') }} o
    INNER JOIN {{ ref('stg_payments') }} p
        ON o.order_id = p.order_id
    WHERE o.status = 'completed'
),

daily_totals AS (
    SELECT
        order_date,
        CAST(SUM(amount) AS DECIMAL(38,8)) AS total_amount,
        CAST(COUNT(*) AS DECIMAL(38,8)) AS order_count
    FROM completed_orders
    GROUP BY order_date
),

rolling_30_day AS (
    SELECT
        order_date,
        total_amount,
        order_count,
        CAST(SUM(total_amount) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS DECIMAL(38,8)) AS rolling_30_day_amount,
        CAST(SUM(order_count) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS DECIMAL(38,8)) AS rolling_30_day_orders,
        CAST(AVG(total_amount) OVER (
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS DECIMAL(38,8)) AS rolling_30_day_avg_daily
    FROM daily_totals
)

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
