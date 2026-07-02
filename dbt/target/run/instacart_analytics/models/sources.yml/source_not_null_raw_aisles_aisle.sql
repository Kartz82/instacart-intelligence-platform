
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select aisle
from "instacart_db"."raw"."aisles"
where aisle is null



  
  
      
    ) dbt_internal_test