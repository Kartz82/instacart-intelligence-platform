
  create view "instacart_db"."analytics_staging"."stg_aisles__dbt_tmp"
    
    
  as (
    select
    aisle_id::integer as aisle_id,
    aisle::varchar as aisle_name
from "instacart_db"."raw"."aisles"
  );