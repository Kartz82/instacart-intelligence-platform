
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select total_products
from "instacart_db"."analytics_kpis"."mart_executive_kpis"
where total_products is null



  
  
      
    ) dbt_internal_test