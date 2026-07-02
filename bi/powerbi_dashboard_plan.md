# Power BI Dashboard Plan

## Dashboard Purpose

Create a recruiter-ready BI dashboard that explains customer behavior, product performance, retention patterns, and basket affinity from the Instacart analytics warehouse.

The dashboard should consume dbt marts only. Power BI should not connect to raw tables.

## Target Audience

- Hiring managers reviewing Analytics Engineering, Data Analyst, BI Analyst, Product Analyst, and Junior Data Engineer portfolios.
- Business stakeholders interested in grocery marketplace behavior.
- Analytics reviewers who want to see clear metric definitions, reproducibility, and practical recommendations.

## Data Sources

Power BI Desktop should connect to PostgreSQL and import these dbt marts:

| Mart | PostgreSQL relation | Purpose |
|---|---|---|
| Executive KPIs | `analytics_kpis.mart_executive_kpis` | Headline operating metrics |
| Product Performance | `analytics_kpis.mart_product_performance` | Product, aisle, and department performance |
| Customer Segments | `analytics_kpis.mart_customer_segments` | Behavioral customer engagement groups |
| Cohort Retention | `analytics_analysis.mart_cohort_retention` | Observed order-sequence retention |
| Basket Affinity | `analytics_analysis.mart_basket_affinity` | SQL-first product-pair affinity |

## Recommended Pages

### 1. Executive Overview

Purpose: Show the scale and baseline behavior of the dataset.

KPI cards:
- Total orders: TODO: insert validated KPI value.
- Total customers: TODO: insert validated KPI value.
- Total products: TODO: insert validated KPI value.
- Total order items: TODO: insert validated KPI value.
- Reorder rate: TODO: insert validated KPI value.
- Average basket size: TODO: insert validated KPI value.
- Average orders per customer: TODO: insert validated KPI value.
- Top department by items: TODO: insert validated KPI value.

Recommended visuals:
- KPI card row from `mart_executive_kpis`.
- Small table listing all executive KPI fields.
- Text box with data limitations.

Slicers/filters:
- None required on this page because `mart_executive_kpis` is a one-row snapshot.

Screenshot placeholder:
- TODO: add screenshot after Power BI build.

### 2. Product Performance

Purpose: Identify products, aisles, and departments driving volume and reorder behavior.

Recommended visuals:
- Bar chart: top 20 products by `total_order_items`.
- Bar chart: top departments by summed item volume.
- Scatter plot: `distinct_customers` vs. `reorder_rate`, sized by `total_order_items`.
- Matrix: product, aisle, department, total order items, distinct orders, distinct customers, reorder rate.

Slicers/filters:
- Department name.
- Aisle name.
- Reorder rate range.
- Minimum total order items.

KPI cards:
- Highest-volume product: TODO: fill after validation.
- Highest-volume department: TODO: fill after validation.
- Average product reorder rate: TODO: fill after validation.

Screenshot placeholder:
- TODO: add screenshot after Power BI build.

### 3. Customer Segments

Purpose: Explain customer engagement groups using behavioral, non-financial signals.

Recommended visuals:
- Donut or bar chart: customer count by `behavioral_segment`.
- Matrix: segment, customer count, average orders, average basket size, average reorder rate.
- Box or column chart: average `behavioral_score` by segment.
- Table sample: customers sorted by behavioral score.

Slicers/filters:
- Behavioral segment.
- Frequency score.
- Basket size score.
- Reorder score.
- Recency proxy score.

KPI cards:
- Largest segment: TODO: fill after validation.
- Highest average order segment: TODO: fill after validation.
- Highest average reorder segment: TODO: fill after validation.

Screenshot placeholder:
- TODO: add screenshot after Power BI build.

### 4. Cohort Retention

Purpose: Show how customer activity changes across observed order milestones.

Recommended visuals:
- Line chart: `observed_order_number` vs. `retention_rate`.
- Bar chart: `observed_order_number` vs. `active_customers`.
- Matrix: observed order number, starting customers, active customers, retention rate.

Slicers/filters:
- Observed order number range.

KPI cards:
- Starting customers: TODO: fill after validation.
- Retention at order 2: TODO: fill after validation.
- Retention at order 5: TODO: fill after validation.
- Retention at order 10: TODO: fill after validation.

Screenshot placeholder:
- TODO: add screenshot after Power BI build.

### 5. Basket Affinity

Purpose: Identify frequently co-occurring products for merchandising and cross-sell analysis.

Recommended visuals:
- Scatter plot: support vs. confidence, sized or colored by lift.
- Table: product A, product B, orders with both, support, confidence, lift.
- Bar chart: top product pairs by lift.
- Bar chart: top product pairs by support.

Slicers/filters:
- Minimum lift.
- Minimum support.
- Minimum orders with both.
- Product A name.
- Product B name.

KPI cards:
- Highest-lift pair: TODO: fill after validation.
- Highest-support pair: TODO: fill after validation.
- Number of affinity pairs: TODO: fill after validation.

Screenshot placeholder:
- TODO: add screenshot after Power BI build.

### 6. Recommendations

Purpose: Convert validated analysis into concise business actions.

Recommended visuals/content:
- Text cards for 3-5 validated recommendations.
- Supporting KPI callouts from prior pages.
- Table of limitations.
- Link or note pointing to `analysis/recommendation_memo.md`.

Recommended sections:
- Customer lifecycle recommendation: TODO: fill after validation.
- Product/category merchandising recommendation: TODO: fill after validation.
- Repeat-purchase engagement recommendation: TODO: fill after validation.
- Basket affinity recommendation: TODO: fill after validation.

Screenshot placeholder:
- TODO: add screenshot after Power BI build.

## Power BI Build Notes

1. Use PostgreSQL connector in Power BI Desktop.
2. Connect to local database:
   - Server: `localhost:5434`
   - Database: `instacart_db`
3. Import dbt marts only:
   - `analytics_kpis.mart_executive_kpis`
   - `analytics_kpis.mart_product_performance`
   - `analytics_kpis.mart_customer_segments`
   - `analytics_analysis.mart_cohort_retention`
   - `analytics_analysis.mart_basket_affinity`
4. Avoid importing `raw` tables.
5. Use import mode for portfolio simplicity.
6. Format rates as percentages.
7. Use thousands separators for counts.
8. Keep all final dashboard values traceable to dbt marts.

## Screenshot Placeholder Plan

After Power BI is built and validated, export one screenshot per page:

```text
reports/powerbi_executive_overview.png
reports/powerbi_product_performance.png
reports/powerbi_customer_segments.png
reports/powerbi_cohort_retention.png
reports/powerbi_basket_affinity.png
reports/powerbi_recommendations.png
```

Do not add screenshots until the dashboard values have been validated against dbt output.

## Limitations

- No prices are available in the source dataset.
- Revenue, profit, margin, AOV, and CLV should not appear in the dashboard.
- The dataset does not include real calendar order dates.
- Cohort retention is based on observed order sequence, not weekly or monthly cohorts.
- Basket affinity is product co-occurrence analysis, not prediction or machine learning.
- Customer segments are behavioral engagement segments, not financial RFM segments.
