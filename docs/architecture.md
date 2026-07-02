# Project Architecture

## Project Purpose

This project is a local Analytics Engineering and BI portfolio build using the public Instacart order dataset. The goal is to demonstrate a PostgreSQL-first warehouse, dbt modeling, SQL analysis, and Power BI planning without adding machine learning or unsupported financial metrics.

The project is designed for Analytics Engineer, Data Analyst, BI Analyst, Product Analyst, and Junior Data Engineer roles.

## Local Architecture Overview

The active architecture is intentionally simple:

1. Raw Instacart CSV files are stored locally in `data/raw/`.
2. `src/database_loader.py` loads the CSVs into PostgreSQL.
3. PostgreSQL stores source-shaped tables in the `raw` schema.
4. dbt builds staging, intermediate, star schema, KPI, and analysis marts.
5. SQL analysis files query dbt marts.
6. Power BI Desktop should connect to dbt marts for dashboarding.
7. The recommendation memo and final README case study should be filled only after metrics are validated.

Power BI should consume dbt marts, not raw tables.

## Data Flow

```text
Instacart CSVs
  -> Python loader
  -> PostgreSQL raw schema
  -> dbt staging models
  -> dbt intermediate models
  -> dbt core star schema
  -> dbt KPI and analysis marts
  -> SQL analysis files
  -> Power BI Desktop dashboard
  -> recommendation memo
  -> final README case study
```

## Schema And Layer Explanation

### Raw Layer

Location: PostgreSQL `raw` schema.

Tables:
- `raw.departments`
- `raw.aisles`
- `raw.products`
- `raw.orders`
- `raw.order_products`

Purpose:
- Preserve source-shaped Instacart data after local CSV load.
- Provide a stable warehouse landing zone for dbt.
- Apply basic database constraints and indexes.

### dbt Staging Layer

Location: dbt `models/staging/`.

Models:
- `stg_departments`
- `stg_aisles`
- `stg_products`
- `stg_orders`
- `stg_order_products`

Purpose:
- Standardize types.
- Rename fields where useful for readability.
- Keep logic light and source-aligned.
- Add dbt tests for source integrity.

### dbt Intermediate Layer

Location: dbt `models/intermediate/`.

Models:
- `int_order_item_enriched`
- `int_customer_order_history`

Purpose:
- Join order items to order, product, aisle, and department context.
- Prepare reusable customer lifecycle summaries.
- Keep repeated join logic out of final marts.

### dbt Core Star Schema

Location: dbt `models/marts/core/`.

Models:
- `dim_customers`
- `dim_products`
- `dim_orders`
- `fact_order_items`

Purpose:
- Provide a clean dimensional model for analytics.
- Use one row per business entity in dimensions.
- Use one row per `order_id` + `product_id` in the fact table.

### dbt KPI Marts

Location: dbt `models/marts/kpis/`.

Models:
- `mart_executive_kpis`
- `mart_product_performance`
- `mart_customer_segments`

Purpose:
- Provide business-facing metrics for BI and analysis.
- Keep metrics reproducible from dbt models.
- Avoid unsupported financial metrics such as revenue, margin, AOV, and CLV.

### dbt Analysis Marts

Location: dbt `models/marts/analysis/`.

Models:
- `mart_cohort_retention`
- `mart_basket_affinity`

Purpose:
- Support order-sequence retention analysis.
- Support SQL-first product affinity analysis.
- Provide BI-ready tables for Power BI and stakeholder review.

## SQL Analysis Layer

Location: `analysis/`.

Files:
- `executive_kpis.sql`
- `product_performance.sql`
- `customer_segments.sql`
- `cohort_retention.sql`
- `basket_affinity.sql`
- `recommendation_memo.md`

Purpose:
- Query dbt marts directly.
- Keep business questions readable for recruiters and stakeholders.
- Provide a place to validate findings before the final README case study.

## Power BI Layer

Location: `bi/`.

Files:
- `powerbi_dashboard_plan.md`
- `data_dictionary.md`

Power BI Desktop should import:
- `analytics_kpis.mart_executive_kpis`
- `analytics_kpis.mart_product_performance`
- `analytics_kpis.mart_customer_segments`
- `analytics_analysis.mart_cohort_retention`
- `analytics_analysis.mart_basket_affinity`

Power BI should not connect to `raw` tables.

## Why PostgreSQL Is Primary

PostgreSQL is the primary warehouse for this project because it is:

- Local and reproducible.
- Easy to run with Docker.
- Compatible with dbt Core.
- Sufficient for the project scale and portfolio goals.
- Directly connectable from Power BI Desktop.

Using PostgreSQL keeps the project practical and recruiter-readable without introducing unnecessary cloud infrastructure.

## Why BigQuery Is Future Enhancement Only

BigQuery is intentionally not implemented in the active architecture.

It may be a future enhancement if the project needs:
- Cloud-hosted warehouse deployment.
- Larger-scale public sharing.
- Scheduled cloud transformations.
- A cloud BI stack.

For the current portfolio version, adding BigQuery would increase setup complexity without improving the core Analytics Engineering story.

## Data Limitations

- The dataset does not include product prices.
- Revenue, profit, margin, AOV, and CLV should not be calculated.
- The dataset does not include real calendar order dates.
- Cohort retention is based on observed order sequence, not weekly or monthly calendar cohorts.
- Basket affinity is product co-occurrence analysis, not prediction.
- Customer segments are behavioral engagement groups, not financial RFM segments.
- Final metric values should not be added to docs until PostgreSQL load, dbt run, and dbt tests pass.

## Reproducibility Notes

Expected local workflow:

```bash
cp .env.example .env
docker compose up -d
python src/database_loader.py

cp dbt/profiles.yml.example dbt/profiles.yml
export DBT_PROFILES_DIR=./dbt
dbt run --project-dir dbt --select +path:models/marts
dbt test --project-dir dbt
```

Run analysis SQL after marts are built:

```bash
psql -h localhost -p 5434 -U postgres -d instacart_db -f analysis/executive_kpis.sql
psql -h localhost -p 5434 -U postgres -d instacart_db -f analysis/product_performance.sql
psql -h localhost -p 5434 -U postgres -d instacart_db -f analysis/customer_segments.sql
psql -h localhost -p 5434 -U postgres -d instacart_db -f analysis/cohort_retention.sql
psql -h localhost -p 5434 -U postgres -d instacart_db -f analysis/basket_affinity.sql
```

## Cleanup Commands

Stop PostgreSQL containers while keeping the local database volume:

```bash
docker compose down
```

Full local PostgreSQL volume reset:

```bash
docker compose down -v
```

Use the volume reset only when you want to remove the local database state and reload from CSVs.
