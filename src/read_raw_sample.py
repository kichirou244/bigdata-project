"""Spark đọc & kiểm tra raw (count + schema + 5 dòng đầu)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from split_csv import split_file

ROOT = Path(__file__).resolve().parents[1]
BIG_FILE_BYTES = 64 * 1024 * 1024
CHUNK_MB = 256


def latest_raw_file(raw_root: Path, dataset: str | None) -> Path:
    manifests = sorted(
        raw_root.glob("**/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") != "success" or (dataset and data.get("dataset") != dataset):
            continue
        dest = Path(data["files"][0]["destination"])
        return dest if dest.is_absolute() else ROOT / dest
    raise SystemExit(f"Không tìm thấy manifest success nào trong {raw_root}")


def prepare_csv(path: Path) -> tuple[list[str], bool]:
    if path.stat().st_size < BIG_FILE_BYTES:
        return [str(path)], False

    out_dir = ROOT / "data" / "work" / "split" / path.stem
    if not (out_dir / "split_manifest.json").exists():
        print("NOTE   | file lớn: chuẩn hóa qua src/split_csv.py ...")
        split_file(path, out_dir, CHUNK_MB)
    chunks = sorted(str(p) for p in out_dir.glob("*.csv"))
    print(f"NOTE   | đọc {len(chunks)} chunk đã chuẩn hóa (1 dòng = 1 record)")
    return chunks, True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path")
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--dataset")
    args = parser.parse_args()

    path = Path(args.path).expanduser().resolve() if args.path else latest_raw_file(
        Path(args.raw_root).expanduser().resolve(), args.dataset
    )
    if not path.exists():
        raise SystemExit(f"File không tồn tại: {path}")
    if path.stat().st_size == 0:
        raise SystemExit(f"File rỗng: {path}")
    if path.name.lower().endswith((".tar.bz2", ".zip", ".gz", ".bz2")):
        raise SystemExit("Raw là archive -> trỏ vào file CSV đã trích xuất.")

    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.master("local[*]")
        .appName("raw-inspect")
        .config("spark.driver.memory", "4g")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    try:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            files, normalized = prepare_csv(path)
            df = (
                spark.read.option("header", True)
                .option("encoding", "UTF-8")
                .option("multiLine", "false" if normalized else "true")
                .csv(files)
            )
        elif suffix == ".json":
            df = spark.read.json(str(path))
        elif suffix == ".parquet":
            df = spark.read.parquet(str(path))
        else:
            raise SystemExit(f"Chưa hỗ trợ đọc trực tiếp: {path.name}")

        rows = df.count()
        print(f"file   = {path}\nrows   = {rows:,}")
        if suffix == ".csv":
            split_manifest = ROOT / "data" / "work" / "split" / path.stem / "split_manifest.json"
            if split_manifest.exists():
                expected = json.loads(split_manifest.read_text(encoding="utf-8"))["records"]
                print(f"records (split_manifest) = {expected:,} -> "
                      f"{'KHỚP' if expected == rows else 'KHÔNG KHỚP'}")
        df.printSchema()
        df.show(5, truncate=False)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
