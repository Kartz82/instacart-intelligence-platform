# Orchestration — Apache Airflow 3 on Astro CLI

Two DAGs, run locally in Docker with the Astro CLI (Astro Runtime 3.3-8 = Airflow 3.3.2).

| DAG | Schedule | Flow |
| :--- | :--- | :--- |
| `instacart_dbt_build` | Mondays 06:00 UTC | `dbt_deps → dbt_run → dbt_test → databricks_configured → databricks_full_refresh` |
| `instacart_lakehouse_incremental` | Daily, 2026-01-01 → 2026-01-10, **for backfill** | `compute_wave → databricks_configured → merge_wave` |

**What makes it production-shaped**

- **Test gate.** `dbt_test` blocks the Databricks refresh: a failing data test fails the
  task and nothing downstream starts. `dbt_test` has `retries=0` (a failing test is a
  real failure); `dbt_run` has one retry for connection blips.
- **Retries with exponential backoff** on every task, and **alerts**: a failure callback
  on every task logs and, if `alert_webhook_url` is set, posts to a Slack-style webhook
  (`include/alerts.py`).
- **Deferrable Databricks operator.** `DatabricksRunNowOperator(deferrable=True)` waits
  for the Job in the triggerer, not in a worker slot.
- **Backfill.** Each day of the incremental DAG maps to one wave (2026-01-01 → wave 0 …
  2026-01-10 → wave 9). `depends_on_past=True` + `max_active_runs=1` force waves to land
  in order; Delta MERGE on natural keys makes any re-run safe.
- **Safe first run.** Until the `databricks_job_id` Variable is set, the Databricks steps
  are *skipped*, not failed — so the dbt half can be proven on its own first.
- **DAG integrity tests** (`tests/dags/`) run in CI against Airflow 3.3.2.

---

## Run it

Prerequisites: Docker Desktop running, Astro CLI (`brew install astro`), and the
Postgres warehouse up (`docker compose up -d` in the repo root).

```bash
cd airflow
cp .env.example .env          # Postgres settings already point at host.docker.internal:5434
./scripts/sync_dbt.sh         # copies ../dbt into include/dbt (re-run after dbt changes)
astro dev start               # builds the image; Airflow UI at http://localhost:8080
```

1. In the UI, unpause **`instacart_dbt_build`** and trigger it. `databricks_full_refresh`
   shows as *skipped* until step 2.
2. Connect Databricks — on your machine only, never committed:
   - add `AIRFLOW_VAR_DATABRICKS_JOB_ID=<job id>` and the
     `AIRFLOW_CONN_DATABRICKS_DEFAULT=...` line to `airflow/.env` (template in `.env.example`;
     the token is a Databricks personal access token), then `astro dev restart`.
3. Backfill the incremental waves:

   ```bash
   astro dev run backfill create --dag-id instacart_lakehouse_incremental \
       --from-date 2026-01-01 --to-date 2026-01-10
   ```

4. Run the DAG tests inside the image: `astro dev pytest`.

Stop with `astro dev stop`; remove everything with `astro dev kill`.

### Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `dbt_run` can't connect to Postgres | `docker ps` should show `instacart_postgres`; `.env` must have `POSTGRES_HOST=host.docker.internal` |
| `dbt_run` takes hours | A cold build has taken 3h 35m 53s before (most likely missing planner statistics; unconfirmed). Try `ANALYZE;` in Postgres first, or let it finish once — the warm rebuild took 6m 52s |
| `include/dbt` missing / stale | Re-run `./scripts/sync_dbt.sh` |
| Port 8080 busy | `astro config set webserver.port 8081` |

## Measured results

| Measurement | Value |
| :--- | :--- |
| `instacart_dbt_build` green end to end | TODO: verify (screenshot of the grid view) |
| `dbt_run` / `dbt_test` task durations | TODO: verify (task duration in the Airflow UI) |
| 10-wave backfill completed | TODO: verify (all 10 `instacart_lakehouse_incremental` runs green) |
