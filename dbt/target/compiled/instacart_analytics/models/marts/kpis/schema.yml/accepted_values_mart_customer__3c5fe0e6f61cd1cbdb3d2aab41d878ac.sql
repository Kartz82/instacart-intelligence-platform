
    
    

with all_values as (

    select
        basket_size_score as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_kpis"."mart_customer_segments"
    group by basket_size_score

)

select *
from all_values
where value_field not in (
    '1','2','3','4','5'
)


