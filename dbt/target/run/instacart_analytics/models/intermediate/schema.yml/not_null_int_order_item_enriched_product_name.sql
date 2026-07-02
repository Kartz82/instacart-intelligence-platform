
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select product_name
from "instacart_db"."analytics_intermediate"."int_order_item_enriched"
where product_name is null



  
  
      
    ) dbt_internal_test