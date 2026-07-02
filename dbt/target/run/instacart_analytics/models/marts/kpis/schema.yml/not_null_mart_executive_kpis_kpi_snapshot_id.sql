
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select kpi_snapshot_id
from "instacart_db"."analytics_kpis"."mart_executive_kpis"
where kpi_snapshot_id is null



  
  
      
    ) dbt_internal_test