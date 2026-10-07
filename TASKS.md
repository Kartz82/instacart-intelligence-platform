# TASKS — Instacart Intelligence Platform (Flagship #1)

Legend: `[AGENT]` = Claude Code can complete and verify. `[HUMAN]` = needs credentials, GUI tooling, or Kartz's accounts.

Last loop update: 2026-10-07 (lakehouse + Airflow upgrade, branch `feature/lakehouse-spark-airflow`).

---

## Verified baseline (established this session, do not re-derive by guessing)

- Starting baseline, before any change: **`PASS=199 WARN=0 ERROR=0`** — 16 models, **183 data tests** — in **3h 35m 53s** (cold).
- Final state, after all model work: **`PASS=256 WARN=0 ERROR=0 SKIP=0`** — 19 models (12 tables, 7 views), **237 data tests** — in **6m 52s** (warm). Same machine, same data, byte-identical marts; see G2. The 31x gap is most likely planner statistics on the cold run, but that was not measured — both numbers are recorded rather than only the fast one.
- Warehouse is live: Docker container `instacart_postgres`, host port 5434, `raw` schema loaded, `analytics_*` schemas materialized.
- Raw Kaggle CSVs already present in `data/raw/` — the Kaggle-download human step is **already satisfied**.

---

## A. Foundation

- [x] **A1 [AGENT]** Add `CLAUDE.md` to repo root. *done = file exists and records the resolved Postgres/BigQuery decision and the cold-vs-warm build-time warning.*
- [x] **A2 [AGENT]** Add `TASKS.md` (this file). *done = every open item is atomic, tagged, and has a "done =" condition.*
- [x] **A3 [AGENT]** Establish a verified green baseline before changing anything. *done = full `dbt build` exits 0; counts recorded above.*
- [x] **A4 [AGENT]** Write `docs/decisions.md` — the Postgres-vs-BigQuery call, why proxy-RFM instead of true RFM, why pre-aggregate for BI, why basket affinity is thresholded at 1000/100. *done = 7 decisions, each with Context / Options / Chosen / Tradeoff, every figure queried from the built warehouse.*
- [x] **A5 [AGENT]** Add `dbt/packages.yml` pinning `dbt_utils`. *done = `dbt deps` installed dbt_utils 1.4.1 cleanly.*

## B. Cross-database portability + BigQuery target

- [x] **B1 [AGENT]** Replace Postgres-only SQL in all 16 models with dbt cross-db macros. *done = zero `::` / `filter (where` / `double precision` left in `models/`; `dbt parse` clean; **all 197 compiled nodes pass `EXPLAIN` against Postgres**. `EXPLAIN` was used instead of `dbt build --empty` because `--empty` would have overwritten the 3.5h-old materialized tables with `LIMIT 0` results.*
- [x] **B2 [AGENT]** Add a `bigquery` output to `dbt/profiles.yml.example` and `dbt/profiles.yml`. *done = both targets documented; `sources.yml` schema now reads `DBT_RAW_SCHEMA` so it resolves to a Postgres schema or a BigQuery dataset. Verified `stg_orders` still compiles to `"instacart_db"."raw"."orders"`.*
- [x] **B3 [AGENT]** Write `ingestion/load_bigquery.py`. *done = `python ingestion/load_bigquery.py --dry-run` prints every `bq mk` / `bq load` / validation command and exits 0 with no credentials. Optional `--gcs-bucket` staging for the 574 MB order_products.csv.*
- [ ] **B4 [HUMAN]** Actually run the BigQuery load and `dbt build --target bigquery`. *done = Kartz reports PASS counts; numbers recorded here. Requires GCP credentials the agent must not use. **BigQuery SQL is written but has never been executed — do not claim it works until this passes.*** 

## C. Missing models (spec calls for them, repo lacks them)

- [x] **C1 [AGENT]** `dim_time` from `order_dow` + `order_hour_of_day`, with daypart and weekend flags. *done = built; **exactly 168 rows**, asserted by a singular test on row count / 7 distinct days / 24 distinct hours.*
- [x] **C2 [AGENT]** `mart_time_patterns` — order volume and reorder rate by day-of-week × hour. *done = **168 rows**; `sum(total_orders)` = **3,421,083** = `dim_orders` row count, asserted by a singular reconciliation test.*
- [x] **C3 [AGENT]** `mart_reorder_behavior` — department × aisle reorder rate vs department and platform benchmarks. *done = **134 rows**, one per aisle; all rates in [0,1] by range test.*
- [x] **C4 [AGENT]** Extend `schema.yml` coverage for C1–C3. *done = `dbt build --select dim_time mart_time_patterns mart_reorder_behavior` returned **`PASS=57 WARN=0 ERROR=0`** (3 models + 54 tests).*

## D. Orchestration + reproducibility (the "DE, not analyst" layer)

- [x] **D1 [AGENT]** `Dockerfile` for the Python/dbt runner. *done = file present with the build/run commands documented in its header. The `docker build` itself is D5 [HUMAN].*
- [x] **D2 [AGENT]** `.github/workflows/dbt_build.yml`. *done = valid YAML (verified by `yaml.safe_load`); weekly cron + manual dispatch + PR validation that uses `--empty` against a PR-scoped dataset so a PR never rebuilds 32M rows. Secrets named in the file header.*
- [x] **D3 [AGENT]** `.github/workflows/dbt_docs.yml` — `dbt docs generate --static` → GitHub Pages. *done = valid YAML; Pages source documented in the file header.*
- [ ] **D4 [HUMAN]** Add repo secrets (`GCP_SA_KEY`, `GCP_PROJECT`, `BQ_DATASET`, `BQ_RAW_DATASET`), set Pages source to GitHub Actions, confirm first green run. *done = green run badge.*
- [ ] **D5 [HUMAN]** `docker build -t instacart-platform .` *done = image builds; agent has no guarantee of a running daemon for a clean-room build.*

## E. BI deliverables

- [x] **E1 [AGENT]** Rewrite `bi/powerbi_dashboard_plan.md`. *done = 5 core pages + optional field-parameters page; the previously missing **Temporal Behavior** page is now fed by `mart_time_patterns`. Every visual names its exact mart column. The old plan's 7 `TODO: insert validated KPI value` placeholders are gone — cards now bind to measures instead of hard-coded numbers.*
- [x] **E2 [AGENT]** Add explicit **DAX measure definitions**. *done = 33 complete measures across 6 groups; the previous plan contained zero DAX.*
- [x] **E3 [AGENT]** Add **conditional-formatting rules** + field-parameters page. *done = 4 rule sets stated as field + rule type + thresholds + hex colours, including the diverging zero-centred scale on `reorder_rate_vs_department`.*
- [ ] **E4 [HUMAN]** Build the `.pbix`, take screenshots into `screenshots/`. *agent cannot render Power BI.*

## F. Documentation

- [x] **F1 [AGENT]** Update `bi/data_dictionary.md` for `dim_time`, `mart_time_patterns`, `mart_reorder_behavior`. *done = both new BI marts fully documented column-by-column, plus the aggregation warning against averaging rates, and `fact_order_items` marked do-not-import.*
- [x] **F2 [AGENT]** Add an ERD to `docs/erd.md`. *done = Mermaid `erDiagram` for the star schema + a full model-lineage flowchart matching the actual `ref()` graph, plus grain/key and materialization tables.*
- [x] **F3 [AGENT]** README: verified build section, orchestration + BigQuery sections, skills→usage map, Modules 5 and 6. *done = added the verified build table (`PASS=256`, 19 models, 237 tests, both cold and warm timings), Warehouse Targets, Orchestration, a 12-row skills→usage map, and 6 new Key Metrics lines. Every figure came from a query run this session.*
- [x] **F5 [AGENT]** Fill `analysis/recommendation_memo.md`, which still held 20 unfilled `TODO:` placeholders. *done = all 12 metric placeholders replaced with queried values, 5 findings sections written, 4 recommendations added, and the validation checklist marked against the actual run. Derived shares re-checked: the 4 segment counts sum exactly to 206,209.*
- [x] **F4 [AGENT]** Grounded resume bullets in `docs/resume_bullets.md`. *done = 7 bullets, each with a named source query, plus an explicit **"Not yet true"** table listing the 4 claims that must not be used until BigQuery / CI / Power BI actually run.*

## G. Ship

- [x] **G1 [AGENT]** Final full `dbt build` after all model changes. *done = **`PASS=256 WARN=0 ERROR=0 SKIP=0`**, 19 models + 237 data tests, 6m 52s.*
- [x] **G2 [AGENT]** Diff the rebuilt marts against the pre-rewrite snapshot. *done = **zero differences**. Executive KPIs, all 4 segment counts, the full 21-point retention curve, affinity pair count and max lift, and all 8 row counts are identical before vs after the cross-database rewrite. The migration is proved result-neutral, not assumed to be.*
- [ ] **G3 [HUMAN]** Push, pin the repo, update `kartz82.github.io` project entry if any figure changed.

## H. Findings raised during this loop

- [x] **H1 [RESOLVED]** The `Early Lifecycle` segment in `mart_customer_segments` matched **0 customers**. The cause was **not** branch ordering, as first suspected: the branch condition `total_orders <= 3` is unsatisfiable against this dataset, because every customer in the extract has between **4 and 100** orders (verified against the warehouse — 0 customers with <= 3 orders, 23,986 with exactly 4). Reordering the `CASE` was tested and changed nothing. Resolved by removing the dead branch rather than lowering the threshold, which would have manufactured a lifecycle stage the curated sample does not contain. Added `assert_customer_segments_cover_all_customers.sql` so an empty or unexpected segment fails the build. **Segment counts are unchanged** (High Engagement 28,883 / Loyal Routine 62,818 / At Risk 44,873 / Moderate Engagement 69,635), so nothing published on `kartz82.github.io` needed updating. Documented as Decision 8 in `docs/decisions.md`.

---

## I. Lakehouse layer — PySpark + Delta on Databricks (`spark/`)

- [x] **I1 [AGENT]** Port 5 marts + their silver dependencies to PySpark (`gold.py`, `silver.py`). *done = `test_equivalence.py`: all 5 gold marts and 3 silver tables match the dbt models built on DuckDB over a synthetic sample, row for row. Basket affinity rewritten as array pair generation instead of a self-join.*
- [x] **I2 [AGENT]** Bronze loader with explicit schemas, FAILFAST parsing, lineage columns. *done = `bronze.py`; quoted product names with embedded commas parse correctly in the sample.*
- [x] **I3 [AGENT]** Incremental MERGE design + tests. *done = `test_incremental.py`: 3 waves converge to the full-load state, silver and gold; a re-run wave is a no-op.*
- [x] **I4 [AGENT]** Quality gates, run log, OPTIMIZE/time-travel helpers, 6-stage pipeline, Job JSON, 3 notebooks. *done = `test_pipeline_local.py` runs all 6 stages end to end (Parquet); `test_invariants.py` proves the gate catches an injected orphan row.*
- [ ] **I5 [AGENT/CI]** `test_delta_incremental.py` green in GitHub Actions. *done = `spark_tests.yml` passes with `TEST_WITH_DELTA=1`. **Real Delta MERGE / OPTIMIZE / time travel have not been executed yet** — the dev environment could not download the Delta jars.*
- [ ] **I6 [HUMAN+AGENT]** Databricks Free Edition: Git folder, `setup`, upload CSVs to the volume, create the Job from `spark/databricks/instacart_lakehouse_job.json`, run `mode=full`. *done = Job run green; `instacart_ops.pipeline_runs` has a full-mode run.*
- [ ] **I7 [HUMAN]** Export dbt marts (`spark/scripts/export_dbt_marts.py`), upload to the volume, run `reconcile_with_dbt`. *done = 5 / 5 marts reconcile on the full dataset; paste the table into `spark/README.md`.*
- [ ] **I8 [HUMAN+AGENT]** Run incremental waves + `delta_features_demo`. *done = runtimes, MERGE counts, OPTIMIZE files before/after copied from the run log into `spark/README.md` (replacing every TODO there).*

## J. Orchestration — Airflow 3 on Astro (`airflow/`)

- [x] **J1 [AGENT]** `instacart_dbt_build`: `dbt_deps → dbt_run → dbt_test → Databricks`, test gate, retries with backoff, failure alerts. *done = DAG integrity tests pass on Airflow 3.3.2 (6 / 6), including the gate order and `dbt_test.retries == 0`; Databricks operator templates render (`job_id`, `wave`).*
- [x] **J2 [AGENT]** `instacart_lakehouse_incremental`: one wave per day, `depends_on_past`, backfill-ready. *done = wave mapping tested (day 1 → wave 0, day 10 → wave 9, out-of-range rejected).*
- [ ] **J3 [HUMAN]** `astro dev start`, trigger `instacart_dbt_build`. *done = green run (Databricks step skipped is expected until J4).*
- [ ] **J4 [HUMAN]** Databricks connection + `databricks_job_id` in `airflow/.env`; backfill 10 waves. *done = 10 green runs; screenshot of the grid.*
- [ ] **J5 [HUMAN]** Astronomer free workshop / Airflow fundamentals cert. *Course item; not code.*

## K. Azure design (concept only)

- [x] **K1 [AGENT]** `docs/azure_architecture.md`: ADLS Gen2 + ADF + Azure Databricks + Unity Catalog + Key Vault mapping, orchestration tradeoff, code deltas. *done = file exists and is labelled design-only.*
- [ ] **K2 [HUMAN]** Microsoft Applied Skills badge (if available). *Course item.*

## L. Findings raised during this loop

- [x] **L1 [RESOLVED]** `dim_time.time_key` was engine-dependent (`generate_series` returns DOUBLE on DuckDB). Fixed with integer casts; no-op on Postgres. Decision 9.
- [x] **L2 [RESOLVED]** `lift` ties at the 6th decimal round differently by engine. Reconciliation tolerance of one unit in the last place on `lift` only. Decision 10.
- [ ] **L3 [HUMAN]** Re-run the Postgres `dbt build` after the `dim_time` cast and `mart_basket_affinity` var changes. *done = `PASS=256` (or higher) again and marts identical to before. Both changes should be result-neutral on Postgres; this confirms it.*
