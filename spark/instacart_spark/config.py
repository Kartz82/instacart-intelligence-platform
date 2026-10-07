"""Runtime settings, read from environment variables so the same code runs locally and
on Databricks without edits. Job parameters on Databricks are passed as CLI arguments to
``jobs/run_stage.py``, which overrides these defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    # Unity Catalog catalog. None means "use the session's current catalog".
    # TODO: verify - on Databricks Free Edition the default catalog is usually `workspace`.
    catalog: str | None = os.getenv("LAKEHOUSE_CATALOG") or None

    bronze_schema: str = _env("BRONZE_SCHEMA", "instacart_bronze")
    silver_schema: str = _env("SILVER_SCHEMA", "instacart_silver")
    gold_schema: str = _env("GOLD_SCHEMA", "instacart_gold")
    ops_schema: str = _env("OPS_SCHEMA", "instacart_ops")

    # "delta" on Databricks. "parquet" is only a local fallback for machines where the
    # Delta jars cannot be downloaded; MERGE / OPTIMIZE / time travel need "delta".
    storage_format: str = _env("LAKEHOUSE_FORMAT", "delta")

    # Folder holding the Kaggle CSVs. Locally: data/raw. On Databricks: a Unity Catalog
    # volume path such as /Volumes/<catalog>/<schema>/<volume>/instacart
    raw_path: str = _env("RAW_DATA_PATH", "data/raw")

    # Basket-affinity eligibility thresholds. Defaults match the dbt vars and
    # docs/decisions.md section 3.
    min_product_orders: int = int(_env("MIN_PRODUCT_ORDERS", "1000"))
    min_pair_orders: int = int(_env("MIN_PAIR_ORDERS", "100"))

    # Incremental simulation: one "wave" is a window of `order_number` values, i.e. the
    # next batch of orders each customer places. See bronze.select_wave.
    wave_size: int = int(_env("WAVE_SIZE", "10"))

    def table(self, layer: str, name: str) -> str:
        """Fully-qualified table name for a layer: bronze | silver | gold | ops."""
        schema = {
            "bronze": self.bronze_schema,
            "silver": self.silver_schema,
            "gold": self.gold_schema,
            "ops": self.ops_schema,
        }[layer]
        parts = [self.catalog, schema, name] if self.catalog else [schema, name]
        return ".".join(parts)

    def schema_names(self) -> list[str]:
        names = [self.bronze_schema, self.silver_schema, self.gold_schema, self.ops_schema]
        return [f"{self.catalog}.{n}" if self.catalog else n for n in names]

    def with_overrides(self, **kwargs) -> "Settings":
        return replace(self, **{k: v for k, v in kwargs.items() if v is not None})
