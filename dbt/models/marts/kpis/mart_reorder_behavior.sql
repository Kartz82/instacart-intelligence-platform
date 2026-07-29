-- Reorder behaviour at the department x aisle grain, benchmarked against its department.
--
-- Grain choice: product-level reorder rate already lives in mart_product_performance
-- and customer-level reorder rate already lives in dim_customers. The missing cut is
-- the category rollup, which is also the only one small enough to import whole into
-- the BI layer. One row per department x aisle.
--
-- Volume floor: aisles with very few line items produce unstable rates, so a floor is
-- flagged rather than filtered. Filtering would silently drop long-tail categories from
-- the BI totals; flagging lets the dashboard grey them out while keeping the sums honest.

{% set volume_floor = 1000 %}

with aisle_reorder as (
    select
        order_items.department_id,
        order_items.aisle_id,
        count(*) as total_order_items,
        sum(order_items.reordered) as reordered_items,
        count(distinct order_items.order_id) as distinct_orders,
        count(distinct order_items.user_id) as distinct_customers,
        count(distinct order_items.product_id) as distinct_products
    from {{ ref('fact_order_items') }} as order_items
    group by order_items.department_id, order_items.aisle_id
),

department_reorder as (
    select
        department_id,
        sum(total_order_items) as department_order_items,
        sum(reordered_items) as department_reordered_items
    from aisle_reorder
    group by department_id
),

platform_reorder as (
    select
        sum(total_order_items) as platform_order_items,
        sum(reordered_items) as platform_reordered_items
    from aisle_reorder
),

labelled as (
    select
        aisle_reorder.department_id,
        products.department_name,
        aisle_reorder.aisle_id,
        products.aisle_name,
        aisle_reorder.total_order_items,
        aisle_reorder.reordered_items,
        aisle_reorder.distinct_orders,
        aisle_reorder.distinct_customers,
        aisle_reorder.distinct_products,
        department_reorder.department_order_items,
        department_reorder.department_reordered_items,
        platform_reorder.platform_order_items,
        platform_reorder.platform_reordered_items
    from aisle_reorder
    inner join department_reorder
        on aisle_reorder.department_id = department_reorder.department_id
    inner join (
        select distinct
            aisle_id,
            aisle_name,
            department_id,
            department_name
        from {{ ref('dim_products') }}
    ) as products
        on aisle_reorder.aisle_id = products.aisle_id
        and aisle_reorder.department_id = products.department_id
    cross join platform_reorder
),

rated as (
    select
        *,
        round(
            cast(reordered_items as {{ dbt.type_numeric() }})
            / nullif(total_order_items, 0),
            4
        ) as reorder_rate,
        round(
            cast(department_reordered_items as {{ dbt.type_numeric() }})
            / nullif(department_order_items, 0),
            4
        ) as department_reorder_rate,
        round(
            cast(platform_reordered_items as {{ dbt.type_numeric() }})
            / nullif(platform_order_items, 0),
            4
        ) as platform_reorder_rate
    from labelled
)

select
    department_id,
    department_name,
    aisle_id,
    aisle_name,
    total_order_items,
    reordered_items,
    distinct_orders,
    distinct_customers,
    distinct_products,
    reorder_rate,
    department_reorder_rate,
    platform_reorder_rate,
    round(reorder_rate - department_reorder_rate, 4) as reorder_rate_vs_department,
    round(reorder_rate - platform_reorder_rate, 4) as reorder_rate_vs_platform,
    case
        when total_order_items < {{ volume_floor }} then true
        else false
    end as below_volume_floor,
    round(
        cast(total_order_items as {{ dbt.type_numeric() }})
        / nullif(platform_order_items, 0),
        6
    ) as share_of_order_items
from rated
