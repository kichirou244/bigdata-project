"""Spark Processing Pipeline for BigData Checkpoint 3 (YouTube Trending Analytics).
End-to-End Pipeline: Raw -> Read/Schema -> Transform -> Join -> Quality -> Aggregate -> Output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    DoubleType,
    DateType,
    TimestampType,
)

from quality_report import (
    null_counts,
    duplicate_key_count,
    unmatched_count,
    build_quality_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "logs" / "pipeline.log"

SRC_MAP = {
    "country": "country",
    "channel_name": "channel_title",
    "snapshot_date": "trending_date",
    "video_tags": "tags",
    "view_count": "views",
    "like_count": "likes",
    "thumbnail_url": "thumbnail_link",
    "publish_date": "publish_time",
}

EMOJI_RE = (
    r"[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE00}-\x{FE0F}"
    r"\x{200B}-\x{200F}\x{2028}-\x{202F}\x{0000}-\x{001F}]"
)


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def ensure_hadoop_home() -> None:
    winutils = ROOT / "hadoop" / "bin"
    if os.name != "nt" or not (winutils / "winutils.exe").exists():
        return
    os.environ["HADOOP_HOME"] = str(ROOT / "hadoop")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(str(winutils))
        except OSError:
            pass
    cur_path = os.environ.get("PATH", "")
    if str(winutils) not in cur_path.split(os.pathsep):
        os.environ["PATH"] = str(winutils) + os.pathsep + cur_path


def load_config(path: str) -> dict:
    cfg_path = Path(path)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_spark(cfg: dict) -> SparkSession:
    ensure_hadoop_home()
    memory = cfg.get("spark_driver_memory", "4g")
    shuffle_parts = cfg.get("shuffle_partitions", "64")
    return (
        SparkSession.builder
        .appName("checkpoint3-youtube-trending-pipeline")
        .master("local[*]")
        .config("spark.driver.memory", memory)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", shuffle_parts)
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


def read_trending_raw(spark: SparkSession, input_path: Path | list[Path]) -> DataFrame:
    """Read raw trending data with fallback schema handling."""
    if isinstance(input_path, list):
        file_targets = [str(p) for p in input_path]
    elif input_path.is_file():
        file_targets = [str(input_path)]
    elif input_path.is_dir():
        file_targets = [str(p) for p in sorted(input_path.glob("*.csv"))]
    else:
        file_targets = [str(input_path)]

    df = (
        spark.read.option("header", True)
        .option("encoding", "UTF-8")
        .option("multiLine", "false")
        .csv(file_targets)
    )
    # Standardize column names
    clean_cols = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.toDF(*clean_cols)
    for src, dst in SRC_MAP.items():
        if src in df.columns and dst not in df.columns:
            df = df.withColumnRenamed(src, dst)
    return df


def read_dim_country(spark: SparkSession, dim_path: Path) -> DataFrame:
    schema = StructType([
        StructField("country_code", StringType(), False),
        StructField("country_name", StringType(), False),
        StructField("continent", StringType(), False),
        StructField("sub_region", StringType(), True),
        StructField("market_tier", StringType(), True),
    ])
    return spark.read.schema(schema).option("header", True).csv(str(dim_path))


def transform_trending(raw: DataFrame) -> DataFrame:
    """
    Apply >= 3 transformations with clear business logic:
    1. Clean & Parse: Parse trending_dt & publish_dt; clean emojis in text; standardize country code.
    2. Filter: Remove invalid / negative views, missing video_id, null dates.
    3. Row Hashing & Feature Derivation:
       - row_hash: Per-row SHA-256 directly in Spark (Thầy nhận xét)
       - views_per_hour: Window calculation delta_views / delta_hours
       - year_month & publish_hour
    """
    df = raw.withColumn(
        "trending_dt",
        F.coalesce(
            F.to_date("trending_date", "yyyy-MM-dd"),
            F.to_date(
                F.regexp_extract("trending_date", r"^(\d{2}\.\d{2}\.\d{2})", 1), "yy.dd.MM"
            ),
        ),
    ).withColumn(
        "publish_dt",
        F.coalesce(
            F.to_timestamp("publish_time", "yyyy-MM-dd HH:mm:ssXXX"),
            F.to_timestamp("publish_time", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"),
            F.to_timestamp("publish_time", "yyyy-MM-dd'T'HH:mm:ssXXX"),
            F.to_timestamp("publish_time", "yyyy-MM-dd HH:mm:ss"),
            F.to_timestamp("publish_time", "yyyy-MM-dd'T'HH:mm:ss"),
            F.to_timestamp(F.to_date("publish_time")),
        ),
    )

    # Cast numeric columns
    for col in ["views", "likes", "comment_count"]:
        if col in df.columns:
            df = df.withColumn(col, F.expr(f"try_cast({col} AS BIGINT)"))
        else:
            df = df.withColumn(col, F.lit(0).cast(LongType()))
    df = df.fillna({"likes": 0, "comment_count": 0, "views": 0})

    # Standardize country
    if "country" in df.columns:
        df = df.withColumn("country", F.upper(F.trim(F.col("country"))))
    else:
        df = df.withColumn("country", F.lit("UNKNOWN"))

    # Clean text columns
    for col in ["title", "channel_title"]:
        if col in df.columns:
            cleaned = F.regexp_replace(F.col(col), EMOJI_RE, "")
            cleaned = F.regexp_replace(cleaned, r"\s{2,}", " ")
            df = df.withColumn(col, F.trim(cleaned))
        else:
            df = df.withColumn(col, F.lit("Unknown"))

    # Filter invalid records (Quality Rule)
    valid_df = df.filter(
        F.col("video_id").isNotNull()
        & (F.trim(F.col("video_id")) != "")
        & F.col("views").isNotNull()
        & (F.col("views") >= 0)
        & F.col("trending_dt").isNotNull()
        & F.col("country").isNotNull()
        & (F.col("country") != "")
    )

    # Row Hashing: SHA-256 for each record (thực hiện nhận xét của GV)
    hash_expr = F.sha2(
        F.concat_ws(
            "||",
            F.coalesce(F.col("video_id"), F.lit("")),
            F.coalesce(F.col("country"), F.lit("")),
            F.coalesce(F.col("trending_dt").cast("string"), F.lit("")),
            F.coalesce(F.col("views").cast("string"), F.lit("0")),
            F.coalesce(F.col("likes").cast("string"), F.lit("0")),
            F.coalesce(F.col("comment_count").cast("string"), F.lit("0")),
        ),
        256,
    )
    with_hash = valid_df.withColumn("row_hash", hash_expr)

    # Deduplicate snapshot by (video_id, country, trending_dt)
    dedup = with_hash.dropDuplicates(["video_id", "country", "trending_dt"])

    # Window calculations for views_per_hour
    w = Window.partitionBy("video_id", "country").orderBy("trending_dt")
    return (
        dedup.withColumn("prev_views", F.lag("views").over(w))
        .withColumn("prev_dt", F.lag("trending_dt").over(w))
        .withColumn("delta_views", F.col("views") - F.col("prev_views"))
        .withColumn(
            "delta_hours",
            (F.unix_timestamp("trending_dt") - F.unix_timestamp("prev_dt")) / 3600.0,
        )
        .withColumn(
            "views_per_hour",
            F.when(F.col("delta_hours") > 0, F.round(F.col("delta_views") / F.col("delta_hours"), 2))
            .otherwise(None),
        )
        .withColumn("year_month", F.date_format("trending_dt", "yyyy-MM"))
        .withColumn("publish_hour", F.hour("publish_dt"))
    )


def join_trending_country(fact_df: DataFrame, dim_country_df: DataFrame) -> DataFrame:
    """Join Fact with Dimension Country (Left Join on country == country_code)."""
    return fact_df.join(
        dim_country_df,
        fact_df.country == dim_country_df.country_code,
        "left",
    )


def summarize_trending(joined: DataFrame) -> DataFrame:
    """
    Aggregate KPI trả lời câu hỏi Đồ án 1:
    - Group grain: continent, country_name, year_month
    - Metrics: total_videos, total_views, avg_views, avg_likes, avg_views_per_hour, peak_views_per_hour
    """
    return (
        joined
        .filter(F.col("country_name").isNotNull())
        .groupBy("continent", "country_name", "country", "year_month")
        .agg(
            F.countDistinct("video_id").alias("unique_videos"),
            F.count(F.lit(1)).alias("total_snapshots"),
            F.max("views").alias("top_video_views"),
            F.round(F.avg("views"), 2).alias("avg_views"),
            F.round(F.avg("likes"), 2).alias("avg_likes"),
            F.round(F.avg("views_per_hour"), 2).alias("avg_views_per_hour"),
            F.round(F.max("views_per_hour"), 2).alias("peak_views_per_hour"),
        )
        .orderBy(F.desc("avg_views_per_hour"), F.desc("top_video_views"))
    )


def run_pipeline(config_path: str, limit_files: int | None = None) -> dict:
    cfg = load_config(config_path)
    spark = build_spark(cfg)
    spark.sparkContext.setLogLevel("WARN")

    t0 = time.perf_counter()
    metrics: dict = {}

    try:
        raw_input = Path(cfg["raw_input_path"])
        if not raw_input.is_absolute():
            raw_input = ROOT / raw_input

        dim_path = Path(cfg["dim_country_path"])
        if not dim_path.is_absolute():
            dim_path = ROOT / dim_path

        out_summary = Path(cfg["output_summary_path"])
        if not out_summary.is_absolute():
            out_summary = ROOT / out_summary

        preview_csv = Path(cfg["preview_path"])
        if not preview_csv.is_absolute():
            preview_csv = ROOT / preview_csv

        evidence_dir = Path(cfg.get("evidence_dir", "evidence"))
        if not evidence_dir.is_absolute():
            evidence_dir = ROOT / evidence_dir
        evidence_dir.mkdir(parents=True, exist_ok=True)

        log("=" * 60)
        log("CHECKPOINT 3: SPARK PROCESSING PIPELINE")
        log(f"Raw Input:  {raw_input}")
        log(f"Dimension:  {dim_path}")
        log(f"Output:     {out_summary}")
        log("=" * 60)

        # 1. Read Raw & Dimension
        if limit_files and raw_input.is_dir():
            target_files = sorted(raw_input.glob("chunk_*.csv"))[:limit_files]
            log(f"Running sample mode: {len(target_files)} chunks")
            raw_df = read_trending_raw(spark, target_files)
        else:
            raw_df = read_trending_raw(spark, raw_input)

        dim_df = read_dim_country(spark, dim_path)

        input_rows = raw_df.count()
        dim_rows = dim_df.count()
        log(f"[INPUT] fact_rows={input_rows:,} | dim_countries={dim_rows:,}")

        # 2. Transformations
        clean_df = transform_trending(raw_df)
        clean_rows = clean_df.count()
        dropped = input_rows - clean_rows
        log(f"[CLEAN] valid_rows={clean_rows:,} | dropped_rows={dropped:,} ({(dropped/input_rows*100 if input_rows else 0):.2f}%)")

        # Row hashing stats
        sample_hash = clean_df.select("row_hash").limit(1).collect()
        sample_hash_val = sample_hash[0]["row_hash"] if sample_hash else "N/A"
        log(f"[ROW_HASH] Strategy=sha256_per_record | Sample={sample_hash_val[:16]}...")

        # 3. Join Fact + Dimension
        dim_dup_count = duplicate_key_count(dim_df, "country_code")
        joined_df = join_trending_country(clean_df, dim_df)
        joined_rows = joined_df.count()
        unmatched = unmatched_count(joined_df, "country_name")
        log(f"[JOIN] joined_rows={joined_rows:,} | dim_unique_check={dim_dup_count==0} | unmatched={unmatched}")

        # 4. Aggregation & Business KPI
        summary_df = summarize_trending(joined_df)
        summary_groups = summary_df.count()
        log(f"[AGG] KPI output groups={summary_groups:,}")

        # 5. Capture Explain Plan
        explain_file = evidence_dir / "explain_plan.txt"
        with explain_file.open("w", encoding="utf-8") as ef:
            plan_str = summary_df._jdf.queryExecution().explainString(
                spark._jvm.org.apache.spark.sql.execution.ExplainMode.fromString("formatted")
            )
            ef.write(plan_str)
        log(f"[PLAN] Formatted explain plan written to: {explain_file}")

        # 6. Write Output
        out_summary.parent.mkdir(parents=True, exist_ok=True)
        (
            summary_df.write.mode("overwrite")
            .partitionBy("continent")
            .parquet(str(out_summary))
        )
        (
            summary_df.limit(50).coalesce(1)
            .write.mode("overwrite")
            .option("header", True)
            .csv(str(preview_csv))
        )
        log(f"[WRITE] Parquet saved: {out_summary}")
        log(f"[WRITE] CSV preview saved: {preview_csv}")

        # 7. Collect Execution Metrics
        elapsed = round(time.perf_counter() - t0, 2)
        metrics = {
            "dataset": "youtube_trending",
            "checkpoint": "checkpoint-3",
            "runtime_seconds": elapsed,
            "input_rows": input_rows,
            "clean_rows": clean_rows,
            "dropped_rows": dropped,
            "joined_rows": joined_rows,
            "unmatched_rows": unmatched,
            "output_groups": summary_groups,
            "dim_unique": dim_dup_count == 0,
            "sample_row_hash": sample_hash_val,
            "partitions": summary_df.rdd.getNumPartitions(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        metrics_file = evidence_dir / "execution_metrics.json"
        metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"[BASELINE] Runtime: {elapsed} s | Metrics: {metrics_file}")

        print("\n" + "=" * 60)
        print("SAMPLE TOP OUTPUT (Preview):")
        print("=" * 60)
        summary_df.select("continent", "country_name", "year_month", "unique_videos", "avg_views_per_hour").show(10, truncate=False)

        return metrics
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Spark Processing Pipeline - Checkpoint 3")
    parser.add_argument("--config", default="config/config.json")
    parser.add_argument("--limit-chunks", type=int, default=None, help="Run on subset of chunks for fast test")
    args = parser.parse_args()
    run_pipeline(args.config, limit_files=args.limit_chunks)


if __name__ == "__main__":
    main()
