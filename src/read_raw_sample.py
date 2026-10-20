"""Đọc & kiểm tra raw bằng Spark – evidence 'Spark đọc được sample raw'.

Mặc định: tự tìm file trong manifest success mới nhất.
Output mong đợi: rows = ..., printSchema(), 5 dòng đầu.

Chạy:
  python src/read_raw_sample.py
  python src/read_raw_sample.py --path data/raw/youtube_trending/.../video.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def latest_raw_file(raw_root: Path, dataset: str | None) -> Path:
    manifests = sorted(
        raw_root.glob("**/manifest.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") != "success":
            continue
        if dataset and data.get("dataset") != dataset:
            continue
        dest = Path(data["files"][0]["destination"])
        return dest if dest.is_absolute() else ROOT / dest
    raise SystemExit(f"Không tìm thấy manifest success nào trong {raw_root}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Spark read & inspect raw data")
    parser.add_argument("--path", help="file raw cụ thể (csv/json/parquet)")
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--dataset", help="lọc manifest theo dataset")
    args = parser.parse_args()

    path = Path(args.path).expanduser().resolve() if args.path else latest_raw_file(
        Path(args.raw_root).expanduser().resolve(), args.dataset
    )
    if not path.exists():
        raise SystemExit(f"File không tồn tại: {path}")
    if path.stat().st_size == 0:
        raise SystemExit(f"File rỗng: {path}")

    name = path.name.lower()
    if name.endswith((".tar.bz2", ".zip", ".gz", ".bz2")):
        raise SystemExit(
            f"Raw là archive ({path.name}) -> hãy chạy file CSV đã trích xuất, "
            "vd: python src/read_raw_sample.py --path <file.csv>"
        )

    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.master("local[*]")
        .appName("raw-inspect")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    try:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = spark.read.option("header", True).csv(str(path))
        elif suffix == ".json":
            df = spark.read.json(str(path))
        elif suffix == ".parquet":
            df = spark.read.parquet(str(path))
        else:
            raise SystemExit(f"Chưa hỗ trợ đọc trực tiếp: {path.name}")

        print(f"file   = {path}")
        print(f"rows   = {df.count()}")
        df.printSchema()
        df.show(5, truncate=False)
        print("EVIDENCE: Spark đọc raw thành công (count + schema + sample).")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
