
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select average_orders_per_customer
from "instacart_db"."analytics_kpis"."mart_executive_kpis"
where average_orders_per_customer is null



  
  
      
    ) dbt_internal_test