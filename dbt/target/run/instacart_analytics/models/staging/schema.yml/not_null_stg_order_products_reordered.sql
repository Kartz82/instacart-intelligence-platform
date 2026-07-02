
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select reordered
from "instacart_db"."analytics_staging"."stg_order_products"
where reordered is null



  
  
      
    ) dbt_internal_test