# Instacart Analytics Recommendation Memo

## Executive Summary

TODO: fill after dbt validation.

This memo should summarize the validated KPI, product, customer, cohort, and basket affinity findings from the dbt marts. Do not add results until the local PostgreSQL load, dbt run, and dbt tests have completed successfully.

## Metrics To Fill After dbt Run

- TODO: insert validated total orders.
- TODO: insert validated total customers.
- TODO: insert validated total products.
- TODO: insert validated total order items.
- TODO: insert validated reorder rate.
- TODO: insert validated average basket size.
- TODO: insert validated average orders per customer.
- TODO: insert validated active department count.
- TODO: insert validated top department by items.
- TODO: insert validated largest behavioral customer segment.
- TODO: insert validated retention rate at selected observed order milestones.
- TODO: insert validated top product affinity pairs by lift/support.

## Recommended Business Questions

1. Which top-line operating metrics best describe the dataset's observed shopping behavior?
2. Which departments and products drive the most basket volume?
3. Which products have high reorder behavior and may represent habit-forming purchases?
4. How are customers distributed across behavioral engagement segments?
5. How quickly does observed customer activity decline across order-sequence milestones?
6. Which product pairs appear together often enough to inform merchandising, search, or bundle recommendations?

## Likely Insight Categories

### Executive KPIs

TODO: fill after dbt validation.

Expected focus:
- Overall order and customer scale.
- Reorder behavior.
- Basket size.
- Department breadth.

### Product Performance

TODO: fill after dbt validation.

Expected focus:
- Highest-volume products.
- Highest-volume departments.
- Products with strong repeat behavior.
- Products with broad customer reach.

### Customer Behavior Segments

TODO: fill after dbt validation.

Expected focus:
- Size of each behavioral segment.
- Difference in order frequency by segment.
- Difference in basket size by segment.
- Difference in reorder behavior by segment.

### Cohort Retention

TODO: fill after dbt validation.

Expected focus:
- Share of customers reaching each observed order milestone.
- Drop-off points across order sequence.
- Milestones suitable for lifecycle messaging.

### Basket Affinity

TODO: fill after dbt validation.

Expected focus:
- Product pairs with high lift.
- Product pairs with high support.
- Product relationships that are actionable for merchandising.

## Recommendation Placeholders

- TODO: add one recommendation for customer lifecycle strategy.
- TODO: add one recommendation for product/category merchandising.
- TODO: add one recommendation for repeat-purchase engagement.
- TODO: add one recommendation for basket affinity or cross-sell testing.

## Limitations

- No prices are included in the public Instacart dataset.
- Revenue, profit, margin, AOV, and CLV cannot be calculated without adding external price data.
- The dataset does not include real calendar order dates.
- Cohort retention is based on observed order sequence, not weekly or monthly calendar cohorts.
- Basket analysis is product affinity analysis, not prediction or machine learning.
- Customer segments are behavioral/RFM-style engagement groups, not financial RFM segments.

## Validation Checklist

- TODO: run PostgreSQL load successfully.
- TODO: run `dbt run --project-dir dbt --select +path:models/marts`.
- TODO: run `dbt test --project-dir dbt`.
- TODO: run each SQL file in `analysis/`.
- TODO: copy only validated metrics into this memo.
