"""P3: Spark transform CSV -> Parquet phân vùng (FR1–FR4)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

from split_csv import split_file

ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "logs" / "transform.log"

CANON = [
    "video_id", "trending_date", "title", "channel_title", "category_id",
    "publish_time", "tags", "views", "likes", "dislikes", "comment_count",
    "thumbnail_link", "comments_disabled", "ratings_disabled",
    "video_error_or_removed", "description",
]
DROP_COLS = [
    "description", "tags", "thumbnail_link",
    "comments_disabled", "ratings_disabled", "video_error_or_removed",
]
SRC_MAP = {
    "country": "region",
    "channel_name": "channel_title",
    "snapshot_date": "trending_date",
    "video_tags": "tags",
    "view_count": "views",
    "like_count": "likes",
    "thumbnail_url": "thumbnail_link",
    "publish_date": "publish_time",
}
REGION_RE = re.compile(r"^([A-Z]{2})videos\.csv$", re.I)
BIG_FILE_BYTES = 64 * 1024 * 1024
CHUNK_MB = 256
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
    os.environ.setdefault("HADOOP_HOME", str(ROOT / "hadoop"))
    os.add_dll_directory(str(winutils))
    if str(winutils) not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = str(winutils) + os.pathsep + os.environ.get("PATH", "")


def latest_raw_with_csv(raw_root: Path, dataset: str) -> Path:
    runs = sorted(
        (raw_root / dataset).glob("ingest_date=*/run_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for run in runs:
        if any(run.glob("*.csv")):
            return run
    raise SystemExit(f"Không tìm thấy run raw có CSV trong {raw_root / dataset}")


def prepare_inputs(input_path: Path) -> list[tuple[list[Path], bool]]:
    if input_path.is_file():
        candidates = [input_path]
    elif (input_path / "split_manifest.json").exists():
        return [(sorted(input_path.glob("*.csv")), True)]
    else:
        candidates = sorted(input_path.glob("*.csv"))
    if not candidates:
        raise SystemExit(f"Không tìm thấy CSV trong: {input_path}")

    small: list[Path] = []
    entries: list[tuple[list[Path], bool]] = []
    for file in candidates:
        if file.stat().st_size < BIG_FILE_BYTES:
            small.append(file)
            continue
        out_dir = ROOT / "data" / "work" / "split" / file.stem
        if not (out_dir / "split_manifest.json").exists():
            log(f"auto-split | {file.name} ({file.stat().st_size:,} bytes) -> {out_dir}")
            split_file(file, out_dir, CHUNK_MB)
        entries.append((sorted(out_dir.glob("*.csv")), True))
    if small:
        entries.append((small, False))
    return entries


def read_raw(spark, entries: list[tuple[list[Path], bool]]):
    keep = [c for c in CANON if c not in DROP_COLS] + ["region"]
    frames = []
    for files, normalized in entries:
        for file in files:
            df = (
                spark.read.option("header", True)
                .option("encoding", "UTF-8")
                .option("multiLine", "false" if normalized else "true")
                .csv(str(file))
            )
            df = df.toDF(*[c.strip().lower().replace(" ", "_") for c in df.columns])
            for src, dst in SRC_MAP.items():
                if src in df.columns and dst not in df.columns:
                    df = df.withColumnRenamed(src, dst)
            if "region" not in df.columns:
                match = REGION_RE.match(file.name)
                df = df.withColumn(
                    "region", F.lit(match.group(1).upper() if match else "UNKNOWN")
                )
            for col in keep:
                if col not in df.columns:
                    df = df.withColumn(col, F.lit(None).cast("string"))
            frames.append(df.select(keep))
    out = frames[0]
    for df in frames[1:]:
        out = out.unionByName(df)
    return out


def rows_in_from_split_manifests(entries: list[tuple[list[Path], bool]]) -> int | None:
    total = 0
    for files, normalized in entries:
        if not normalized or not files:
            return None
        manifest = files[0].parent / "split_manifest.json"
        if not manifest.exists():
            return None
        total += json.loads(manifest.read_text(encoding="utf-8"))["records"]
    return total


def clean(df):
    df = df.withColumn(
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
    df = df.dropDuplicates(["video_id", "region", "trending_dt"])
    for col in ["category_id", "views", "likes", "dislikes", "comment_count"]:
        df = df.withColumn(col, F.expr(f"try_cast({col} AS BIGINT)"))
    df = df.fillna({"likes": 0, "dislikes": 0, "comment_count": 0})
    for col in ["title", "channel_title"]:
        cleaned = F.regexp_replace(F.col(col), EMOJI_RE, "")
        cleaned = F.regexp_replace(cleaned, r"\s{2,}", " ")
        df = df.withColumn(col, F.trim(cleaned))
    return df.filter(
        F.col("video_id").isNotNull()
        & (F.trim(F.col("video_id")) != "")
        & F.col("views").isNotNull()
        & (F.col("views") >= 0)
        & F.col("trending_dt").isNotNull()
    )


def add_growth(df):
    w = Window.partitionBy("video_id", "region").orderBy("trending_dt")
    return (
        df.withColumn("prev_views", F.lag("views").over(w))
        .withColumn("prev_dt", F.lag("trending_dt").over(w))
        .withColumn("delta_views", F.col("views") - F.col("prev_views"))
        .withColumn(
            "delta_hours",
            (F.unix_timestamp("trending_dt") - F.unix_timestamp("prev_dt")) / 3600.0,
        )
        .withColumn(
            "views_per_hour",
            F.when(F.col("delta_hours") > 0, F.col("delta_views") / F.col("delta_hours")),
        )
        .withColumn("year_month", F.date_format("trending_dt", "yyyy-MM"))
    )


def summarize(daily):
    return (
        daily.groupBy("video_id", "region")
        .agg(
            F.min("trending_dt").alias("first_trending_dt"),
            F.max("trending_dt").alias("last_trending_dt"),
            F.countDistinct("trending_dt").alias("snapshots"),
            F.max("views").alias("total_views"),
            F.max_by("title", "trending_dt").alias("title"),
            F.max_by("channel_title", "trending_dt").alias("channel_title"),
            F.max_by("category_id", "trending_dt").alias("category_id"),
            F.min("publish_dt").alias("publish_dt"),
            F.avg("views_per_hour").alias("avg_views_per_hour"),
            F.max("views_per_hour").alias("peak_views_per_hour"),
        )
        .withColumn("retention_days", F.datediff("last_trending_dt", "first_trending_dt"))
        .withColumn("publish_hour", F.hour("publish_dt"))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--dataset", default="youtube_trending")
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--out-root", default=str(ROOT / "data" / "processed" / "youtube_trending"))
    args = parser.parse_args()
    ensure_hadoop_home()

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    spark = (
        SparkSession.builder.master("local[*]")
        .appName("yt-transform")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "64")
        .config("spark.driver.maxResultSize", "1g")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    try:
        input_path = (
            Path(args.input).expanduser().resolve()
            if args.input
            else latest_raw_with_csv(Path(args.raw_root).resolve(), args.dataset)
        )
        log(f"start | input={input_path}")

        entries = prepare_inputs(input_path)
        raw = read_raw(spark, entries)
        rows_in = rows_in_from_split_manifests(entries)
        rows_in_src = "split_manifest"
        if rows_in is None:
            rows_in, rows_in_src = raw.count(), "spark_count"
        log(f"rows_in={rows_in:,} (nguồn: {rows_in_src})")

        out_root = Path(args.out_root).resolve()
        daily_out, summary_out = out_root / "daily", out_root / "summary"

        daily = add_growth(clean(raw))
        (
            daily.repartition("region").write.mode("overwrite")
            .partitionBy("region", "year_month").parquet(str(daily_out))
        )
        daily_check = spark.read.parquet(str(daily_out))
        rows_clean = daily_check.count()
        log(f"rows_clean={rows_clean:,} | dropped={rows_in - rows_clean:,}")

        summary = summarize(daily_check)
        (
            summary.repartition("region").write.mode("overwrite")
            .partitionBy("region").parquet(str(summary_out))
        )
        summary_rows = summary.count()

        duration = round(time.perf_counter() - t0, 1)
        manifest = {
            "dataset": args.dataset,
            "stage": "p3-transform",
            "engine": f"pyspark-local[{spark.sparkContext.defaultParallelism}]",
            "spark_driver_memory": spark.sparkContext.getConf().get("spark.driver.memory"),
            "source": str(input_path),
            "started_at_utc": started.isoformat(timespec="seconds"),
            "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "duration_seconds": duration,
            "rows_in": rows_in,
            "rows_in_source": rows_in_src,
            "rows_clean": rows_clean,
            "rows_dropped": rows_in - rows_clean,
            "dropped_heavy_columns": DROP_COLS,
            "daily_rows": rows_clean,
            "summary_rows": summary_rows,
            "outputs": {"daily": str(daily_out), "summary": str(summary_out)},
            "status": "success",
        }
        run_dir = out_root / "_manifests"
        run_dir.mkdir(parents=True, exist_ok=True)
        stamp = started.strftime("%Y%m%dT%H%M%SZ")
        (run_dir / f"run_{stamp}.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log(
            f"success | rows_in={rows_in:,} clean={rows_clean:,} "
            f"| daily={rows_clean:,} summary={summary_rows:,} "
            f"| duration={duration}s (NFR2 <= 600s)"
        )
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
