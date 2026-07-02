
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select eval_set
from "instacart_db"."analytics_intermediate"."int_order_item_enriched"
where eval_set is null



  
  
      
    ) dbt_internal_test