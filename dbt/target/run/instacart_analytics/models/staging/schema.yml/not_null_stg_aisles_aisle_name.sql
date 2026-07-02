
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select aisle_name
from "instacart_db"."analytics_staging"."stg_aisles"
where aisle_name is null



  
  
      
    ) dbt_internal_test