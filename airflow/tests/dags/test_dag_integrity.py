"""DAG integrity tests. Run locally with ``astro dev pytest`` (inside the Astro image),
or with plain pytest in any environment that has Airflow 3 and the Databricks provider.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pendulum
import pytest

AIRFLOW_HOME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AIRFLOW_HOME))  # `include` package
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")

from airflow.models import DagBag  # noqa: E402


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(AIRFLOW_HOME / "dags"))


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_expected_dags(dagbag):
    assert {"instacart_dbt_build", "instacart_lakehouse_incremental"} <= set(dagbag.dag_ids)


def test_dbt_test_gates_databricks(dagbag):
    dag = dagbag.dags["instacart_dbt_build"]
    order = ["dbt_deps", "dbt_run", "dbt_test", "databricks_configured", "databricks_full_refresh"]
    for upstream, downstream in zip(order, order[1:], strict=False):
        assert downstream in dag.get_task(upstream).downstream_task_ids, (upstream, downstream)
    assert dag.get_task("databricks_full_refresh").trigger_rule == "all_success"
    assert dag.get_task("dbt_test").retries == 0


def test_every_task_alerts_on_failure(dagbag):
    for dag_id in ("instacart_dbt_build", "instacart_lakehouse_incremental"):
        for t in dagbag.dags[dag_id].tasks:
            assert t.on_failure_callback, f"{dag_id}.{t.task_id} has no failure callback"


def test_incremental_runs_in_order(dagbag):
    dag = dagbag.dags["instacart_lakehouse_incremental"]
    assert dag.max_active_runs == 1
    assert all(t.depends_on_past for t in dag.tasks)


def test_wave_mapping():
    sys.path.insert(0, str(AIRFLOW_HOME / "dags"))
    from instacart_lakehouse_incremental import wave_for

    assert wave_for(pendulum.datetime(2026, 1, 1, tz="UTC"), None) == 0
    assert wave_for(pendulum.datetime(2026, 1, 10, 23, tz="UTC"), None) == 9
    assert wave_for(None, 4) == 4
    with pytest.raises(ValueError):
        wave_for(pendulum.datetime(2026, 1, 11, tz="UTC"), None)
    with pytest.raises(ValueError):
        wave_for(None, None)
