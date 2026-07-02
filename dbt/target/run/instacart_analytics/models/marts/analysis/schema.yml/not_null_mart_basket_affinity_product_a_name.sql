
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select product_a_name
from "instacart_db"."analytics_analysis"."mart_basket_affinity"
where product_a_name is null



  
  
      
    ) dbt_internal_test