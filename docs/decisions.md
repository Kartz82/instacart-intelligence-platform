# Decisions & Tradeoffs

Every decision here changed what the warehouse can and cannot answer. Each entry states
the context, the options considered, what was chosen, and what that choice costs.

All figures on this page were produced by querying the built warehouse, not estimated.

---

## 1. PostgreSQL is the default target; BigQuery is a second target, not a replacement

**Context.** The project brief recommended BigQuery to align with the GCP Professional
Data Engineer certification. By the time that recommendation was acted on, the platform
had already been built, loaded, and verified end-to-end on PostgreSQL 15, and the figures
published on the portfolio site came from that run.

**Options.**

| Option | Effect |
| --- | --- |
| Migrate fully to BigQuery | Cert alignment, but discards a verified build and makes every published figure unreproducible without a paid GCP project |
| Stay on Postgres only | Reproducible and free, but no cloud-warehouse evidence |
| Make the models portable, run on both | Both stories, at the cost of writing SQL against the lowest common denominator |

**Chosen.** Portability. Every model uses dbt cross-database macros —
`{{ dbt.type_int() }}`, `{{ dbt.type_numeric() }}`, `{{ dbt.type_string() }}`,
`{{ dbt.type_float() }}` — instead of Postgres-only `::numeric(10,4)` casts,
`FILTER (WHERE ...)` clauses, and `VARCHAR`. `sources.yml` reads its schema from
`DBT_RAW_SCHEMA` so the same source definition resolves to a Postgres schema or a
BigQuery dataset.

**Tradeoff.** Portable SQL is more verbose: `max(order_id) FILTER (WHERE rank = 1)`
becomes `max(case when rank = 1 then order_id end)`. Two engines also mean two ways for
a change to break, so the Postgres build is the gate that must stay green.

**Verification status.** Postgres is verified — a full `dbt build` returns
`PASS=256 WARN=0 ERROR=0` (19 models, 237 data tests), and every compiled node plans
cleanly under `EXPLAIN`. The rewrite was also proved result-neutral: every mart was
snapshotted before the change and diffed after the rebuild, with **zero differences**
across executive KPIs, segment counts, the retention curve, affinity pair count and max
lift, and all eight table row counts.

The BigQuery target is written but **not yet executed**; it requires GCP credentials.
See `TASKS.md` item B4.

---

## 2. The customer segmentation is behavioural, not true RFM

**Context.** The obvious segmentation for retail data is RFM — Recency, Frequency,
Monetary.

**The blocker.** The Instacart dataset supports only one of those three directly:

| RFM component | Available? | Why |
| --- | --- | --- |
| Recency | No | There are no absolute timestamps. The only temporal fields are `order_dow` (0-6), `order_hour_of_day` (0-23), and `days_since_prior_order` |
| Frequency | Yes | `order_number` and the observed order count are real |
| Monetary | No | The dataset contains **no prices and no quantities**. Revenue cannot be derived at any grain |

**Chosen.** `mart_customer_segments` scores four behavioural axes — order frequency,
average basket size, reorder rate, and a recency *proxy* built from
`days_since_prior_order` on the customer's most recent observed order — and the columns
are named to say so (`recency_proxy_score`, `basket_size_score`).

**Tradeoff.** The segments are not comparable to a revenue-based RFM model and must not
be described as such. Presenting a basket-size score as "monetary value" would be a
fabricated metric. The honest framing is the stronger one anyway: it demonstrates
knowing what the data cannot support.

---

## 3. Basket affinity is thresholded, because the pair space is otherwise unusable

**Context.** Product co-occurrence is a self-join of the 33,819,106-row fact table
against itself. Pair counts grow quadratically with the catalog.

**The arithmetic**, from the built warehouse:

| Stage | Count |
| --- | ---: |
| Products in the catalog | 49,688 |
| Distinct pairs if every product were eligible | 1,234,423,828 |
| Products appearing in >= 1,000 distinct orders | 5,237 (10.5% of the catalog) |
| Distinct pairs among eligible products | 13,710,466 |
| Pairs surviving the >= 100 co-order threshold, i.e. rows in `mart_basket_affinity` | 254,490 |

**Chosen.** Two thresholds: products must appear in >= 1,000 distinct orders to enter the
join, and a pair must co-occur in >= 100 orders to be emitted.

**Tradeoff.** Long-tail products are excluded entirely, so the mart cannot answer
"what pairs with this rare item". That is the correct trade: below those volumes, lift is
dominated by sampling noise — a pair seen 3 times together can post a spectacular lift
that means nothing. The thresholds are the honest boundary of what the data supports, and
they are documented in the mart rather than hidden.

---

## 4. Low-volume categories are flagged, not filtered

**Context.** `mart_reorder_behavior` reports reorder rate per department x aisle. Small
aisles produce unstable rates.

**Chosen.** A `below_volume_floor` boolean (floor: 1,000 order line items). Rows stay in
the mart; the BI layer greys them out.

**Why not filter.** Filtering would silently drop categories from dashboard totals, so
department sums would no longer reconcile to the platform total — a class of bug that is
invisible until someone adds up the numbers by hand.

**Result on this data.** All 134 aisles clear the floor; **0 rows are flagged**. The guard
never binds on the current dataset. It stays in because the floor is a property of the
method, not of this particular extract, and a future load with a sparser catalog would
need it.

---

## 5. `dim_time` is generated, not derived from the fact table

**Context.** The finest real time grain in this dataset is day-of-week x hour-of-day:
7 x 24 = 168 slots.

**Chosen.** Generate the full 168-row grid with `dbt_utils.generate_series` and left-join
the facts onto it, rather than `SELECT DISTINCT` from the orders table.

**Why.** A derived dimension only contains slots that have data. If a slot had zero
orders it would vanish, and the heatmap would silently reshape itself instead of showing
an empty cell — the visually important result. A singular test asserts the grid is exactly
168 rows with 7 distinct days and 24 distinct hours.

**Tradeoff.** None material; the dimension is 168 rows.

---

## 6. Aggregation happens in dbt, not in the BI tool

**Context.** `fact_order_items` holds 33,819,106 rows. Power BI can import it, but the
model file would be enormous and every visual would recompute aggregates on refresh.

**Chosen.** Every mart is pre-aggregated to a BI-sized grain, and the fact table stays in
the warehouse:

| Mart | Grain | Rows |
| --- | --- | ---: |
| `mart_time_patterns` | day-of-week x hour | 168 |
| `mart_reorder_behavior` | department x aisle | 134 |
| `mart_executive_kpis` | one snapshot row | 1 |
| `mart_basket_affinity` | product pair | 254,490 |

**Tradeoff.** Every new question that needs a different cut requires a new dbt model
rather than a drag-and-drop change in Power BI. That is the intended direction: it puts
the business logic in version-controlled, tested SQL instead of inside a `.pbix` file
nobody can diff.

---

## 7. Order counts and item counts are aggregated separately

**Context.** `mart_time_patterns` reports both orders and line items per time slot.

**The trap.** Joining the order grain to the line-item grain and counting would multiply
each order by its basket size — inflating "orders" by roughly 10x, in a way that still
looks plausible on a heatmap.

**Chosen.** Aggregate `dim_orders` and `fact_order_items` in separate CTEs, then join both
onto `dim_time`. A singular test
(`assert_mart_time_patterns_reconciles_to_orders.sql`) asserts that
`sum(total_orders)` in the mart equals the row count of `dim_orders`.

**Verified.** Both equal **3,421,083**.

---

## 8. There is no "Early Lifecycle" segment, because the sample contains no new customers

**Context.** `mart_customer_segments` originally defined five behavioural segments. One of
them, `Early Lifecycle`, matched **zero customers** in every build.

**The cause.** The branch condition was `frequency_score <= 2 and total_orders <= 3`. That
is unsatisfiable against this dataset. Queried from the built warehouse:

| Measure | Value |
| --- | ---: |
| Minimum orders per customer | 4 |
| Maximum orders per customer | 100 |
| Customers with <= 3 orders | 0 |
| Customers with exactly 4 orders | 23,986 |

The Instacart extract is a curated sample: users were selected to have between 4 and 100
orders. Customers new to the platform are excluded from the sample by construction.

**Options.**

| Option | Effect |
| --- | --- |
| Lower the threshold until the segment populates | Manufactures a lifecycle stage the data does not contain; the segment would be an artefact of the chosen cut point, not a real cohort |
| Leave the dead branch in place | A segment that never appears in the BI layer, and a documented five-segment model that actually produces four |
| Remove the branch and document why | Four segments, all populated, and the sample's limitation stated explicitly |

**Chosen.** Removed. The model defines four segments, and all four are populated.

**Tradeoff.** The segmentation cannot describe customer onboarding or first-purchase
behaviour. That is a property of the sample rather than of the method — on a full
transaction log the branch would be reinstated.

**Guarded by a test.** `assert_customer_segments_cover_all_customers.sql` fails if any
expected segment is empty, if an unexpected segment appears, or if any customer is left
unclassified. An unsatisfiable CASE branch is invisible in code review — it looks correct
and simply never fires — so the invariant is enforced rather than trusted.

**Verified.** Segment counts are unchanged by this fix, because the removed branch never
matched anything: High Engagement **28,883**, Loyal Routine **62,818**, At Risk **44,873**,
Moderate Engagement **69,635**. Total **206,209**, reconciling to `dim_customers`.
