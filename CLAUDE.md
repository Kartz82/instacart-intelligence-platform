# CLAUDE.md — Flagship Data Projects Build Context

> **How to use this file:** This is the project brief for Claude Code. Read it first, then scan the repo (see "First actions" below) before generating anything. A copy of this file lives in both flagship repos.

---

## Author & objective

- Owner: **Kartz** — GitHub `Kartz82`, portfolio `kartz82.github.io`.
- Background: M.S. Data Science; core stack **Python, SQL, dbt Core, PostgreSQL, BigQuery, GCP, Power BI (DAX/Power Query), Snowflake, Docker**. Holds **GCP Professional Data Engineer**, GCP ACE, and PL-300.
- Goal: build **two flagship portfolio projects** that (a) prove real Data Engineer + BI capability and (b) survive AI/ATS resume screening by being recruiter-legible.
- The two flagships must showcase **different** capabilities — do not build two near-identical dbt+PowerBI projects.

## Resolved decisions

1. **Warehouse for Flagship #1: PostgreSQL is the verified default; BigQuery is an additional target.** The brief originally recommended BigQuery to align with the GCP PDE cert, but this repo was already built, run, and verified end-to-end on PostgreSQL 15, and the numbers published on the portfolio site came from that run. Resolution: keep Postgres as the dev/default target, make the dbt models cross-database portable, and add a BigQuery target + `bq load` ingestion path + CI that runs against BigQuery. See `docs/decisions.md`.
2. **Flagship #2 identity: KPI Reliability & Diagnostic Engine** (`~/Projects/data-reliability-kpi-monitoring`) — differentiated, maps to Data QA / Analytics Engineer roles. It is a **packaging upgrade of existing working code, not a rebuild**.

---

## THE HARD RULES (do not violate)

1. **No fabrication.** Never invent, estimate, or "fill in" a metric, row count, percentage, or result. Every number that lands in a README, comment, or resume bullet must trace to an actual query/script output that has been run. Where a real number isn't available yet, write a literal `TODO: verify (<how to obtain it>)` placeholder — never a plausible-looking fake.
2. **Verify, don't assume.** Recompute figures from the data; do not carry forward numbers from prior notes as fact.
3. **Agent boundaries — these need the human, flag them, don't fake them:**
   - Cannot download from Kaggle (needs the human's login). *(Already satisfied: `data/raw/` is populated.)*
   - Cannot run BigQuery/GCP without the human's credentials.
   - Cannot build or render a Power BI `.pbix` — the agent produces the **design spec + DAX definitions**; the human assembles the dashboard.
   - Cannot push/pin to the human's GitHub or take dashboard screenshots.
4. **Recruiter-legibility is a requirement, not a nice-to-have.** READMEs lead with business questions, then page-by-page/model-by-model breakdown, then a skills→usage map. This project is partly a fix for ATS auto-rejection, so keyword density and business framing matter.

---

## FLAGSHIP #1 — Instacart Intelligence Platform (Data Engineer + BI)

**Positioning:** "I can engineer and visualize a real warehouse at scale." This is the volume + end-to-end pipeline story. Lead with the **~32M order-line records** in `fact_order_items` (bigger signal than "3.4M orders").

### Dataset — Instacart Market Basket Analysis (Kaggle)

| File | Grain | Approx rows | Key columns |
|---|---|---|---|
| `orders.csv` | one order | ~3.4M | order_id, user_id, eval_set, order_number, order_dow, order_hour_of_day, days_since_prior_order |
| `order_products__prior.csv` | order × product | ~32.4M | order_id, product_id, add_to_cart_order, reordered |
| `order_products__train.csv` | order × product | ~1.38M | order_id, product_id, add_to_cart_order, reordered |
| `products.csv` | product | ~49.7K | product_id, product_name, aisle_id, department_id |
| `aisles.csv` | aisle | 134 | aisle_id, aisle |
| `departments.csv` | department | 21 | department_id, department |

Notes: `eval_set` splits orders into prior/train/test; `test` has no product labels. The item fact table is built from **prior + train** (`data/raw/order_products.csv` is the pre-unioned file the loader reads).

**Dataset limitation to respect:** the Instacart data contains **no absolute timestamps** — only `order_dow`, `order_hour_of_day`, and `days_since_prior_order`. True calendar recency and monetary value are therefore not derivable. RFM-style work must use documented proxies (recency proxy from `days_since_prior_order`, monetary proxy from basket size), and must say so. Do not present a proxy as true RFM.

### Architecture

1. **Ingestion** — Python loader → warehouse, scripted and reproducible (not manual upload). `src/database_loader.py` for Postgres; `ingestion/` for the BigQuery path.
2. **Staging** (`stg_*`) — one per source: orders, order_products (prior+train), products, aisles, departments. Light typing/renaming only.
3. **Intermediate** — `int_order_item_enriched` (join product → aisle → department), `int_customer_order_history`.
4. **Dimensional star schema** — `dim_customers`, `dim_products` (denormalized w/ aisle + department), `dim_orders`, `dim_time` (from order_dow + order_hour_of_day), `fact_order_items` (grain: one product per order — the ~32M-row fact; this is the scale flex).
5. **Marts** (each answers one business question) — `mart_customer_segments`, `mart_basket_affinity` (support / confidence / lift), `mart_reorder_behavior`, `mart_cohort_retention`, `mart_time_patterns`, `mart_product_performance`, `mart_executive_kpis`.
6. **BI layer** — pre-aggregate in the marts so Power BI imports small/fast tables (keep the 32M-row fact in the warehouse). Architecture talking point: *"pre-aggregate in dbt so the BI layer stays performant at scale."*

### dbt requirements

- `dbt_project.yml`, `packages.yml`, `sources.yml`, per-model `schema.yml`.
- **Tests: 40+ target.** Reference bar: the Customer Intelligence DW project had 41 tests. *(This repo is already well past that — see TASKS.md for the verified count.)*
- `dbt docs generate` → lineage graph, hosted on GitHub Pages.

### Orchestration

This is the piece that makes it read as **DE, not analyst-with-dbt.** A **GitHub Actions** workflow runs `dbt build` on a schedule. Human wires secrets/service account.

---

## FLAGSHIP #2 — KPI Reliability & Diagnostic Engine (Analytics Engineer / Data QA)

**Positioning:** "I can diagnose why metrics break and measurably fix detection." This is an **upgrade of an existing project**, not a rebuild — most of the work is packaging + a clear before/after story.

- What it is: anomaly detection + root-cause analysis across 5 KPIs (Conversion Rate, CTR, Revenue/Session, AOV, Latency) over a synthetic daily panel, across region/device/browser/channel/segment.
- The story: static-threshold monitoring flagged normal variation → replaced with **residual-based detection (actual − expected) + contribution-based RCA** → large false-positive reduction with recall held. **Every figure in that story must be re-derived from a real pipeline run before it ships.**
- Stack: Python, PostgreSQL, SQL, dbt Core, Pandas, NumPy, Plotly, **Streamlit**.
- **Data is synthetic** (self-generated with injected known anomalies). State this prominently — it's honest AND a strength (controlled ground truth, so recall/F1 are meaningful).

Agent tasks: restructure README to the standard format; build a before/after comparison table from a real run; write the Streamlit layout spec; diagram the detection→RCA flow; write a "Decisions & tradeoffs" section (why residual beat static thresholds). Human re-runs, screenshots, re-pushes.

---

## BI / dashboard design principles (for the Power BI SPEC the agent writes)

The agent does **not** build the `.pbix` — it writes the spec + DAX; the human assembles.

**Do:**
- One cohesive custom theme; sidebar nav with active-state; clean KPI cards; a repeating layout grid across pages.
- Encode meaning with **conditional formatting** — heatmap tables, red for loss/risk (flag at-risk customers, low-reorder products). This is the single strongest technique the benchmark dashboards used.
- Decision-oriented tables that surface the *bad* cases (churning users, low-reorder SKUs), not just totals.
- A dynamic metric × dimension selector page (field parameters).

**Don't:**
- Pie/donut for >3 categories or near-equal splits.
- Decorative elements crossing axis labels; playful fonts on a serious dashboard.
- Over-rounding / inconsistent precision.
- Full-page charts whose bars are all ~equal — if there's no variation, drop the chart or find the cut that has signal.

**Pages (5):** Executive Overview · Customer Segmentation (segments + at-risk cohort) · Basket & Cross-sell · Temporal Behavior (DOW × hour heatmap) · Product/Department Performance.

---

## Ownership split

**Agent can produce here:** ingestion script · dbt models + tests · mart SQL · orchestration config · Dockerfile/requirements · Power BI design spec + DAX definitions + conditional-formatting rules · architecture diagram + ERD + data dictionary · both READMEs · "Decisions & tradeoffs" · grounded resume bullets · pinned-repo descriptions.

**Human must do:** GCP/BigQuery setup + run the BigQuery loader · build Power BI dashboard · screenshots · run orchestration in own GitHub · host dbt docs · push/pin repos · **verify every metric before it ships.**

---

## Working notes for agents in this repo

1. **Full `dbt build` timings vary enormously: 3h 35m on the first cold build, 6m 52s on a warm rebuild** of the same project (likely planner statistics — the cold run had no `ANALYZE` stats for the `mart_basket_affinity` self-join over 33.8M rows; unconfirmed). Assume it may be slow: background it, never block on it. Validate SQL changes with `dbt parse` plus `EXPLAIN` over `target/compiled/**/*.sql`. Do **not** use `dbt build --empty` against the default target — it materialises with `LIMIT 0` and would wipe the built marts; point it at a scratch dataset instead.
2. The Postgres warehouse runs in Docker on host port **5434** (`docker compose up -d`, container `instacart_postgres`). The `raw` schema is already loaded.
3. Run dbt from the `dbt/` directory using the repo venv: `../venv/bin/dbt <cmd> --profiles-dir .`
4. Reuse conventions from `~/Projects/customer_intelligence_warehouse` so the two flagships feel consistent.
5. Never run anything that needs credentials the environment doesn't have — surface it as a human step instead.
