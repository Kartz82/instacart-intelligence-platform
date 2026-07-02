select
    product_a_id,
    product_b_id,
    count(*) as row_count
from "instacart_db"."analytics_analysis"."mart_basket_affinity"
group by product_a_id, product_b_id
having count(*) > 1