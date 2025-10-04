with customers as (

    select * from {{ ref('stg_customers') }}

),

orders as (

    select * from {{ ref('stg_orders') }}

),

-- Get the most recent order date across all data to use as "current date"
current_date_cte as (
    select max(order_date) as current_date
    from orders
),

customer_order_summary as (

    select
        customer_id,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,
        count(*) as total_orders,
        sum(case when status = 'completed' then 1 else 0 end) as completed_orders
    from orders
    group by customer_id

),

at_risk_customers as (

    select
        c.customer_id,
        c.first_name,
        c.last_name,
        cos.first_order_date,
        cos.last_order_date,
        cos.total_orders,
        cos.completed_orders,
        cd.current_date,
        (cd.current_date - cos.last_order_date) as days_since_last_order
    from customers c
    inner join customer_order_summary cos
        on c.customer_id = cos.customer_id
    cross join current_date_cte cd
    where (cd.current_date - cos.last_order_date) > 60
        and cos.total_orders > 0  -- ensure they have prior activity

)

select * from at_risk_customers
order by days_since_last_order desc