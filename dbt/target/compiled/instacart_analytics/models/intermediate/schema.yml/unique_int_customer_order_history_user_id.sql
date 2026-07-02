
    
    

select
    user_id as unique_field,
    count(*) as n_records

from "instacart_db"."analytics_intermediate"."int_customer_order_history"
where user_id is not null
group by user_id
having count(*) > 1


