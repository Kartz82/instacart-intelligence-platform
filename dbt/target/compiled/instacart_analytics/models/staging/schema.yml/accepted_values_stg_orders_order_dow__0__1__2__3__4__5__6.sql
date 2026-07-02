
    
    

with all_values as (

    select
        order_dow as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_staging"."stg_orders"
    group by order_dow

)

select *
from all_values
where value_field not in (
    '0','1','2','3','4','5','6'
)


