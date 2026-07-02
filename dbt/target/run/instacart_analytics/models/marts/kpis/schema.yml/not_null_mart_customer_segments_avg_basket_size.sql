
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select avg_basket_size
from "instacart_db"."analytics_kpis"."mart_customer_segments"
where avg_basket_size is null



  
  
      
    ) dbt_internal_test