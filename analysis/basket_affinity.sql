/*
Business question:
Which frequently purchased products tend to appear in the same basket?

Notes:
- This is SQL-first product affinity analysis, not prediction.
- Product pairs are pre-filtered in the dbt mart to keep output practical.
*/

select
    product_a_id,
    product_a_name,
    product_b_id,
    product_b_name,
    orders_with_a,
    orders_with_b,
    orders_with_both,
    support,
    confidence_a_to_b,
    lift
from analytics_analysis.mart_basket_affinity
order by lift desc, orders_with_both desc
limit 50;

/*
High-support pairs can be useful for merchandising and dashboard callouts.
*/

select
    product_a_name,
    product_b_name,
    orders_with_both,
    support,
    confidence_a_to_b,
    lift
from analytics_analysis.mart_basket_affinity
order by support desc, lift desc
limit 50;
