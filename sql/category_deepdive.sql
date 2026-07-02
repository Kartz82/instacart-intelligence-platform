/*
Category and SKU performance views for merchandising analytics.

These queries are intentionally compact and interview-friendly: they summarize
department volume, department reorder behavior, and top SKU velocity from the
warehouse tables populated by src/database_loader.py.
*/

DROP VIEW IF EXISTS department_performance;
DROP VIEW IF EXISTS top_product_velocity;

CREATE VIEW department_performance AS
SELECT
    d.department_id,
    d.department,
    COUNT(op.order_id) AS total_item_purchases,
    COUNT(DISTINCT op.order_id) AS distinct_orders,
    COUNT(DISTINCT op.product_id) AS distinct_products,
    ROUND(AVG(op.reordered)::NUMERIC, 3) AS reorder_rate,
    ROUND(COUNT(op.order_id)::NUMERIC / NULLIF(COUNT(DISTINCT op.order_id), 0), 2) AS avg_department_items_per_order
FROM order_products op
JOIN products p
    ON op.product_id = p.product_id
JOIN departments d
    ON p.department_id = d.department_id
GROUP BY d.department_id, d.department;

CREATE VIEW top_product_velocity AS
SELECT
    p.product_id,
    p.product_name,
    d.department,
    a.aisle,
    COUNT(op.order_id) AS purchase_count,
    COUNT(DISTINCT op.order_id) AS order_count,
    ROUND(AVG(op.reordered)::NUMERIC, 3) AS reorder_rate
FROM order_products op
JOIN products p
    ON op.product_id = p.product_id
JOIN departments d
    ON p.department_id = d.department_id
JOIN aisles a
    ON p.aisle_id = a.aisle_id
GROUP BY p.product_id, p.product_name, d.department, a.aisle;

SELECT
    department,
    total_item_purchases,
    distinct_orders,
    distinct_products,
    reorder_rate
FROM department_performance
ORDER BY total_item_purchases DESC
LIMIT 15;

SELECT
    product_name,
    department,
    aisle,
    purchase_count,
    reorder_rate
FROM top_product_velocity
ORDER BY purchase_count DESC
LIMIT 20;
