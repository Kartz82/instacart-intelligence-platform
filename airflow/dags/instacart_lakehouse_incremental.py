"""Incremental lakehouse loads, one wave per day, built to be backfilled.

The Kaggle extract is static, so "new data" is simulated: wave N is the window of order
numbers [10N + 1, 10N + 10] for every customer (spark/instacart_spark/bronze.py). The
largest order_number in the dataset is 100, so waves 0-9 cover everything.

Each DAG run maps its logical date to a wave:

    2026-01-01 -> wave 0,  2026-01-02 -> wave 1,  ...,  2026-01-10 -> wave 9

and triggers the Databricks Job in incremental mode, which MERGEs that wave into bronze
and silver and rebuilds gold.

Backfill (loads all ten waves in order, one at a time):

    astro dev run backfill create --dag-id instacart_lakehouse_incremental \
        --from-date 2026-01-01 --to-date 2026-01-10

``depends_on_past`` and ``max_active_runs=1`` force the waves to land in order: wave 3
never MERGEs before wave 2 has succeeded. MERGE on natural keys makes a re-run of a
wave a no-op, so clearing and re-running any day is safe.

A manual run can target a specific wave with the ``wave`` param.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from airflow.sdk import DAG, Param, Variable, task
from include.alerts import on_failure, on_retry

FIRST_DAY = pendulum.datetime(2026, 1, 1, tz="UTC")
N_WAVES = 10

default_args = {
    "owner": "kartz",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "depends_on_past": True,
    "on_failure_callback": on_failure,
    "on_retry_callback": on_retry,
}


def wave_for(logical_date: pendulum.DateTime | None, override: int | None) -> int:
    """Wave number for a run: the explicit override, else days since FIRST_DAY."""
    if override is not None:
        wave = int(override)
    elif logical_date is None:
        raise ValueError("run has no logical date; trigger it with the `wave` param")
    else:
        wave = (pendulum.instance(logical_date).start_of("day") - FIRST_DAY).days
    if not 0 <= wave < N_WAVES:
        raise ValueError(f"wave {wave} is outside 0..{N_WAVES - 1}")
    return wave


with DAG(
    dag_id="instacart_lakehouse_incremental",
    description="One incremental Delta MERGE wave per day; backfill to load all waves",
    schedule="@daily",
    start_date=FIRST_DAY,
    end_date=FIRST_DAY.add(days=N_WAVES - 1),
    catchup=False,  # waves are loaded deliberately, by backfill, not on DAG unpause
    max_active_runs=1,
    default_args=default_args,
    params={"wave": Param(None, type=["null", "integer"], minimum=0, maximum=N_WAVES - 1)},
    tags=["instacart", "databricks", "incremental", "backfill"],
    doc_md=__doc__,
) as dag:

    @task
    def compute_wave(logical_date=None, params=None) -> int:
        wave = wave_for(logical_date, (params or {}).get("wave"))
        print(f"logical_date={logical_date} -> wave {wave}")
        return wave

    @task.short_circuit(ignore_downstream_trigger_rules=True)
    def databricks_configured() -> bool:
        return bool(Variable.get("databricks_job_id", default=None))

    run_wave = DatabricksRunNowOperator(
        task_id="merge_wave",
        databricks_conn_id="databricks_default",
        job_id="{{ var.value.databricks_job_id }}",
        job_parameters={
            "mode": "incremental",
            "wave": "{{ ti.xcom_pull(task_ids='compute_wave') }}",
        },
        deferrable=True,
        execution_timeout=timedelta(hours=2),
    )

    compute_wave() >> databricks_configured() >> run_wave
