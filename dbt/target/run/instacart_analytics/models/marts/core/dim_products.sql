
  
    

  create  table "instacart_db"."analytics_core"."dim_products__dbt_tmp"
  
  
    as
  
  (
    select
    products.product_id,
    products.product_name,
    products.aisle_id,
    aisles.aisle_name,
    products.department_id,
    departments.department_name
from "instacart_db"."analytics_staging"."stg_products" as products
inner join "instacart_db"."analytics_staging"."stg_aisles" as aisles
    on products.aisle_id = aisles.aisle_id
inner join "instacart_db"."analytics_staging"."stg_departments" as departments
    on products.department_id = departments.department_id
  );
  