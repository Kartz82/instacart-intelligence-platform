# Lakehouse layer — PySpark + Delta Lake on Databricks

The same Instacart pipeline as the dbt project, rebuilt as a **bronze → silver → gold
Delta Lake medallion** in PySpark, with **incremental MERGE loads**, **time travel**,
**OPTIMIZE / Z-ORDER**, data-quality gates, and a **scheduled Databricks Job**.

The dbt project stays the reference implementation. Every Spark transformation is a
port of a named dbt model and is **tested row for row against dbt's own output**.

---

## Business question this layer answers

*Can the warehouse logic move to a distributed engine without changing a single
number, and can it load new data incrementally instead of rebuilding 33.8M rows?*

---

## Layout

| Path | What it is |
| :--- | :--- |
| `instacart_spark/bronze.py` | CSV → typed bronze with explicit schemas, `FAILFAST` parsing, lineage columns (`_batch_id`, `_ingested_at`, `_source_file`); wave selection for simulated arrivals |
| `instacart_spark/silver.py` | Ports of 5 staging + 2 intermediate + 5 core dbt models (`dim_orders`, `dim_customers`, `dim_products`, `dim_time`, `fact_order_items`) |
| `instacart_spark/gold.py` | Ports of 5 marts: `mart_executive_kpis`, `mart_customer_segments`, `mart_cohort_retention`, `mart_time_patterns`, `mart_basket_affinity` |
| `instacart_spark/incremental.py` | Delta `MERGE INTO` upserts, and the pure-DataFrame form of the same rule used in tests |
| `instacart_spark/delta_ops.py` | `OPTIMIZE … ZORDER BY`, `DESCRIBE HISTORY`, `VERSION AS OF`, `RESTORE` |
| `instacart_spark/quality.py` | Data-quality gates (uniqueness, referential integrity, accepted values, ranges, reconciliation) that fail the Job |
| `instacart_spark/runlog.py` | Times every stage into `instacart_ops.pipeline_runs` — the only source for runtime claims |
| `instacart_spark/reconcile.py` | Row-for-row comparison of Spark marts vs dbt marts, Markdown report |
| `instacart_spark/pipeline.py` | The six stages the Job runs: setup · bronze · silver · gold · quality · optimize |
| `notebooks/run_stage.py` | Databricks notebook each Job task runs (widgets → `pipeline.run_stage`) |
| `notebooks/delta_features_demo.py` | Version history, time travel, bad-write `RESTORE`, OPTIMIZE before/after |
| `notebooks/reconcile_with_dbt.py` | Databricks gold vs the Postgres dbt marts |
| `databricks/instacart_lakehouse_job.json` | Job definition: 6 chained notebook tasks on serverless, job parameters, retries |
| `scripts/export_dbt_marts.py` | Exports the 5 dbt marts from Postgres to Parquet for reconciliation |
| `tests/` | Equivalence, incremental convergence, invariants, end-to-end stage wiring |

---

## Engineering choices worth asking about in an interview

**Basket affinity without a self-join.** The SQL self-joins the line-item table on
`order_id`. The Spark port collapses each order's eligible products into one sorted
array and generates the `a < b` pairs from it locally — one shuffle on `order_id`
instead of a join that shuffles every line against every other line in its order.
Results are identical: `collect_set` guarantees one entry per (order, product), so
counting pairs equals the SQL's `count(distinct order_id)`.

**Incremental silver, rebuilt gold.** A wave MERGEs into `dim_orders` and
`fact_order_items` on their natural keys, and recomputes `dim_customers` **only for the
customers in the wave**, from their full history. Gold is rebuilt: the marts are small,
and several are global by definition — one new order can shift every customer's
`ntile()` score and every pair's support denominator.

**Idempotent re-runs.** Because every MERGE is keyed on the natural grain, re-running a
wave changes nothing. That is what makes Airflow retries and backfills safe.

**Measured, not claimed.** Stage runtimes, MERGE row counts and OPTIMIZE file counts are
written by the pipeline to `instacart_ops.pipeline_runs`. Nothing in this repo quotes a
runtime that is not in that table.

---

## How correctness is proven

| Test | What it proves | Where it runs |
| :--- | :--- | :--- |
| `test_equivalence.py` | The real dbt models are built on **DuckDB** (`dbt-duckdb`) over a synthetic sample; all 5 Spark gold marts and 3 silver tables match them row for row | local + CI |
| `test_incremental.py` | Loading wave by wave converges to exactly the full-load state, silver and gold; re-running a wave is a no-op | local + CI |
| `test_delta_incremental.py` | The same, through the real pipeline stages with **real Delta MERGE, OPTIMIZE and time travel** | CI (needs the Delta jars) |
| `test_invariants.py` | 168-slot grid, order-count reconciliation, fact grain, quality gates pass on clean data and **catch an injected orphan row** | local + CI |
| `test_pipeline_local.py` | All six stages run end to end and write the run log | local + CI |
| `notebooks/reconcile_with_dbt.py` | Databricks gold vs the Postgres dbt marts **on the full 33.8M-row dataset** | Databricks |

The synthetic sample (`tests/make_sample_data.py`) exists only to give dbt and Spark
the same small input. **No number from it appears in any README or resume bullet.**

Two things the equivalence test surfaced, both fixed in the dbt project rather than
papered over in Spark — see `docs/decisions.md` §9 and §10.

### Run the tests

```bash
python -m venv .venv-spark && source .venv-spark/bin/activate
pip install -r spark/requirements-dev.txt          # needs Java 17+
dbt deps --project-dir dbt --profiles-dir dbt
cd spark
DBT_ORACLE_PROJECT_DIR=../dbt TEST_WITH_DELTA=1 pytest tests -v
```

Leave out `TEST_WITH_DELTA=1` if your machine cannot download the Delta jars from Maven;
the Delta test is then skipped and everything else still runs.

---

## Running it on Databricks Free Edition

1. **Git folder.** Workspace → *Create* → *Git folder* →
   `https://github.com/Kartz82/instacart-intelligence-platform` (public; no credentials).
   Check out the branch that holds this code.
2. **Schemas + volume.** Open `spark/notebooks/run_stage`, set `stage = setup`, run all.
   Creates `instacart_bronze`, `instacart_silver`, `instacart_gold`, `instacart_ops` and
   the volume `/Volumes/workspace/instacart_bronze/raw`.
3. **Upload the CSVs** to that volume (Catalog → volume → *Upload to this volume*):
   `departments.csv`, `aisles.csv`, `products.csv`, `orders.csv`, and either the
   pre-unioned `order_products.csv` or both `order_products__prior.csv` and
   `order_products__train.csv`.
4. **Create the Job** from `databricks/instacart_lakehouse_job.json`: six notebook tasks
   (`setup → bronze → silver → gold → quality → optimize`), serverless compute, job
   parameters `mode`, `wave`, `catalog`, `raw_path`. Replace `{{YOUR_EMAIL}}` in the
   notebook paths with your workspace user folder. Add a schedule and failure email in
   the Job UI.
5. **Run it** with `mode = full`. Then, for the incremental story, run it with
   `mode = incremental` and `wave = 0, 1, 2 …` (or let Airflow backfill it — see
   `airflow/README.md`) into a fresh set of schemas.
6. **Prove it**: run `notebooks/delta_features_demo` and `notebooks/reconcile_with_dbt`.

---

## Results on the full dataset

Filled in only from `instacart_ops.pipeline_runs` and the reconciliation notebook.

| Measurement | Value |
| :--- | :--- |
| Full-load Job, total wall clock | TODO: verify (sum of `seconds` for one full-mode `run_id` in `instacart_ops.pipeline_runs`) |
| Slowest stage | TODO: verify (max `seconds` by stage for that run) |
| Incremental wave, average wall clock | TODO: verify (avg `seconds` of bronze+silver+gold per incremental `run_id`) |
| Rows MERGEd per wave | TODO: verify (`details.merge` for incremental bronze/silver rows) |
| `fact_order_items` files before → after OPTIMIZE | TODO: verify (`details.optimize` of the optimize stage) |
| Marts reconciling to dbt (Postgres) | TODO: verify (`reconcile_with_dbt` output; target 5 / 5) |

---

## Known limits

- **Databricks Free Edition** runs serverless compute with daily usage limits; a full
  load of 33.8M line items plus the affinity pair generation is the heaviest stage.
- Delta `MERGE`, `OPTIMIZE` and time travel are verified in CI (`test_delta_incremental.py`,
  synthetic sample). `RESTORE`, the Databricks notebooks and the Job have **not** been run
  on Databricks yet; nothing claims they work on the full dataset until they do.
- Waves are a **simulation** of arrival over a static extract (order-number windows),
  not real event-time data. The dataset has no timestamps.
