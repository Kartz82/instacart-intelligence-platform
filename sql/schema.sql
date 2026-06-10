CREATE TABLE IF NOT EXISTS departments (
    department_id INT PRIMARY KEY,
    department VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS aisles (
    aisle_id INT PRIMARY KEY,
    aisle VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    aisle_id INT REFERENCES aisles(aisle_id),
    department_id INT REFERENCES departments(department_id)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    eval_set VARCHAR(10),
    order_number INT NOT NULL,
    order_dow INT NOT NULL,
    order_hour_of_day INT NOT NULL,
    days_since_prior_order DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS order_products (
    order_id INT,
    product_id INT REFERENCES products(product_id),
    add_to_cart_order INT,
    reordered INT,
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_products_product_id ON order_products(product_id);
CREATE INDEX IF NOT EXISTS idx_products_department_id ON products(department_id);