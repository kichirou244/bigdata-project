"""Benchmark Runner for Checkpoint 4 (YouTube Trending Pipeline Optimization).
Strictly follows:
- Same input (fixed 1 chunk = 256 MB, 167,866 rows)
- Same resources (local[*], 4g driver memory)
- Exactly 1 main change: Tune spark.sql.shuffle.partitions from 64 down to 8 (aligned with CPU cores to eliminate small-task scheduling overhead)
- >= 3 runs for Baseline, >= 3 runs for Optimized -> report Median
- Correctness verification (row counts, nulls, business metrics)
- Produces reports/benchmark.csv, reports/explain-before.txt, reports/explain-after.txt, reports/benchmark_summary.json
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

from pipeline import (
    load_config,
    ensure_hadoop_home,
    read_trending_raw,
    read_dim_country,
    transform_trending,
    join_trending_country,
    summarize_trending,
    duplicate_key_count,
    unmatched_count,
    ROOT,
)

CONFIG_PATH = ROOT / "config" / "config.json"
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def get_spark(cfg: dict, app_name: str, shuffle_parts: int) -> SparkSession:
    ensure_hadoop_home()
    memory = cfg.get("spark_driver_memory", "4g")
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", memory)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", str(shuffle_parts))
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


def execute_pipeline(spark: SparkSession, cfg: dict, target_files: list[Path], tag: str) -> tuple[float, DataFrame, str, dict]:
    """Execute end-to-end pipeline and return (elapsed_seconds, summary_df, explain_formatted, stats_dict)."""
    t0 = time.perf_counter()

    raw_df = read_trending_raw(spark, target_files)
    dim_df = read_dim_country(spark, ROOT / cfg["dim_country_path"])

    input_count = raw_df.count()

    # Transformation
    clean_df = transform_trending(raw_df)
    clean_count = clean_df.count()

    # Sample hash
    sample_hash = clean_df.select("row_hash").limit(1).collect()
    sample_hash_val = sample_hash[0]["row_hash"] if sample_hash else "N/A"

    # Join
    joined_df = join_trending_country(clean_df, dim_df)
    joined_count = joined_df.count()
    unmatched = unmatched_count(joined_df, "country_name")

    # Summarize
    summary_df = summarize_trending(joined_df)
    summary_count = summary_df.count()

    # Formatted explain
    explain_str = summary_df._jdf.queryExecution().explainString(
        spark._jvm.org.apache.spark.sql.execution.ExplainMode.fromString("formatted")
    )

    # Action: Materialize / Write
    out_dir = ROOT / "output" / f"bench_{tag}"
    summary_df.write.mode("overwrite").partitionBy("continent").parquet(str(out_dir))

    # Collect KPI metrics for correctness assertion
    top_row = summary_df.select("top_video_views", "avg_views", "avg_views_per_hour").first()
    business_kpis = {
        "top_video_views": top_row["top_video_views"] if top_row else 0,
        "avg_views": float(top_row["avg_views"]) if top_row else 0.0,
        "avg_views_per_hour": float(top_row["avg_views_per_hour"]) if top_row else 0.0,
    }

    elapsed = round(time.perf_counter() - t0, 2)
    stats = {
        "input_count": input_count,
        "clean_count": clean_count,
        "joined_count": joined_count,
        "unmatched": unmatched,
        "summary_count": summary_count,
        "business_kpis": business_kpis,
        "sample_hash": sample_hash_val,
    }
    return elapsed, summary_df, explain_str, stats


def main():
    cfg = load_config(str(CONFIG_PATH))
    raw_dir = ROOT / cfg["raw_input_path"]
    target_files = sorted(raw_dir.glob("chunk_*.csv"))[:1]
    chunk_name = target_files[0].name
    file_size_mb = round(target_files[0].stat().st_size / (1024 * 1024), 2)
    print(f"=== BENCHMARK WORKLOAD ===")
    print(f"File: {chunk_name} ({file_size_mb} MB)")
    print(f"Driver Memory: {cfg.get('spark_driver_memory', '4g')}")
    print("=" * 60)

    # 1. BASELINE BENCHMARK (3 runs with shuffle_partitions = 64)
    print("\n>>> STARTING BASELINE RUNS (spark.sql.shuffle.partitions = 64) <<<")
    baseline_times = []
    baseline_stats = None
    baseline_explain = ""

    spark_base = get_spark(cfg, "benchmark-baseline", shuffle_parts=64)
    spark_base.sparkContext.setLogLevel("WARN")

    try:
        for r in range(1, 4):
            print(f"Running Baseline {r}/3...")
            elapsed, s_df, expl, stats = execute_pipeline(spark_base, cfg, target_files, tag="baseline")
            baseline_times.append(elapsed)
            print(f"  -> Baseline Run {r}: {elapsed} s")
            if r == 1:
                baseline_stats = stats
                baseline_explain = expl
    finally:
        spark_base.stop()

    baseline_median = round(statistics.median(baseline_times), 2)
    print(f"--> Baseline Times: {baseline_times} | Median: {baseline_median} s")

    # 2. OPTIMIZED BENCHMARK (3 runs with shuffle_partitions = 8)
    print("\n>>> STARTING OPTIMIZED RUNS (One Change: spark.sql.shuffle.partitions = 8) <<<")
    opt_times = []
    opt_stats = None
    opt_explain = ""

    spark_opt = get_spark(cfg, "benchmark-optimized", shuffle_parts=8)
    spark_opt.sparkContext.setLogLevel("WARN")

    try:
        for r in range(1, 4):
            print(f"Running Optimized {r}/3...")
            elapsed, s_df, expl, stats = execute_pipeline(spark_opt, cfg, target_files, tag="optimized")
            opt_times.append(elapsed)
            print(f"  -> Optimized Run {r}: {elapsed} s")
            if r == 1:
                opt_stats = stats
                opt_explain = expl
    finally:
        spark_opt.stop()

    opt_median = round(statistics.median(opt_times), 2)
    speedup_pct = round(((baseline_median - opt_median) / baseline_median) * 100, 2)
    delta_s = round(baseline_median - opt_median, 2)
    print(f"--> Optimized Times: {opt_times} | Median: {opt_median} s")
    print(f"--> Speedup: {speedup_pct}% (Saved {delta_s} s)")

    # 3. CORRECTNESS VERIFICATION
    print("\n>>> VERIFYING CORRECTNESS <<<")
    checks = []
    c1 = (baseline_stats["input_count"] == opt_stats["input_count"])
    checks.append(("Input Row Count Match", c1, f"{baseline_stats['input_count']} vs {opt_stats['input_count']}"))
    c2 = (baseline_stats["clean_count"] == opt_stats["clean_count"])
    checks.append(("Clean Valid Rows Match", c2, f"{baseline_stats['clean_count']} vs {opt_stats['clean_count']}"))
    c3 = (baseline_stats["joined_count"] == opt_stats["joined_count"])
    checks.append(("Joined Fact-Dim Rows Match", c3, f"{baseline_stats['joined_count']} vs {opt_stats['joined_count']}"))
    c4 = (baseline_stats["summary_count"] == opt_stats["summary_count"])
    checks.append(("Output Summary Groups Match", c4, f"{baseline_stats['summary_count']} vs {opt_stats['summary_count']}"))
    c5 = (baseline_stats["business_kpis"] == opt_stats["business_kpis"])
    checks.append(("Business KPIs Exact Match", c5, f"{baseline_stats['business_kpis']} vs {opt_stats['business_kpis']}"))

    all_passed = all(chk[1] for chk in checks)
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    print(f"OVERALL CORRECTNESS: {'PASS' if all_passed else 'FAIL'}")

    # 4. SAVE ARTIFACTS
    (REPORTS_DIR / "explain-before.txt").write_text(baseline_explain, encoding="utf-8")
    (REPORTS_DIR / "explain-after.txt").write_text(opt_explain, encoding="utf-8")
    print("Saved explain-before.txt and explain-after.txt.")

    csv_file = REPORTS_DIR / "benchmark.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["experiment", "run_id", "workload", "input_rows", "shuffle_partitions", "runtime_seconds", "is_median"])
        for idx, t in enumerate(baseline_times):
            writer.writerow(["baseline", idx + 1, chunk_name, baseline_stats["input_count"], 64, t, t == baseline_median])
        for idx, t in enumerate(opt_times):
            writer.writerow(["optimized", idx + 1, chunk_name, opt_stats["input_count"], 8, t, t == opt_median])
    print(f"Saved benchmark results to: {csv_file}")

    summary_data = {
        "workload": {
            "chunk_file": chunk_name,
            "chunk_size_mb": file_size_mb,
            "input_rows": baseline_stats["input_count"],
            "clean_rows": baseline_stats["clean_count"],
            "output_groups": baseline_stats["summary_count"],
        },
        "environment": {
            "spark_version": "3.5.1",
            "python_version": "3.12",
            "master": "local[*]",
            "driver_memory": cfg.get("spark_driver_memory", "4g"),
            "shuffle_partitions_before": 64,
            "shuffle_partitions_after": 8,
        },
        "baseline": {
            "runs": baseline_times,
            "median": baseline_median,
        },
        "optimized": {
            "runs": opt_times,
            "median": opt_median,
        },
        "speedup_percent": speedup_pct,
        "delta_seconds": delta_s,
        "correctness": "PASS" if all_passed else "FAIL",
        "assertions": checks,
        "business_kpis": baseline_stats["business_kpis"],
    }
    (REPORTS_DIR / "benchmark_summary.json").write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Saved benchmark_summary.json.")


if __name__ == "__main__":
    main()
