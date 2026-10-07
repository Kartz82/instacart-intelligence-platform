"""Shared fixtures.

The equivalence tests need two things that are slow to produce, so both are session
scoped: a Spark session, and the dbt-on-DuckDB reference marts for the synthetic sample.

The reference marts are built by ``dbt_oracle.py`` when ``DBT_ORACLE_PROJECT_DIR`` points
at a dbt project whose ``dbt_packages`` is installed; if it is unset the equivalence tests
are skipped (the pure-Spark tests still run).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # make `instacart_spark` importable
sys.path.insert(0, str(HERE))

from make_sample_data import generate  # noqa: E402

# Thresholds shrunk to fit a 300-user sample. Passed to BOTH dbt and Spark.
SAMPLE_VARS = {"min_product_orders": 20, "min_pair_orders": 5}


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("sample")
    generate(out, users=300, seed=7)
    return out


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    from instacart_spark.session import get_spark

    os.environ["SPARK_WAREHOUSE_DIR"] = str(tmp_path_factory.mktemp("warehouse"))

    session = get_spark("instacart-tests", delta=os.getenv("TEST_WITH_DELTA") == "1")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def dbt_marts(sample_dir, tmp_path_factory) -> dict[str, pd.DataFrame]:
    project = os.getenv("DBT_ORACLE_PROJECT_DIR")
    if not project:
        pytest.skip("DBT_ORACLE_PROJECT_DIR not set; skipping dbt equivalence tests")
    out = tmp_path_factory.mktemp("oracle")
    dbt_bin = os.getenv("DBT_BIN") or shutil.which("dbt") or "dbt"
    subprocess.run(
        [
            sys.executable, str(HERE / "dbt_oracle.py"),
            "--csv-dir", str(sample_dir),
            "--out-dir", str(out),
            "--project-dir", project,
            "--dbt-bin", dbt_bin,
            "--vars", json.dumps(SAMPLE_VARS),
        ],
        check=True,
    )
    return {p.stem: pd.read_parquet(p) for p in out.glob("*.parquet")}
