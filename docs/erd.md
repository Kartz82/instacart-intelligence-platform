# Entity Relationship Diagram

The warehouse is a star schema: one line-item fact surrounded by four conformed
dimensions, with marts built on top. This diagram matches the actual `ref()` graph in
`dbt/models/` — regenerate the lineage view with `dbt docs generate` to confirm.

Row counts are from the verified PostgreSQL build.

## Star schema

```mermaid
erDiagram
    DIM_CUSTOMERS ||--o{ FACT_ORDER_ITEMS : "places"
    DIM_ORDERS    ||--o{ FACT_ORDER_ITEMS : "contains"
    DIM_PRODUCTS  ||--o{ FACT_ORDER_ITEMS : "is purchased as"
    DIM_TIME      ||--o{ FACT_ORDER_ITEMS : "occurs in"
    DIM_CUSTOMERS ||--o{ DIM_ORDERS       : "owns"

    DIM_CUSTOMERS {
        int  user_id PK "206,209 rows"
        int  total_orders
        int  total_items_purchased
        numeric avg_basket_size
        numeric customer_reorder_rate
        numeric avg_days_since_prior_order
        numeric latest_days_since_prior_order
    }

    DIM_ORDERS {
        int  order_id PK "3,421,083 rows"
        int  user_id FK
        text eval_set
        int  order_number
        int  order_dow
        text order_day_of_week
        int  order_hour_of_day
        float days_since_prior_order
        int  basket_size
        numeric order_reorder_rate
    }

    DIM_PRODUCTS {
        int  product_id PK "49,688 rows"
        text product_name
        int  aisle_id FK
        text aisle_name
        int  department_id FK
        text department_name
    }

    DIM_TIME {
        text time_key PK "168 rows"
        int  order_dow
        int  order_hour_of_day
        text order_day_of_week
        bool is_weekend
        text daypart
    }

    FACT_ORDER_ITEMS {
        int order_id FK "33,819,106 rows"
        int product_id FK
        int user_id FK
        int add_to_cart_order
        int reordered
        int order_number
        int order_dow
        text order_day_of_week
        int order_hour_of_day
        float days_since_prior_order
        int aisle_id
        int department_id
    }
```

### Grain and keys

| Table | Grain | Primary key | Rows |
| :--- | :--- | :--- | ---: |
| `fact_order_items` | one product within one order | `(order_id, product_id)` — enforced by a singular test, not a database constraint | 33,819,106 |
| `dim_orders` | one order | `order_id` | 3,421,083 |
| `dim_customers` | one customer | `user_id` | 206,209 |
| `dim_products` | one product | `product_id` | 49,688 |
| `dim_time` | one day-of-week × hour-of-day slot | `time_key` | 168 |

`dim_time` has no foreign key column on the fact table. The fact carries `order_dow` and
`order_hour_of_day` directly, and `mart_time_patterns` joins on that pair. Adding a
`time_key` column to a 33.8M-row fact to save a two-column join would cost more storage
than it saves in query time, and the pair is already indexed by the aggregation.

## Model lineage

```mermaid
flowchart LR
    subgraph sources["raw sources"]
        S1[raw.orders]
        S2[raw.order_products]
        S3[raw.products]
        S4[raw.aisles]
        S5[raw.departments]
    end

    subgraph staging["staging - views"]
        ST1[stg_orders]
        ST2[stg_order_products]
        ST3[stg_products]
        ST4[stg_aisles]
        ST5[stg_departments]
    end

    subgraph intermediate["intermediate - views"]
        I1[int_order_item_enriched]
        I2[int_customer_order_history]
    end

    subgraph core["marts/core - tables"]
        C1[dim_customers]
        C2[dim_products]
        C3[dim_orders]
        C4[dim_time]
        C5[fact_order_items]
    end

    subgraph kpis["marts/kpis - tables"]
        K1[mart_executive_kpis]
        K2[mart_customer_segments]
        K3[mart_product_performance]
        K4[mart_reorder_behavior]
    end

    subgraph analysis["marts/analysis - tables"]
        A1[mart_basket_affinity]
        A2[mart_cohort_retention]
        A3[mart_time_patterns]
    end

    S1 --> ST1
    S2 --> ST2
    S3 --> ST3
    S4 --> ST4
    S5 --> ST5

    ST1 --> I1
    ST2 --> I1
    ST3 --> I1
    ST4 --> I1
    ST5 --> I1
    ST1 --> I2
    ST2 --> I2

    I2 --> C1
    ST3 --> C2
    ST4 --> C2
    ST5 --> C2
    ST1 --> C3
    ST2 --> C3
    I1 --> C5

    C1 --> K1
    C2 --> K1
    C3 --> K1
    C5 --> K1
    C1 --> K2
    C2 --> K3
    C5 --> K3
    C5 --> K4
    C2 --> K4

    C5 --> A1
    C2 --> A1
    C3 --> A1
    C3 --> A2
    C4 --> A3
    C3 --> A3
    C5 --> A3
```

### Materialization strategy

| Layer | Materialization | Why |
| :--- | :--- | :--- |
| staging | view | Thin type-casting and renaming only; materializing would duplicate the raw data for no gain |
| intermediate | view | Reused by exactly one or two downstream models; the query planner inlines them |
| marts/core, marts/kpis, marts/analysis | table | Read repeatedly by the BI layer and by other marts; the ~32M-row fact must not be recomputed per query |

Configured in `dbt/dbt_project.yml`.
