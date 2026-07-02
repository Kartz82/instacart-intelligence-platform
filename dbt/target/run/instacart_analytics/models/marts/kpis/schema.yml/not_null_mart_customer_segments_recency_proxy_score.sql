
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select recency_proxy_score
from "instacart_db"."analytics_kpis"."mart_customer_segments"
where recency_proxy_score is null



  
  
      
    ) dbt_internal_test