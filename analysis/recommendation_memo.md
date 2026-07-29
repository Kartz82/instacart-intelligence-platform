# Instacart Analytics Recommendation Memo

All figures below were produced by querying the built dbt marts after a full
`dbt build` returning `PASS=256 WARN=0 ERROR=0` (19 models, 237 data tests) on
PostgreSQL 15, verified 2026-07-25.

## Executive Summary

The platform's behaviour is dominated by habitual restocking rather than discovery. Across
3,421,083 orders and 33,819,106 line items, **59.01% of all items purchased are reorders**,
average basket depth is 9.89 items, and the average customer places 16.59 observed orders.

The commercially interesting variation is not in the top line — it is in *which* categories
and *which* moments convert into repeat purchase:

- Repeat behaviour splits sharply by category. Milk reorders at **78.18%** while spices &
  seasonings reorders at **15.29%**, a 62.89-point spread across aisles in the same store.
- Repeat behaviour also splits by time of day. Morning is only the third-largest daypart by
  volume yet carries the **highest reorder rate at 61.92%**, against a 59.01% baseline.
- Customer engagement is heavily mid-weighted: the largest segment is Moderate Engagement
  (69,635 customers), and **44,873 customers — 21.8% of the base — sit in the At Risk
  segment.**

## Validated Metrics

| Metric | Value |
| :--- | ---: |
| Total orders | 3,421,083 |
| Total customers | 206,209 |
| Total products | 49,688 |
| Total order items | 33,819,106 |
| Platform reorder rate | 59.01% |
| Average basket size | 9.89 items |
| Average orders per customer | 16.59 |
| Active departments | 21 |
| Top department by items | produce (9,888,378 items) |
| Largest behavioural segment | Moderate Engagement (69,635 customers) |

Retention by observed order milestone: order 3 **100.00%**, order 5 **88.37%**,
order 10 **53.70%**, order 15 **36.41%**, order 20 **26.15%**.

Top affinity pairs: highest lift is *Yogurt, Sheep Milk, Strawberry* + *Yogurt, Sheep Milk,
Blackberry* at **1,431.68 lift** (421 co-orders, 41.89% confidence); highest support is
*Bag of Organic Bananas* + *Organic Hass Avocado* at **1.8930% support** (64,761 co-orders,
2.54 lift).

## Findings

### Executive KPIs

Scale is substantial and repeat-driven: 33.8M line items across 206K customers, with nearly
six in ten items being reorders. Department breadth is complete — all 21 departments are
active — so there is no dormant-category problem to solve; the problem is depth of repeat
within categories.

### Product & Category Performance

Volume and loyalty are not the same thing, and the gap is where the opportunity sits.

| Aisle | Department | Order Items | Reorder Rate | vs Department |
| :--- | :--- | ---: | ---: | ---: |
| milk | dairy eggs | 923,659 | 78.18% | +11.16 pts |
| water seltzer sparkling water | beverages | 878,150 | 72.99% | +7.62 pts |
| fresh fruits | produce | 3,792,661 | 71.88% | +6.83 pts |
| spices seasonings | pantry | 221,371 | 15.29% | −19.45 pts |
| kitchen supplies | household | 9,620 | 19.48% | −20.85 pts |

Banana is the single highest-volume SKU at 491,291 order items with an 84.51% reorder rate.
Spices & seasonings is the largest genuinely low-repeat category — 221,371 items is real
volume, but almost none of it returns.

### Customer Behaviour Segments

| Segment | Customers | Share |
| :--- | ---: | ---: |
| Moderate Engagement | 69,635 | 33.8% |
| Loyal Routine | 62,818 | 30.5% |
| At Risk | 44,873 | 21.8% |
| High Engagement | 28,883 | 14.0% |

The segmentation has no onboarding tier. Every customer in this extract has between 4 and
100 observed orders — the sample was curated that way — so customers new to the platform
are absent by construction, and no threshold on order count can recover them. See
[Decision 8](../docs/decisions.md).

### Cohort Retention

Retention holds completely through order 3, then falls steadily: 88.37% at order 5, 53.70%
at order 10, 36.41% at order 15, 26.15% at order 20. The steepest decline is between orders
5 and 10, where roughly a third of the remaining base stops.

### Basket Affinity

254,490 pairs clear the eligibility thresholds, drawn from the 5,237 products (10.5% of the
catalog) appearing in at least 1,000 distinct orders. The two useful patterns are opposite
in character: extremely high-lift pairs are narrow flavour substitutions within one product
line, while high-support pairs are broad staples that co-occur constantly.

## Recommendations

1. **Customer lifecycle.** Target the orders 5-10 window, where retention falls from 88.37%
   to 53.70% — the largest single drop in the observed curve. Acting before order 5 spends
   budget on customers who were going to stay anyway.
2. **Category merchandising.** Treat spices & seasonings as a replenishment-reminder
   problem, not a discovery problem. At 221,371 items and a 15.29% reorder rate, 19.45
   points below its department, the volume already exists; the return trip does not.
3. **Repeat-purchase engagement.** Schedule replenishment prompts into the morning window,
   which already carries the highest reorder intent at 61.92%. Meeting existing habit is
   cheaper than creating it.
4. **Cross-sell testing.** Run bundle tests on high-*support* pairs such as Bag of Organic
   Bananas + Organic Hass Avocado (64,761 co-orders) rather than on the top-lift pairs. A
   1,431.68 lift on 421 co-orders is a narrow flavour swap and will not move the top line.

## Limitations

- No prices are included in the public Instacart dataset.
- Revenue, profit, margin, AOV, and CLV cannot be calculated without adding external price
  data. No figure above is monetary.
- The dataset does not include real calendar order dates.
- Cohort retention is based on observed order sequence, not weekly or monthly calendar
  cohorts.
- Basket analysis is product affinity analysis, not prediction or machine learning. High
  lift does not imply causation.
- Customer segments are behavioural engagement groups, not financial RFM segments. See
  `docs/decisions.md` §2.
- Affinity coverage is bounded by the eligibility thresholds; long-tail products are absent
  by design.

## Validation Record

- [x] PostgreSQL load completed — `raw` schema populated by `src/database_loader.py`.
- [x] `dbt build` completed — `PASS=256 WARN=0 ERROR=0 SKIP=0`, 19 models, 237 data tests.
- [x] All 197 compiled nodes validated against the query planner via `EXPLAIN`.
- [x] Every metric in this memo re-queried from the built marts.
- [ ] Analysis SQL in `analysis/*.sql` re-run against the rebuilt marts (optional — the
      memo's figures come from the marts directly, not from these scripts).
