
    
    

with child as (
    select product_b_id as from_field
    from "instacart_db"."analytics_analysis"."mart_basket_affinity"
    where product_b_id is not null
),

parent as (
    select product_id as to_field
    from "instacart_db"."analytics_core"."dim_products"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


