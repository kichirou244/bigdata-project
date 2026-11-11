"""Quality Report Module for BigData Checkpoint 3."""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def null_counts(df: DataFrame, cols: list[str] | None = None) -> dict[str, int]:
    """Return null counts by column in a single Spark aggregation action."""
    target_cols = cols or df.columns
    exprs = [F.sum(F.when(F.col(c).isNull() | (F.trim(F.col(c).cast("string")) == ""), 1).otherwise(0)).alias(c) for c in target_cols]
    row = df.agg(*exprs).first()
    return row.asDict() if row else {}


def duplicate_key_count(df: DataFrame, key_cols: list[str] | str) -> int:
    """Count key combinations that occur more than once."""
    keys = [key_cols] if isinstance(key_cols, str) else key_cols
    return df.groupBy(*keys).count().filter(F.col("count") > 1).count()


def unmatched_count(joined_df: DataFrame, check_col: str) -> int:
    """Count records where right side of join is null (unmatched)."""
    return joined_df.filter(F.col(check_col).isNull()).count()


def build_quality_evidence(
    raw_df: DataFrame,
    clean_df: DataFrame,
    joined_df: DataFrame,
    dim_df: DataFrame,
    dim_key: str = "country_code",
    fact_key: str = "country",
) -> dict:
    """Generate comprehensive quality evidence dictionary."""
    total_raw = raw_df.count()
    total_clean = clean_df.count()
    total_joined = joined_df.count()

    dim_duplicates = duplicate_key_count(dim_df, dim_key)
    row_hash_duplicates = duplicate_key_count(clean_df, "row_hash")
    unmatched_dim = unmatched_count(joined_df, "country_name")

    crucial_cols = ["video_id", "country", "trending_dt", "views"]
    clean_nulls = null_counts(clean_df, [c for c in crucial_cols if c in clean_df.columns])

    return {
        "raw_rows": total_raw,
        "clean_rows": total_clean,
        "dropped_rows": total_raw - total_clean,
        "joined_rows": total_joined,
        "dim_duplicates": dim_duplicates,
        "row_hash_duplicates": row_hash_duplicates,
        "unmatched_dim_keys": unmatched_dim,
        "clean_null_counts": clean_nulls,
    }
