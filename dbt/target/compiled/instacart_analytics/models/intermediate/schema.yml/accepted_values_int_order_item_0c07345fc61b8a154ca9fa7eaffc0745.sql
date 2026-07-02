
    
    

with all_values as (

    select
        eval_set as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_intermediate"."int_order_item_enriched"
    group by eval_set

)

select *
from all_values
where value_field not in (
    'prior','train','test'
)


