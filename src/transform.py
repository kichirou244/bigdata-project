"""P3 – Pipeline xử lý dữ liệu YouTube Trending bằng Apache Spark.

Yêu cầu phủ:
  FR1  nạp & làm sạch dữ liệu đa file CSV nhiều quốc gia
  FR2  khử trùng lặp theo (video_id, region, trending_date) + tính số ngày trụ hạng
  FR3  tốc độ tăng trưởng view = Δviews / Δgiờ giữa hai snapshot liên tiếp
  FR4  lưu Parquet phân vùng theo region / year_month

Input  (tự nhận diện, không cần sửa code khi đổi nguồn):
  * thư mục CSV nhỏ kiểu `XXvideos.csv` (Kaggle cũ, region lấy từ tên file);
  * file CSV lớn/CSV gộp (Kaggle 113-nước, ô description chứa newline) ->
    TỰ động chuẩn hóa qua src/split_csv.py (1 dòng = 1 record) rồi đọc song song;
  * schema nguồn khác -> SRC_MAP ánh xạ về canonical
    (view_count -> views, snapshot_date -> trending_date, country -> region, ...);
  * mặc định = run raw mới nhất trong manifest Checkpoint 2.

Output: <out-root>/daily     snapshot hằng ngày đã làm sạch (partition region/year_month)
        <out-root>/summary   1 dòng/video/region: retention_days, peak_views_per_hour, ...
        <out-root>/_manifests/run_*.json + logs/transform.log   (evidence NFR2)

Chiến lược bộ nhớ (máy 16GB, Spark local):
  * description (≈1.4KB/dòng, ~8GB tổng) được DROP trước khi tính metric –
    giữ nguyên ở layer raw, dashboard không dùng -> tiết kiệm RAM/IO;
  * KHÔNG cache DataFrame lớn; summary đọc lại từ Parquet vừa ghi (nhẹ hơn cache).

Chạy:
  python src/transform.py
  python src/transform.py --input data/work/split/trending_yt_videos_113_countries
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
# Cột nặng/không dùng cho metric -> drop TRƯỚC khi xử lý (raw vẫn giữ nguyên bản gốc).
# description trung bình ≈1.4KB/ dòng (~8GB) là nguyên nhân OOM nếu cache nguyên bảng.
DROP_COLS = [
    "description", "tags", "thumbnail_link",
    "comments_disabled", "ratings_disabled", "video_error_or_removed",
]
# Ánh xạ schema nguồn (Kaggle 113-nước bản gộp) -> canonical
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
BIG_FILE_BYTES = 64 * 1024 * 1024  # >= ngưỡng này -> bắt buộc chuẩn hóa trước (split)
CHUNK_MB = 256
# Emoji/ký tự điều khiển/zero-width – giữ nguyên tiếng Việt (Unicode letters)
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
    """Windows: Spark GHI file Parquet cần winutils.exe + hadoop.dll (Hadoop).

    Tự trỏ HADOOP_HOME vào thư mục hadoop/ trong repo (xem README mục 2b) và đưa
    hadoop/bin vào PATH để JVM nạp được hadoop.dll (java.library.path lấy từ PATH).
    """
    winutils_dir = ROOT / "hadoop" / "bin"
    if os.name != "nt" or not (winutils_dir / "winutils.exe").exists():
        return
    os.environ.setdefault("HADOOP_HOME", str(ROOT / "hadoop"))
    os.add_dll_directory(str(winutils_dir))
    if str(winutils_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = str(winutils_dir) + os.pathsep + os.environ.get("PATH", "")


def latest_raw_with_csv(raw_root: Path, dataset: str) -> Path:
    """Run raw mới nhất còn chứa CSV (bỏ qua run chỉ có archive)."""
    runs = sorted(
        (raw_root / dataset).glob("ingest_date=*/run_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for run in runs:
        if any(run.glob("*.csv")):
            return run
    raise SystemExit(
        f"Không tìm thấy run raw nào có CSV trong {raw_root / dataset}. "
        "Chạy ingest trước: python src/ingest_file.py --source <nguồn> --dataset "
        f"{dataset}"
    )


def prepare_inputs(input_path: Path) -> list[tuple[list[Path], bool]]:
    """Trả về [(danh sách file, đã_chuẩn_hoa?)].

    File >= BIG_FILE_BYTES chứa newline trong ô (description đa dòng) phải được
    split -> 1 dòng = 1 record trước khi Spark đọc (xem src/split_csv.py).
    """
    if input_path.is_file():
        candidates = [input_path]
    elif (input_path / "split_manifest.json").exists():
        return [(sorted(input_path.glob("*.csv")), True)]
    else:
        candidates = sorted(input_path.glob("*.csv"))
    if not candidates:
        raise SystemExit(
            f"Không tìm thấy CSV trong: {input_path} "
            "(nếu trỏ vào data/work/split hãy trỏ vào thư mục chunk con)"
        )

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
            # chunk đã chuẩn hóa: multiline=false (splittable, song song);
            # file nhỏ: multiline=true an toàn vì mỗi file chỉ vài MB.
            df = (
                spark.read.option("header", True)
                .option("encoding", "UTF-8")
                .option("multiLine", "false" if normalized else "true")
                .csv(str(file))
            )
            df = df.toDF(*[c.strip().lower().replace(" ", "_") for c in df.columns])
            # Adapter: schema nguồn khác -> canonical (vd. view_count -> views)
            for src, dst in SRC_MAP.items():
                if src in df.columns and dst not in df.columns:
                    df = df.withColumnRenamed(src, dst)
            if "region" not in df.columns:
                match = REGION_RE.match(file.name)
                df = df.withColumn(
                    "region", F.lit(match.group(1).upper() if match else "UNKNOWN")
                )
            # cột không tồn tại ở schema nguồn -> NULL (clean() sẽ try_cast/fill)
            for col in keep:
                if col not in df.columns:
                    df = df.withColumn(col, F.lit(None).cast("string"))
            frames.append(df.select(keep))
            log(f"read | {file.name} | bytes={file.stat().st_size:,} | multiline={not normalized}")

    out = frames[0]
    for df in frames[1:]:
        out = out.unionByName(df)
    return out


def rows_in_from_split_manifests(entries: list[tuple[list[Path], bool]]) -> int | None:
    """Số dòng đầu vào lấy từ split_manifest (không phải Spark count) nếu được."""
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
    """Làm sạch tối thiểu tầng transform (raw vẫn được bảo toàn nguyên vẹn)."""
    df = df.withColumn(
        "trending_dt",
        F.coalesce(
            # snapshot_date ISO: 2026-10-20
            F.to_date("trending_date", "yyyy-MM-dd"),
            # trending_date kiểu Kaggle cũ: YY.DD.MM (17.14.11 -> 2017-11-14)
            F.to_date(
                F.regexp_extract("trending_date", r"^(\d{2}\.\d{2}\.\d{2})", 1),
                "yy.dd.MM",
            ),
        ),
    ).withColumn(
        "publish_dt",
        F.coalesce(
            # 2026-10-09 00:00:00+00:00  (Kaggle 113-nước)
            F.to_timestamp("publish_time", "yyyy-MM-dd HH:mm:ssXXX"),
            # 2017-11-13T16:08:22.000Z   (Kaggle cũ)
            F.to_timestamp("publish_time", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"),
            F.to_timestamp("publish_time", "yyyy-MM-dd'T'HH:mm:ssXXX"),
            F.to_timestamp("publish_time", "yyyy-MM-dd HH:mm:ss"),
            F.to_timestamp("publish_time", "yyyy-MM-dd'T'HH:mm:ss"),
            F.to_timestamp(F.to_date("publish_time")),  # chỉ còn lại ngày
        ),
    )
    # FR2: khử trùng lặp theo KÉO (video_id, region, trending_date)
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
    """FR3: Δviews / Δgiờ giữa hai snapshot liên tiếp (cùng video + region)."""
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
    """FR2/FR3: 1 dòng / video / region (đọc từ Parquet daily vừa ghi -> nhẹ hơn cache)."""
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
    parser = argparse.ArgumentParser(description="P3: Spark transform -> Parquet phân vùng")
    parser.add_argument("--input", help="thư mục CSV hoặc 1 file CSV (mặc định: run raw mới nhất)")
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
        if rows_in is None:
            rows_in = raw.count()
            rows_in_src = "spark_count"
        else:
            rows_in_src = "split_manifest"
        log(f"rows_in={rows_in:,} (nguồn: {rows_in_src})")

        out_root = Path(args.out_root).resolve()
        daily_out, summary_out = out_root / "daily", out_root / "summary"

        # FR4: daily Parquet phân vùng (repation theo region -> mỗi partition dir 1 file)
        daily = add_growth(clean(raw))
        (
            daily.repartition("region").write.mode("overwrite")
            .partitionBy("region", "year_month").parquet(str(daily_out))
        )
        # Summary tính trên Parquet vừa ghi (đọc lại ≈1GB columnar, không cần cache)
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
        finished = datetime.now(timezone.utc)
        manifest = {
            "dataset": args.dataset,
            "stage": "p3-transform",
            "engine": f"pyspark-local[{spark.sparkContext.defaultParallelism}]",
            "spark_driver_memory": spark.sparkContext.getConf().get("spark.driver.memory"),
            "source": str(input_path),
            "started_at_utc": started.isoformat(timespec="seconds"),
            "finished_at_utc": finished.isoformat(timespec="seconds"),
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
            f"dropped={rows_in - rows_clean:,} "
            f"| daily={rows_clean:,} summary={summary_rows:,} "
            f"| duration={duration}s (NFR2 <= 600s)"
        )
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
