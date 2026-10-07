"""Command-line entry point for one pipeline stage.

Locally (full mode works without Delta by using Parquet tables):

    LAKEHOUSE_FORMAT=parquet python spark/jobs/run_stage.py --stage setup
    LAKEHOUSE_FORMAT=parquet python spark/jobs/run_stage.py --stage bronze --raw-path data/raw
    ...

On Databricks the job calls the notebook ``spark/notebooks/run_stage.py``, which
forwards its widgets to the same ``pipeline.run_stage`` function.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instacart_spark.config import Settings  # noqa: E402
from instacart_spark.pipeline import MODES, STAGES, run_stage  # noqa: E402
from instacart_spark.session import get_spark  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--stage", choices=STAGES, required=True)
    p.add_argument("--mode", choices=MODES, default="full")
    p.add_argument("--wave", type=int)
    p.add_argument("--run-id")
    p.add_argument("--catalog")
    p.add_argument("--raw-path")
    p.add_argument("--format", dest="storage_format", choices=["delta", "parquet"])
    p.add_argument("--min-product-orders", type=int)
    p.add_argument("--min-pair-orders", type=int)
    p.add_argument("--wave-size", type=int)
    a = p.parse_args(argv)

    settings = Settings().with_overrides(
        catalog=a.catalog,
        raw_path=a.raw_path,
        storage_format=a.storage_format,
        min_product_orders=a.min_product_orders,
        min_pair_orders=a.min_pair_orders,
        wave_size=a.wave_size,
    )
    spark = get_spark(delta=settings.storage_format == "delta")
    run_stage(spark, a.stage, settings, mode=a.mode, wave=a.wave, run_id=a.run_id)


if __name__ == "__main__":
    main()
