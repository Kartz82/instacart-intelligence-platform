
  create view "instacart_db"."analytics_staging"."stg_order_products__dbt_tmp"
    
    
  as (
    select
    order_id::integer as order_id,
    product_id::integer as product_id,
    add_to_cart_order::integer as add_to_cart_order,
    reordered::integer as reordered
from "instacart_db"."raw"."order_products"
  );