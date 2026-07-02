
    
    

with child as (
    select order_id as from_field
    from "instacart_db"."analytics_intermediate"."int_order_item_enriched"
    where order_id is not null
),

parent as (
    select order_id as to_field
    from "instacart_db"."analytics_staging"."stg_orders"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


