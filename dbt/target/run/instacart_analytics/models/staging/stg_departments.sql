
  create view "instacart_db"."analytics_staging"."stg_departments__dbt_tmp"
    
    
  as (
    select
    department_id::integer as department_id,
    department::varchar as department_name
from "instacart_db"."raw"."departments"
  );