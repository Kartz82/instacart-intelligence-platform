
    
    

select
    kpi_snapshot_id as unique_field,
    count(*) as n_records

from "instacart_db"."analytics_kpis"."mart_executive_kpis"
where kpi_snapshot_id is not null
group by kpi_snapshot_id
having count(*) > 1


