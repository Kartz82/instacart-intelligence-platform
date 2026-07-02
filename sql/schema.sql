CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.departments (
    department_id INTEGER PRIMARY KEY,
    department VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.aisles (
    aisle_id INTEGER PRIMARY KEY,
    aisle VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    aisle_id INTEGER NOT NULL REFERENCES raw.aisles(aisle_id),
    department_id INTEGER NOT NULL REFERENCES raw.departments(department_id)
);

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    eval_set VARCHAR(10) NOT NULL,
    order_number INTEGER NOT NULL,
    order_dow INTEGER NOT NULL,
    order_hour_of_day INTEGER NOT NULL,
    days_since_prior_order DOUBLE PRECISION,
    CONSTRAINT orders_eval_set_check
        CHECK (eval_set IN ('prior', 'train', 'test')),
    CONSTRAINT orders_dow_check
        CHECK (order_dow BETWEEN 0 AND 6),
    CONSTRAINT orders_hour_check
        CHECK (order_hour_of_day BETWEEN 0 AND 23)
);

CREATE TABLE IF NOT EXISTS raw.order_products (
    order_id INTEGER NOT NULL REFERENCES raw.orders(order_id),
    product_id INTEGER NOT NULL REFERENCES raw.products(product_id),
    add_to_cart_order INTEGER NOT NULL,
    reordered INTEGER NOT NULL,
    PRIMARY KEY (order_id, product_id),
    CONSTRAINT order_products_reordered_check
        CHECK (reordered IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_raw_orders_user_id
    ON raw.orders(user_id);

CREATE INDEX IF NOT EXISTS idx_raw_orders_eval_set
    ON raw.orders(eval_set);

CREATE INDEX IF NOT EXISTS idx_raw_order_products_product_id
    ON raw.order_products(product_id);

CREATE INDEX IF NOT EXISTS idx_raw_products_aisle_id
    ON raw.products(aisle_id);

CREATE INDEX IF NOT EXISTS idx_raw_products_department_id
    ON raw.products(department_id);
