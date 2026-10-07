"""Reconcile Spark-built marts against dbt-built marts.

Two modes share one comparison function:

* tests: Spark output vs dbt-on-DuckDB output over the synthetic sample (exact match).
* real data: Spark gold tables on Databricks vs the dbt marts exported from Postgres by
  ``spark/scripts/export_dbt_marts.py``. Writes a Markdown report with the per-mart
  result, which is the evidence behind any "reconciled to dbt" claim.

A mart reconciles when it has the same key set and every column matches: exact for
integers and strings, within ``abs_tol`` for decimals and floats (dbt and Spark both
round to the same scale, so the default tolerance is far below the last kept digit).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .gold import GOLD_KEYS

# Per-column tolerances that override abs_tol. `lift` is computed in SQL as two nested
# decimal divisions, so a value that is an exact tie at the 6th decimal (for example
# 25305 / 13440 = 1.8828125) rounds up or down depending on the engine's intermediate
# decimal scale. One unit in the last kept place is therefore the honest tolerance;
# anything larger is a real mismatch.
COLUMN_TOLERANCES: dict[str, float] = {"lift": 1.0000001e-6}


@dataclass
class MartResult:
    mart: str
    rows_spark: int
    rows_dbt: int
    missing_in_spark: int = 0
    extra_in_spark: int = 0
    mismatched_columns: dict[str, int] = field(default_factory=dict)
    max_abs_diff: dict[str, float] = field(default_factory=dict)
    column_set_diff: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.rows_spark == self.rows_dbt
            and self.missing_in_spark == 0
            and self.extra_in_spark == 0
            and not self.mismatched_columns
            and not self.column_set_diff
        )


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            # Decimal objects -> float for comparison; strings stay strings.
            sample = out[col].dropna()
            if not sample.empty and not isinstance(sample.iloc[0], str):
                try:
                    out[col] = pd.to_numeric(out[col])
                except (TypeError, ValueError):
                    pass
        if pd.api.types.is_bool_dtype(out[col]):
            out[col] = out[col].astype("Int64")
    return out


def compare_frames(
    mart: str, spark_df: pd.DataFrame, dbt_df: pd.DataFrame, keys: list[str], abs_tol: float = 1e-9
) -> MartResult:
    spark_df = _normalise(spark_df)
    dbt_df = _normalise(dbt_df)
    result = MartResult(mart, len(spark_df), len(dbt_df))

    s_cols, d_cols = set(spark_df.columns), set(dbt_df.columns)
    if s_cols != d_cols:
        result.column_set_diff = (
            f"only in spark: {sorted(s_cols - d_cols)}; only in dbt: {sorted(d_cols - s_cols)}"
        )
    common = [c for c in dbt_df.columns if c in s_cols]

    merged = spark_df[common].merge(
        dbt_df[common], on=keys, how="outer", suffixes=("_spark", "_dbt"), indicator=True
    )
    result.missing_in_spark = int((merged["_merge"] == "right_only").sum())
    result.extra_in_spark = int((merged["_merge"] == "left_only").sum())
    both = merged[merged["_merge"] == "both"]

    for col in common:
        if col in keys:
            continue
        a, b = both[f"{col}_spark"], both[f"{col}_dbt"]
        null_mismatch = a.isna() != b.isna()
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            diff = (a.astype(float) - b.astype(float)).abs()
            value_mismatch = diff.fillna(0) > COLUMN_TOLERANCES.get(col, abs_tol)
            if diff.notna().any():
                result.max_abs_diff[col] = float(diff.max())
        else:
            value_mismatch = (a.astype(str) != b.astype(str)) & a.notna() & b.notna()
        bad = int((null_mismatch | value_mismatch).sum())
        if bad:
            result.mismatched_columns[col] = bad
    return result


def to_markdown(results: list[MartResult], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "| Mart | Spark rows | dbt rows | Missing | Extra | Mismatched columns | Result |",
        "| :--- | ---: | ---: | ---: | ---: | :--- | :--- |",
    ]
    for r in results:
        mism = ", ".join(f"{k} ({v})" for k, v in r.mismatched_columns.items()) or "none"
        if r.column_set_diff:
            mism += f"; {r.column_set_diff}"
        lines.append(
            f"| `{r.mart}` | {r.rows_spark:,} | {r.rows_dbt:,} | {r.missing_in_spark:,} | "
            f"{r.extra_in_spark:,} | {mism} | {'PASS' if r.ok else 'FAIL'} |"
        )
    passed = sum(r.ok for r in results)
    lines += ["", f"**{passed} / {len(results)} marts reconcile.**", ""]
    return "\n".join(lines)


def reconcile_all(
    spark_marts: dict[str, pd.DataFrame], dbt_marts: dict[str, pd.DataFrame], abs_tol: float = 1e-9
) -> list[MartResult]:
    return [
        compare_frames(name, spark_marts[name], dbt_marts[name], GOLD_KEYS[name], abs_tol)
        for name in GOLD_KEYS
        if name in spark_marts and name in dbt_marts
    ]
