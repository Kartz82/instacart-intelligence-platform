# Power BI Design Specification

This is the build spec for the Power BI report: page layout, field mappings, DAX measure
definitions, and conditional-formatting rules. It is written to be assembled directly —
every measure below is a complete formula, and every visual names the exact mart column it
binds to.

The `.pbix` itself is built by hand from this spec. Screenshots go in `screenshots/`.

---

## 1. Data connection

Connect Power BI to the dbt marts, not to the raw tables.

| Setting | Value |
| --- | --- |
| Connector | PostgreSQL (local dev) or Google BigQuery (cloud target) |
| Storage mode | **Import** for every table below |
| Refresh | Manual / scheduled after a `dbt build` completes |

**Why Import and not DirectQuery.** `fact_order_items` holds 33,819,106 rows and stays in
the warehouse — no visual binds to it. Every table imported here has already been
pre-aggregated by dbt to a BI-sized grain, so Import gives in-memory speed with a small
model file. See `docs/decisions.md` §6.

### Tables to import

| Table | Schema | Grain | Rows |
| --- | --- | --- | ---: |
| `mart_executive_kpis` | `analytics_kpis` | one snapshot row | 1 |
| `mart_customer_segments` | `analytics_kpis` | customer | 206,209 |
| `mart_product_performance` | `analytics_kpis` | product | 49,688 |
| `mart_reorder_behavior` | `analytics_kpis` | department x aisle | 134 |
| `mart_basket_affinity` | `analytics_analysis` | product pair | 254,490 |
| `mart_cohort_retention` | `analytics_analysis` | order-sequence index | 21 |
| `mart_time_patterns` | `analytics_analysis` | day-of-week x hour | 168 |
| `dim_products` | `analytics_core` | product | 49,688 |
| `dim_time` | `analytics_core` | day-of-week x hour | 168 |

### Model relationships

| From | To | Cardinality | Direction |
| --- | --- | --- | --- |
| `mart_product_performance[product_id]` | `dim_products[product_id]` | many-to-one | single |
| `mart_time_patterns[time_key]` | `dim_time[time_key]` | one-to-one | both |
| `mart_basket_affinity[product_a_id]` | `dim_products[product_id]` | many-to-one | single |

`mart_basket_affinity[product_b_id]` needs a second relationship to `dim_products`, which
Power BI will create inactive. Activate it inside a measure with `USERELATIONSHIP` only if
a visual needs to slice by product B; otherwise leave it inactive so filter context stays
predictable.

`mart_reorder_behavior` and `mart_customer_segments` stand alone and need no relationship
to the others — keep them isolated rather than inventing a bridge table.

### Sort-order columns to set

`order_day_of_week` sorts alphabetically by default, which puts Friday first. Set
**Sort by column** = `order_dow` on `dim_time[order_day_of_week]` and on
`mart_time_patterns[order_day_of_week]`. Do the same for `daypart`, adding a numeric
`daypart_sort` in Power Query (Overnight 1, Morning 2, Midday 3, Afternoon 4, Evening 5).

---

## 2. Theme and layout grid

One custom theme JSON applied report-wide.

| Element | Value |
| --- | --- |
| Canvas | 1280 x 720, background `#F7F8FA` |
| Card background | `#FFFFFF`, corner radius 8, shadow off |
| Primary | `#1F6F54` (deep green; dark enough for white text) |
| Secondary | `#2E5C8A` |
| Risk / negative | `#C0392B` |
| Positive | `#1F8A54` |
| Neutral text | `#2B2F33`; muted `#6B7280` |
| Font | Segoe UI. Titles 14pt semibold, KPI values 28pt semibold, body 10pt |

**Layout grid, repeated on all pages:**

- Left sidebar, 180px, primary colour, page navigation with an active-state highlight.
- Header strip, 56px: page title left, slicers right.
- KPI card row, 96px, four cards.
- Body region below, split into a 2/3 + 1/3 column pair.

Keep the sidebar and header identical across pages so navigation never shifts position.

---

## 3. DAX measures

Create these in a dedicated `_Measures` table (Enter Data → blank table → hide the
placeholder column) so they are not scattered across the data tables.

### Executive measures

```dax
Total Orders = SELECTEDVALUE ( mart_executive_kpis[total_orders] )

Total Customers = SELECTEDVALUE ( mart_executive_kpis[total_customers] )

Total Order Items = SELECTEDVALUE ( mart_executive_kpis[total_order_items] )

Total Products = SELECTEDVALUE ( mart_executive_kpis[total_products] )

Platform Reorder Rate = SELECTEDVALUE ( mart_executive_kpis[reorder_rate] )

Average Basket Size = SELECTEDVALUE ( mart_executive_kpis[average_basket_size] )

Average Orders per Customer =
SELECTEDVALUE ( mart_executive_kpis[average_orders_per_customer] )

Top Department = SELECTEDVALUE ( mart_executive_kpis[top_department_by_items] )
```

`mart_executive_kpis` is a single row, so `SELECTEDVALUE` returns it directly and avoids an
aggregation that would silently read as a sum if the table ever gained rows.

### Customer segmentation measures

```dax
Customers in Segment = COUNTROWS ( mart_customer_segments )

Segment Share =
DIVIDE (
    COUNTROWS ( mart_customer_segments ),
    CALCULATE ( COUNTROWS ( mart_customer_segments ), ALL ( mart_customer_segments ) )
)

At Risk Customers =
CALCULATE (
    COUNTROWS ( mart_customer_segments ),
    mart_customer_segments[behavioral_segment] = "At Risk"
)

At Risk Share =
DIVIDE (
    [At Risk Customers],
    CALCULATE ( COUNTROWS ( mart_customer_segments ), ALL ( mart_customer_segments ) )
)

Avg Reorder Rate (Segment) = AVERAGE ( mart_customer_segments[customer_reorder_rate] )

Avg Orders (Segment) = AVERAGE ( mart_customer_segments[total_orders] )

Avg Basket Size (Segment) = AVERAGE ( mart_customer_segments[avg_basket_size] )

Median Days Since Prior Order =
MEDIAN ( mart_customer_segments[latest_days_since_prior_order] )
```

### Product and category measures

```dax
Product Order Items = SUM ( mart_product_performance[total_order_items] )

Product Reach = SUM ( mart_product_performance[distinct_customers] )

Product Reorder Rate =
AVERAGEX ( mart_product_performance, mart_product_performance[reorder_rate] )

Category Reorder Rate =
DIVIDE (
    SUM ( mart_reorder_behavior[reordered_items] ),
    SUM ( mart_reorder_behavior[total_order_items] )
)

Reorder Gap vs Department = AVERAGE ( mart_reorder_behavior[reorder_rate_vs_department] )

Reorder Gap vs Platform = AVERAGE ( mart_reorder_behavior[reorder_rate_vs_platform] )

Category Item Share = SUM ( mart_reorder_behavior[share_of_order_items] )

Underperforming Aisles =
CALCULATE (
    COUNTROWS ( mart_reorder_behavior ),
    mart_reorder_behavior[reorder_rate_vs_department] < 0,
    mart_reorder_behavior[below_volume_floor] = FALSE ()
)
```

`Category Reorder Rate` deliberately divides summed numerators by summed denominators
rather than averaging per-aisle rates: averaging would weight a 9,620-item aisle the same
as a 3,792,661-item aisle.

### Temporal measures

```dax
Orders in Slot = SUM ( mart_time_patterns[total_orders] )

Slot Share of Orders = SUM ( mart_time_patterns[share_of_total_orders] )

Slot Reorder Rate =
DIVIDE (
    SUM ( mart_time_patterns[reordered_items] ),
    SUM ( mart_time_patterns[total_order_items] )
)

Peak Slot Orders =
MAXX ( ALLSELECTED ( mart_time_patterns ), mart_time_patterns[total_orders] )

Slot vs Peak = DIVIDE ( [Orders in Slot], [Peak Slot Orders] )

Weekend Order Share =
DIVIDE (
    CALCULATE (
        SUM ( mart_time_patterns[total_orders] ),
        mart_time_patterns[is_weekend] = TRUE ()
    ),
    CALCULATE ( SUM ( mart_time_patterns[total_orders] ), ALL ( mart_time_patterns ) )
)
```

`Slot vs Peak` drives the heatmap colour: normalising each cell against the selected peak
keeps the gradient readable when a slicer narrows the range.

### Basket affinity measures

```dax
Pair Count = COUNTROWS ( mart_basket_affinity )

Max Lift = MAX ( mart_basket_affinity[lift] )

Avg Confidence = AVERAGE ( mart_basket_affinity[confidence_a_to_b] )

Co-occurring Orders = SUM ( mart_basket_affinity[orders_with_both] )

Actionable Pairs =
CALCULATE (
    COUNTROWS ( mart_basket_affinity ),
    mart_basket_affinity[lift] > 2,
    mart_basket_affinity[confidence_a_to_b] > 0.1
)
```

### Retention measures

```dax
Retention Rate = SUM ( mart_cohort_retention[retention_rate] )

Active Customers at Milestone = SUM ( mart_cohort_retention[active_customers] )

Retention Drop from Previous =
VAR CurrentIndex = SELECTEDVALUE ( mart_cohort_retention[order_sequence_index] )
VAR PreviousRate =
    CALCULATE (
        SUM ( mart_cohort_retention[retention_rate] ),
        mart_cohort_retention[order_sequence_index] = CurrentIndex - 1
    )
RETURN
    IF (
        NOT ISBLANK ( PreviousRate ),
        SUM ( mart_cohort_retention[retention_rate] ) - PreviousRate
    )
```

### Formatting to set on each measure

| Measure group | Format |
| --- | --- |
| Counts | Whole number, thousands separator |
| Rates and shares | Percentage, **2 decimal places** |
| `Average Basket Size`, `Avg Orders (Segment)` | Decimal, 2 places |
| `Max Lift`, `Avg Confidence` | Decimal, 2 places |
| `support` | Percentage, 4 decimal places (values are small; 2 places rounds them to 0.00%) |

Precision must be consistent within a visual. Mixing "59%" and "59.01%" on one page is the
most common tell of a rushed dashboard.

---

## 4. Pages

### Page 1 — Executive Overview

**Question:** What is the current state of the platform?

| Position | Visual | Fields |
| --- | --- | --- |
| KPI row | 4 cards | `[Total Orders]`, `[Total Customers]`, `[Total Order Items]`, `[Platform Reorder Rate]` |
| Left 2/3 | Line chart | Axis `mart_cohort_retention[observed_order_number]`, value `[Retention Rate]` |
| Right 1/3 | Bar chart | Axis `mart_reorder_behavior[department_name]`, value `[Category Item Share]`, top 10 by value |
| Bottom left | Matrix | Rows `mart_time_patterns[order_day_of_week]`, columns `mart_time_patterns[daypart]`, values `[Orders in Slot]` |
| Bottom right | Cards | `[Top Department]`, `[Average Basket Size]`, `[Average Orders per Customer]` |

No pie chart here: department share has 21 categories, well past the point where a pie
stays readable.

### Page 2 — Customer Segmentation

**Question:** Which customers are disengaging, and who is worth protecting?

| Position | Visual | Fields |
| --- | --- | --- |
| KPI row | 4 cards | `[Total Customers]`, `[At Risk Customers]`, `[At Risk Share]`, `[Avg Reorder Rate (Segment)]` |
| Left 2/3 | Stacked bar | Axis `behavioral_segment`, value `[Customers in Segment]` |
| Right 1/3 | Scatter | X `[Avg Orders (Segment)]`, Y `[Avg Reorder Rate (Segment)]`, legend `behavioral_segment`, size `[Customers in Segment]` |
| Full width, bottom | **At-risk table** | `user_id`, `total_orders`, `avg_basket_size`, `customer_reorder_rate`, `latest_days_since_prior_order`, `behavioral_score`; filtered to `behavioral_segment = "At Risk"`, sorted by `latest_days_since_prior_order` descending |

The at-risk table is the decision-oriented element: it surfaces the specific accounts to
act on rather than only reporting that a risk segment exists.

**Label honestly.** Title the page "Behavioural Segmentation", not "RFM". The dataset has
no prices and no timestamps, so there is no monetary or true recency axis — see
`docs/decisions.md` §2. Add a footnote: *"Recency is a proxy derived from days since the
customer's most recent prior order. The dataset contains no revenue data."*

### Page 3 — Basket & Cross-sell

**Question:** Which products sell together strongly enough to act on?

| Position | Visual | Fields |
| --- | --- | --- |
| KPI row | 4 cards | `[Pair Count]`, `[Actionable Pairs]`, `[Max Lift]`, `[Avg Confidence]` |
| Left 2/3 | Scatter | X `support`, Y `confidence_a_to_b`, size `orders_with_both`, detail `product_a_name` |
| Right 1/3 | Slicers | `lift` (numeric range), `confidence_a_to_b` (numeric range), `department_name` |
| Full width, bottom | Table | `product_a_name`, `product_b_name`, `orders_with_both`, `support`, `confidence_a_to_b`, `lift`, sorted by `lift` descending |

Note on the page that the mart covers only products appearing in at least 1,000 distinct
orders and pairs co-occurring at least 100 times — 254,490 pairs out of a possible
1,234,423,828. Without that note the table reads as the complete pair universe.

### Page 4 — Temporal Behavior

**Question:** When do customers order, and does intent change by time of day?

| Position | Visual | Fields |
| --- | --- | --- |
| KPI row | 4 cards | `[Orders in Slot]`, `[Weekend Order Share]`, `[Peak Slot Orders]`, `[Slot Reorder Rate]` |
| Full width, centre | **Heatmap matrix** | Rows `order_day_of_week` (sorted by `order_dow`), columns `order_hour_of_day`, values `[Orders in Slot]`, background colour by `[Slot vs Peak]` |
| Bottom left | Column chart | Axis `daypart`, value `[Orders in Slot]` |
| Bottom right | Line chart | Axis `order_hour_of_day`, value `[Slot Reorder Rate]`, legend `is_weekend` |

The heatmap is the centrepiece of the report. `mart_time_patterns` is always a complete
168-cell grid, so quiet slots render as genuinely empty cells rather than disappearing.

### Page 5 — Product & Department Performance

**Question:** Which categories under-perform their own department on repeat purchase?

| Position | Visual | Fields |
| --- | --- | --- |
| KPI row | 4 cards | `[Total Products]`, `[Category Reorder Rate]`, `[Underperforming Aisles]`, `[Product Reach]` |
| Left 2/3 | **Aisle diagnostic table** | `department_name`, `aisle_name`, `total_order_items`, `reorder_rate`, `department_reorder_rate`, `reorder_rate_vs_department` — sorted ascending by `reorder_rate_vs_department` so the worst offenders sit at the top |
| Right 1/3 | Bar chart | Axis `department_name`, value `[Category Reorder Rate]`, with a constant line at the platform rate |
| Bottom | Table | `product_name`, `aisle_name`, `total_order_items`, `reorder_rate` from `mart_product_performance`, top 25 by `total_order_items` |

Sorting the aisle table ascending is deliberate: a table sorted by "best" is a vanity
visual, one sorted by the largest negative gap is a work queue.

### Page 6 (optional) — Metric Explorer

A field-parameters page. Create two parameters:

- **Metric**: `[Orders in Slot]`, `[Slot Reorder Rate]`, `[Category Reorder Rate]`, `[Customers in Segment]`, `[Product Order Items]`
- **Dimension**: `department_name`, `aisle_name`, `order_day_of_week`, `daypart`, `behavioral_segment`

Bind both to one bar chart and one table. This demonstrates field parameters without adding
another fixed page that duplicates existing views.

---

## 5. Conditional formatting rules

This is the highest-value formatting technique in the report — it is what turns a table
into a diagnosis. Apply exactly these rules.

### Page 4 heatmap — `[Orders in Slot]` cell background

Format by **rules** on `[Slot vs Peak]`, not by a colour scale over raw order counts, so
the gradient stays stable when slicers change the range.

| Rule | Colour |
| --- | --- |
| `>= 0.80` | `#1F6F54` (white text) |
| `>= 0.60` and `< 0.80` | `#4E9A78` |
| `>= 0.40` and `< 0.60` | `#8FC0A9` |
| `>= 0.20` and `< 0.40` | `#C9DFD3` |
| `< 0.20` | `#F0F4F2` |

### Page 5 aisle diagnostic table — `reorder_rate_vs_department`

Diverging scale centred on zero, because the sign is the entire message.

| Rule | Colour |
| --- | --- |
| `<= -0.15` | `#C0392B`, white text |
| `> -0.15` and `< -0.05` | `#E8A29A` |
| `>= -0.05` and `<= 0.05` | `#F0F0F0` (no signal) |
| `> 0.05` and `< 0.15` | `#A9D3BC` |
| `>= 0.15` | `#1F8A54`, white text |

Add a **data bar** on `total_order_items` in the same table so a large negative gap on a
tiny aisle is visually distinguishable from one on a major aisle.

Add an **icon** on `below_volume_floor`: a warning glyph when `TRUE`, blank when `FALSE`.
On the current data this never triggers — all 134 aisles clear the 1,000-item floor — but
it must be wired so a future, sparser load is not misread as clean.

### Page 2 at-risk table

| Column | Rule | Colour |
| --- | --- | --- |
| `latest_days_since_prior_order` | `>= 30` | `#C0392B`, white text |
| `latest_days_since_prior_order` | `>= 14` and `< 30` | `#E8A29A` |
| `customer_reorder_rate` | data bar, 0 to 1 | `#2E5C8A` |
| `behavioral_score` | icon set, low = red | default |

### Page 3 affinity table

| Column | Rule | Colour |
| --- | --- | --- |
| `lift` | colour scale, min `#F0F0F0` → max `#1F6F54` | — |
| `confidence_a_to_b` | data bar, 0 to 1 | `#2E5C8A` |

### Page 1 department bar

Single colour `#1F6F54`. No rainbow palette — the categories are not ordinal, so colour
would encode nothing.

---

## 6. Things this report must not do

- No pie or donut charts. Department share has 21 near-continuous categories; segment share
  has one dominant group. Both read better as bars.
- No decorative shapes overlapping axis labels or KPI values.
- No mixed precision within a visual.
- No chart whose bars are all within a few percent of each other — if a cut has no
  variation, it does not deserve a full-width visual. The department and aisle cuts do have
  real variation; use those.
- No claim of revenue, margin, or customer lifetime value anywhere in the report. The
  dataset has no prices. Any such figure would be fabricated.

---

## 7. Screenshots to capture

Save into `screenshots/` using these names so the README can reference them directly:

| File | Content |
| --- | --- |
| `executive_overview.png` | Page 1, no slicers applied |
| `customer_segmentation.png` | Page 2, at-risk table visible |
| `basket_cross_sell.png` | Page 3, table sorted by lift descending |
| `temporal_behavior.png` | Page 4, full heatmap |
| `product_department_performance.png` | Page 5, aisle table sorted by worst gap |

---

## 8. Limitations to state on the report itself

Put these in a footer text box on Page 1:

- The dataset contains **no prices, revenue, or quantities**. No monetary metric exists.
- The dataset contains **no absolute dates**. "Recency" is a proxy from
  `days_since_prior_order`; the retention curve is by *order sequence*, not calendar period.
- Basket affinity covers products in >= 1,000 orders and pairs co-occurring >= 100 times.
- Source: public Instacart Market Basket Analysis dataset (Kaggle), 3,421,083 orders.
