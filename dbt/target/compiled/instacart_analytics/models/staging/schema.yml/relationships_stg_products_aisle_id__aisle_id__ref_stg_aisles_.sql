
    
    

with child as (
    select aisle_id as from_field
    from "instacart_db"."analytics_staging"."stg_products"
    where aisle_id is not null
),

parent as (
    select aisle_id as to_field
    from "instacart_db"."analytics_staging"."stg_aisles"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


