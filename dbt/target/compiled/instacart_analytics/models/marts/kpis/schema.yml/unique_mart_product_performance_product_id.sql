
    
    

select
    product_id as unique_field,
    count(*) as n_records

from "instacart_db"."analytics_kpis"."mart_product_performance"
where product_id is not null
group by product_id
having count(*) > 1


