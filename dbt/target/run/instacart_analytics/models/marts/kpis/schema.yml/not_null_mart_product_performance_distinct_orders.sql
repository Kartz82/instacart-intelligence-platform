
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select distinct_orders
from "instacart_db"."analytics_kpis"."mart_product_performance"
where distinct_orders is null



  
  
      
    ) dbt_internal_test