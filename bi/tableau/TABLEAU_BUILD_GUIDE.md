# Tableau Public build guide: Instacart Intelligence Platform

The same five business questions as the Power BI report (`bi/powerbi_dashboard_plan.md`),
rebuilt in **Tableau Public**: free, no credit card, and published to a public URL a
recruiter can click.

Everything here reads the dbt marts. No metric is re-derived in Tableau except the weighted
rates explained in §3, which exist precisely so Tableau does not average rates wrongly.

---

## 0. Setup (one time, ~20 minutes)

1. Install **Tableau Public** (desktop app, free for macOS) and create a free Tableau Public
   account. No card is needed.
2. Start the warehouse and export the marts:

   ```bash
   docker compose up -d
   python bi/tableau/export_for_tableau.py      # writes bi/tableau/data/*.csv + manifest.json
   ```

3. In Tableau Public: **Connect → Text file** → open `bi/tableau/data/`. Add each CSV as
   its **own data source**. The marts have different grains, so joining them would multiply
   rows. The table below says which data source feeds which dashboard.

| CSV | Grain | Rows (full data) | Used by |
| :--- | :--- | ---: | :--- |
| `mart_executive_kpis` | one snapshot row | 1 | Executive Overview |
| `mart_customer_segments` | customer | 206,209 | Executive Overview, Customer Segmentation |
| `mart_cohort_retention` | order-sequence index | 21 | Executive Overview |
| `mart_time_patterns` | day-of-week × hour | 168 | Temporal Behavior |
| `mart_product_performance` | product | 49,688 | Product & Category |
| `mart_reorder_behavior` | department × aisle | 134 | Product & Category |
| `mart_basket_affinity` | product pair | 254,490 | Basket & Cross-sell |

Row counts come from the verified Postgres build (README, Key Metrics). After exporting,
check `manifest.json` against this table. If any count differs, stop and find out why
before building.

Tableau renames columns on import (`behavioral_segment` → **Behavioral Segment**). The
field names below use Tableau's renamed form.

---

## 1. Parameters

Create these once (right-click in the Data pane → **Create Parameter**).

| Parameter | Type | Values | Default | Used for |
| :--- | :--- | :--- | :--- | :--- |
| `Top N` | Integer | range 5–50, step 5 | 20 | Top products list |
| `Min Lift` | Float | range 1–50, step 0.5 | 2 | Basket pair filter |
| `Metric` | String | list: `Orders`, `Reorder rate`, `Avg basket size` | `Orders` | Temporal heatmap metric switch |

Show each parameter control on the dashboard that uses it.

---

## 2. Calculated fields

Create each in the data source named in brackets.

**Customer segments** (`mart_customer_segments`)

```
// Customers
COUNTD([User Id])

// Segment share  (table calculation, compute using Behavioral Segment)
COUNTD([User Id]) / TOTAL(COUNTD([User Id]))

// Customers in segment  (LOD: stays fixed when other filters change the view)
{ FIXED [Behavioral Segment] : COUNTD([User Id]) }

// Recency band  (recency PROXY: days since prior order on the latest observed order)
IF ISNULL([Latest Days Since Prior Order]) THEN "No prior order"
ELSEIF [Latest Days Since Prior Order] >= 30 THEN "30+ days"
ELSEIF [Latest Days Since Prior Order] >= 14 THEN "14–29 days"
ELSE "< 14 days"
END

// Is at risk
[Behavioral Segment] = "At Risk"
```

**Time patterns** (`mart_time_patterns`)

```
// Reorder rate (weighted)
SUM([Reordered Items]) / SUM([Total Order Items])

// Avg basket size (weighted)
SUM([Total Order Items]) / SUM([Total Orders])

// Selected metric
CASE [Metric]
    WHEN "Orders"          THEN SUM([Total Orders])
    WHEN "Reorder rate"    THEN SUM([Reordered Items]) / SUM([Total Order Items])
    WHEN "Avg basket size" THEN SUM([Total Order Items]) / SUM([Total Orders])
END

// Share of peak slot  (table calculation, compute using Table across then down)
SUM([Total Orders]) / WINDOW_MAX(SUM([Total Orders]))
```

**Product & category** (`mart_product_performance`, `mart_reorder_behavior`)

```
// Reorder rate (weighted)  -- in mart_reorder_behavior
SUM([Reordered Items]) / SUM([Total Order Items])

// Reordered items (approx.)  -- mart_product_performance has the rate, not the count.
// The rate is rounded to 4 decimals in the mart, so this is accurate to about 0.01%.
[Reorder Rate] * [Total Order Items]

// Reorder rate (weighted)  -- in mart_product_performance
SUM([Reordered Items (approx.)]) / SUM([Total Order Items])

// Gap vs department label
IF [Reorder Rate Vs Department] <= -0.15 THEN "Far below department"
ELSEIF [Reorder Rate Vs Department] < -0.05 THEN "Below department"
ELSEIF [Reorder Rate Vs Department] <= 0.05 THEN "In line"
ELSE "Above department"
END
```

**Basket** (`mart_basket_affinity`)

```
// Pair label
[Product A Name] + "  +  " + [Product B Name]

// Passes lift filter  (put on Filters shelf, keep True)
[Lift] >= [Min Lift]
```

**Why the weighted rates matter (interview point).** Each row of a mart already holds a
rate. If Tableau's default `AVG(Reorder Rate)` is used when rolling 168 time slots up to 5
dayparts, every slot counts equally regardless of volume, and a 3 a.m. slot with 654 orders
weighs as much as Monday 10:00 with 55,671. Summing numerators and denominators first
gives the true rate. The data dictionary warns against averaging rates for the same reason.

---

## 3. Dashboards

Use one layout for all five: a title bar with the business question as the subtitle, KPI
tiles across the top, the main view below. Fixed size 1200 × 800.

### 3.1 Executive Overview: *what is the current state of the platform?*
- **KPI tiles** (`mart_executive_kpis`, one sheet per tile, Big Number style): Total
  Orders, Total Customers, Total Products, Total Order Items, Reorder Rate (format % 2 dp),
  Average Basket Size, Average Orders per Customer.
- **Retention curve** (`mart_cohort_retention`): Observed Order Number (continuous) on
  Columns, Retention Rate on Rows, line with markers; label orders 5, 10, 15, 20.
- **Segment bar** (`mart_customer_segments`): Behavioral Segment by `Customers`, sorted
  descending, labels showing `Segment share`.

### 3.2 Customer Segmentation: *which customers are disengaging?*
- **Segment × recency band matrix**: Behavioral Segment on Rows, Recency band on Columns,
  `Customers` as text and colour (sequential blue).
- **At-risk work queue**: table filtered to `Is at risk` = True, columns User Id, Total
  Orders, Customer Reorder Rate, Latest Days Since Prior Order. Sort descending by
  Latest Days Since Prior Order. Colour Latest Days Since Prior Order: `>= 30` `#C0392B`,
  `14–29` `#E8A29A`.
- Subtitle note: *"Recency is a proxy (days since prior order). The dataset has no
  calendar dates or prices, so this is behavioural segmentation, not RFM."*

### 3.3 Basket & Cross-sell: *which products sell together strongly enough to act on?*
- **Scatter**: Support on Columns, Confidence A To B on Rows, Lift on Size and Colour
  (`#F0F0F0` → `#1F6F54`), `Pair label` on Detail and Tooltip. `Passes lift filter` = True.
- **Top pairs table**: Pair label, Orders With Both, Support (% 4 dp; values are small),
  Confidence A To B, Lift, sorted by Lift descending.
- **Dashboard action**: selecting a point in the scatter filters the table.
- Caption: *"Pairs need ≥ 100 co-orders among products in ≥ 1,000 orders (see
  docs/decisions.md §3)."*

### 3.4 Temporal Behavior: *when do customers order, and does intent change?*
- **Heatmap**: Order Day Of Week on Rows (sort by Order Dow, ascending), Order Hour Of Day
  on Columns, `Selected metric` on Colour and Label, square marks. The `Metric` parameter
  control switches the measure.
- **Daypart bars**: Daypart by `Reorder rate (weighted)`, with a reference line at the
  platform rate from `mart_executive_kpis`. A separate source can't drive a reference
  line, so type the constant (0.5901) into a calculated field and note its source in the
  caption.

### 3.5 Product & Category: *which categories under-perform their own department?*
- **Aisle diagnostic** (`mart_reorder_behavior`): Aisle Name on Rows, Reorder Rate Vs
  Department on Columns, sorted **ascending** so the worst gaps are first. Diverging colour
  centred at 0 (`#C0392B` → `#F0F0F0` → `#1F8A54`). Exclude Below Volume Floor = True.
- **Top products** (`mart_product_performance`): Product Name filtered to Top `[Top N]` by
  SUM(Total Order Items); bars coloured by `Reorder rate (weighted)`.
- **Department filter** applied to both sheets (Apply to Worksheets → Selected).

---

## 4. Publish

**File → Save to Tableau Public As…**, name it *Instacart Intelligence Platform*. Then on
the Tableau Public site:
- Set the workbook description to the README's one-line summary and link the GitHub repo.
- Turn on **Allow access** for workbook downloads.
- Copy the public URL into: the README "Dashboard" section, `bi/tableau/README.md`, and
  your resume (see §6).

---

## 5. Verify before it counts

Tick each box against the verified Postgres figures (README, Key Metrics):

- [ ] Total Orders tile = **3,421,083**; Total Customers = **206,209**; Total Products = **49,688**.
- [ ] Reorder Rate tile = **59.01%**.
- [ ] Segment bars: High Engagement **28,883**, Loyal Routine **62,818**, At Risk **44,873**,
      Moderate Engagement **69,635** (total 206,209).
- [ ] Retention at order 10 = **53.70%**.
- [ ] Heatmap: busiest slot Monday 10:00 (**55,671** orders); quietest Wednesday 03:00 (**654**).
- [ ] Morning daypart reorder rate = **61.92%** (if you see a different value, AVG was used
      instead of the weighted calc).
- [ ] Top pair by lift and by support match README Module 3.

If any check fails, the workbook is wrong, not the warehouse.

---

## 6. What this adds to the resume (after it is published)

Only once the public link works:

- Skills line: add **Tableau** next to Power BI.
- Instacart Power BI bullet becomes: *"Built **Power BI and Tableau** dashboards…"*, with the
  Tableau Public link in the README.

## 7. Interview talking points

- **LOD vs table calculation.** `{ FIXED [Behavioral Segment] : COUNTD([User Id]) }` is
  computed before view filters, so the segment size stays stable while the at-risk table
  is filtered. `TOTAL(...)` is computed on the view, so the share recomputes with filters.
  Which one to use depends on whether the number should react to the user's filter.
- **Weighted vs averaged rates** (§2), and why the marts store numerators and denominators.
- **Extracts.** Tableau Public stores data as an extract, so the published workbook is a
  snapshot. The source of truth stays in the warehouse and the dbt tests.
- **Same questions, two tools.** Power BI and Tableau answer identical questions from the
  same marts, which shows the modelling, not the BI tool, holds the logic.
