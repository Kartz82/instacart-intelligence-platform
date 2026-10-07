"""Weekly warehouse build: dbt run, then dbt test, then the Databricks lakehouse refresh.

    dbt_deps -> dbt_run -> dbt_test -> databricks_configured -> databricks_full_refresh

* ``dbt_test`` gates everything downstream. A failing test fails the task, and the
  default ``all_success`` trigger rule means the Databricks refresh never starts, so a
  broken warehouse is never propagated into the lakehouse.
* ``dbt run`` and ``dbt test`` are separate tasks (not one ``dbt build``) so the Airflow
  grid shows which half failed and either can be retried on its own.
* The Databricks step is skipped (not failed) until the ``databricks_job_id`` Variable
  is set, so the dbt half can be exercised on its own first.

Weekly because the source is a static Kaggle export; this matches
.github/workflows/dbt_build.yml.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Variable, task
from include.alerts import on_failure, on_retry

DBT = "/usr/local/airflow/dbt_venv/bin/dbt"
DBT_DIR = "/usr/local/airflow/include/dbt"  # synced from ../dbt by scripts/sync_dbt.sh
DBT_FLAGS = "--profiles-dir . --target dev --target-path /tmp/dbt_target --log-path /tmp/dbt_logs"

default_args = {
    "owner": "kartz",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=20),
    "on_failure_callback": on_failure,
    "on_retry_callback": on_retry,
}

with DAG(
    dag_id="instacart_dbt_build",
    description="dbt run -> dbt test (gate) -> Databricks lakehouse full refresh",
    schedule="0 6 * * 1",
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["instacart", "dbt", "databricks"],
    doc_md=__doc__,
) as dag:
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {DBT_DIR} && {DBT} deps {DBT_FLAGS}",
        execution_timeout=timedelta(minutes=10),
    )

    # A cold build of this project once took 3h 35m 53s (see TASKS.md); a warm rebuild 6m 52s.
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && {DBT} run {DBT_FLAGS}",
        execution_timeout=timedelta(hours=4),
        retries=1,  # a model failure is rarely transient; one retry covers connection blips
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && {DBT} test {DBT_FLAGS}",
        execution_timeout=timedelta(hours=1),
        retries=0,  # a failing data test is a real failure; retrying would only delay the alert
    )

    @task.short_circuit(task_id="databricks_configured", ignore_downstream_trigger_rules=True)
    def databricks_configured() -> bool:
        job_id = Variable.get("databricks_job_id", default=None)
        print(f"databricks_job_id = {job_id!r}")
        return bool(job_id)

    databricks_full_refresh = DatabricksRunNowOperator(
        task_id="databricks_full_refresh",
        databricks_conn_id="databricks_default",
        job_id="{{ var.value.databricks_job_id }}",
        job_parameters={"mode": "full", "wave": ""},
        deferrable=True,  # waits in the triggerer, not in a worker slot
        execution_timeout=timedelta(hours=4),
    )

    dbt_deps >> dbt_run >> dbt_test >> databricks_configured() >> databricks_full_refresh
