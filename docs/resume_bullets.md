# Resume Bullets — Instacart Intelligence Platform

Every number below traces to a real run against the built warehouse. The source of each
figure is named so it can be re-derived before it ships.

**Read the "Not yet true" section at the bottom before using any of this.** Some
capabilities in this repo are written and syntax-checked but have never been executed.

---

## Ready to use — every figure verified

> Built an end-to-end analytics platform on the public Instacart dataset, engineering a
> **33.8M-row order-line fact table** and a conformed star schema in dbt Core, with
> **237 automated data tests** passing on a full build (`PASS=256 WARN=0 ERROR=0`).

> Modelled **3.4M orders across 206K customers and a 49.7K-SKU catalog** into a tested
> dimensional warehouse (staging → intermediate → star schema → marts), pre-aggregating
> every BI-facing mart to under 255K rows so the reporting layer stays performant while
> the 33.8M-row fact remains in the warehouse.

> Wrote the dbt project against **cross-database macros so the same models build on both
> PostgreSQL and BigQuery**, eliminating engine-specific casts and `FILTER` clauses;
> validated all 197 compiled nodes against the warehouse query planner and proved the
> migration was **result-neutral** by diffing every mart before and after — zero
> differences across KPIs, segment counts, retention curve, and row counts.

> Engineered a SQL-only market basket analysis that reduced a **1.23-billion-pair search
> space to 254,490 statistically supported product pairs** with support, confidence, and
> lift, using volume thresholds documented as an explicit precision/recall tradeoff.

> Built a category reorder-diagnostic mart benchmarking all **134 aisles** against their
> parent department, surfacing that **spices & seasonings runs a 15.29% reorder rate —
> 19.45 points below its department** — on 221,371 order items.

> Identified that **morning traffic carries the highest reorder rate at 61.92% against a
> 59.01% platform baseline**, despite midday being the higher-volume daypart, by modelling
> demand across a complete 168-slot day-of-week × hour grid.

> Segmented **206,209 customers** into behavioural engagement tiers in SQL, isolating a
> **44,873-customer at-risk cohort**, and documented why the dataset supports only proxy
> recency and no monetary axis rather than presenting it as RFM.

### Where each figure comes from

| Figure | Source |
| :--- | :--- |
| 33,819,106 order-line records | `select count(*) from analytics_core.fact_order_items` |
| 3,421,083 orders / 206,209 customers / 49,688 products | `mart_executive_kpis` |
| 237 data tests, `PASS=256 WARN=0 ERROR=0` | full `dbt build`, 2026-07-25 (19 models; 6m 52s warm, 3h 35m 53s on the first cold build) |
| Result-neutral migration | `metrics_before` vs `metrics_after` diff over all marts — no differences |
| 197 compiled nodes plan cleanly | `EXPLAIN` over `target/compiled/**/*.sql` |
| 1,234,423,828 possible pairs → 254,490 retained; 5,237 eligible products | `docs/decisions.md` §3 |
| 134 aisles; spices & seasonings 15.29%, −19.45 pts, 221,371 items | `mart_reorder_behavior` |
| Morning 61.92% vs platform 59.01% | `mart_time_patterns` grouped by daypart |
| 44,873 at-risk customers | `mart_customer_segments` grouped by `behavioral_segment` |

---

## Lakehouse + Airflow upgrade — status per bullet

### Usable now (verified by tests in this repo)

> Re-implemented a dbt warehouse as a **bronze → silver → gold Delta Lake medallion in
> PySpark**, proving equivalence by building the original dbt models on a second engine
> and matching **all 5 gold marts and 3 silver tables row for row**; the cross-engine
> test also exposed and fixed a portability bug in the dbt project's surrogate keys.

> Rewrote a quadratic SQL self-join for market-basket pair counting as **per-order array
> pair generation in PySpark** (one shuffle instead of a join), with results identical to
> the SQL implementation.

> Built **Airflow 3** orchestration where a failing **dbt test blocks downstream
> publication**, with retries, exponential backoff, webhook alerting, a deferrable
> Databricks operator, and a backfillable incremental DAG; covered by DAG integrity tests.

Sources: `spark/tests/test_equivalence.py`, `docs/decisions.md` §9, `airflow/tests/dags/`.
State these as *built and tested*, not *deployed*, until the steps below run.

### Usable after Databricks runs (`TASKS.md` I5–I8, J3–J4)

> Engineered **incremental, idempotent Delta `MERGE` loads** on Databricks over a
> 33.8M-row fact table, cutting per-load runtime from TODO: verify (full-mode `run_id`
> total in `instacart_ops.pipeline_runs`) to TODO: verify (incremental `run_id` total).

> Scheduled a 6-stage **Databricks Job** with data-quality gates, reconciled **TODO:
> verify (n / 5) marts** to the PostgreSQL dbt build on the full dataset, and compacted
> the fact table from TODO: verify (files_before) to TODO: verify (files_after) files with
> `OPTIMIZE … ZORDER BY`.

> Orchestrated dbt and Databricks with **Apache Airflow**, backfilling TODO: verify (10)
> incremental loads in order with `depends_on_past` and recovering a bad write with
> **Delta time travel / `RESTORE`**.

---

## Not yet true — do not use until the corresponding step runs

These describe work that exists in the repository but has **never been executed**. Writing
them on a resume today would be a fabrication.

| Claim | Blocked on | Becomes true when |
| :--- | :--- | :--- |
| "Deployed the warehouse to BigQuery" | GCP credentials | `ingestion/load_bigquery.py` runs for real and `dbt build --target bigquery` passes (`TASKS.md` B4) |
| "Automated scheduled builds in CI" | Repo secrets + a first run | `.github/workflows/dbt_build.yml` completes green (`TASKS.md` D4) |
| "Published dbt lineage documentation" | GitHub Pages enabled | `dbt_docs.yml` deploys successfully (`TASKS.md` D4) |
| "Built a 5-page Power BI dashboard" | Power BI Desktop | The `.pbix` is assembled from `bi/powerbi_dashboard_plan.md` (`TASKS.md` E4) |
| "Deployed a Delta lakehouse on Databricks" | A green Job run | `TASKS.md` I6 |
| Any lakehouse runtime, speed-up, or file-count figure | The run log | `instacart_ops.pipeline_runs` has the run (`TASKS.md` I8) |
| "Reconciled to the dbt warehouse on the full dataset" | The reconciliation notebook | 5 / 5 PASS (`TASKS.md` I7) |
| "Orchestrated with Airflow" (as running, not built) | `astro dev start` + a green run | `TASKS.md` J3–J4 |
| Any revenue, margin, AOV, or CLV figure | Nothing — **permanently unavailable** | Never. The dataset contains no prices. |

Until BigQuery has actually run, the honest phrasing is *"written to target both PostgreSQL
and BigQuery; verified on PostgreSQL"* — which is still a stronger claim than most
portfolio projects can make, and it survives an interview question.

---

## Pinned repository description

> End-to-end analytics engineering platform on the Instacart dataset: 33.8M-row fact
> table, dbt star schema with 237 passing tests, cross-database models targeting
> PostgreSQL and BigQuery, scheduled builds in GitHub Actions, and a full Power BI design
> specification with DAX.
