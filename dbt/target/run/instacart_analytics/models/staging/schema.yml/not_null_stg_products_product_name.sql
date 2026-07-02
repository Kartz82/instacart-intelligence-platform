
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select product_name
from "instacart_db"."analytics_staging"."stg_products"
where product_name is null



  
  
      
    ) dbt_internal_test