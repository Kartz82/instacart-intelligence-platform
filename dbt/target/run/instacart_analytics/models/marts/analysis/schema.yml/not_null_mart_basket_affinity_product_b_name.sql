
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select product_b_name
from "instacart_db"."analytics_analysis"."mart_basket_affinity"
where product_b_name is null



  
  
      
    ) dbt_internal_test