"""Đọc & kiểm tra raw bằng Spark – evidence 'Spark đọc được sample raw'.

VẤN ĐỀ QUAN TRỌNG (đã phát hiện khi verify checkpoint):
    Raw CSV của nguồn Kaggle có ô `description` chứa NEWLINE trong nháy kép
    -> 1 record = NHIỀU dòng vật lý.
    `spark.read.csv(path)` (multiLine=false, mặc định) vì vậy cắt vỡ record và
    đếm ra ~103 TRIỆU "dòng" thay vì 6.094.047 record thật.
    `multiLine=true` thì đúng, nhưng Spark phải nạp nguyên file 8,59 GB vào 1 task -> OOM
    trên máy 16 GB.

    → Cách đúng (giống transform.py): chuẩn hóa 1 dòng = 1 record bằng src/split_csv.py
      rồi đọc song song các chunk (multiLine=false, an toàn về RAM).

Mặc định: tự tìm file raw trong manifest success mới nhất.
Output mong đợi: rows = <số record thật>, printSchema(), 5 dòng đầu.

Chạy:
  python src/read_raw_sample.py
  python src/read_raw_sample.py --path data/raw/youtube_trending/.../file.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from split_csv import count_records, split_file

ROOT = Path(__file__).resolve().parents[1]
BIG_FILE_BYTES = 64 * 1024 * 1024  # >= ngưỡng này -> chuẩn hóa trước khi Spark đọc
CHUNK_MB = 256


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


def chunk_dir_for(path: Path) -> Path:
    return ROOT / "data" / "work" / "split" / path.stem


def prepare_csv(spark, path: Path) -> tuple[list[str], Path | None]:
    """Trả (danh sách file CSV để đọc, thư mục chunk nếu đã chuẩn hóa).

    File nhỏ  -> đọc trực tiếp với multiLine=true (đúng & không OOM).
    File lớn  -> chuẩn hóa qua split_csv.py (1 dòng = 1 record) rồi đọc multiLine=false.
    """
    if path.stat().st_size < BIG_FILE_BYTES:
        print(
            f"NOTE   | file < {BIG_FILE_BYTES // (1024 * 1024)} MB -> đọc trực tiếp, multiLine=true"
        )
        return [str(path)], None

    out_dir = chunk_dir_for(path)
    if not (out_dir / "split_manifest.json").exists():
        print(f"NOTE   | file lớn + CSV đa dòng -> chuẩn hóa qua src/split_csv.py ...")
        split_file(path, out_dir, CHUNK_MB)
    chunks = sorted(str(p) for p in out_dir.glob("*.csv"))
    print(
        f"NOTE   | raw CSV có ô 'description' chứa newline -> đọc multiLine=false SẼ VỠ record.\n"
        f"       | Đã đọc qua {len(chunks)} chunk chuẩn hóa (1 dòng = 1 record) tại {out_dir}"
    )
    return chunks, out_dir


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
        .config("spark.driver.memory", "4g")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    try:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            files, chunk_dir = prepare_csv(spark, path)
            df = spark.read.option("header", True).option("encoding", "UTF-8").csv(files)
        elif suffix == ".json":
            df = spark.read.json(str(path))
        elif suffix == ".parquet":
            df = spark.read.parquet(str(path))
        else:
            raise SystemExit(f"Chưa hỗ trợ đọc trực tiếp: {path.name}")

        rows = df.count()
        print(f"file   = {path}")
        print(f"rows   = {rows:,}")
        if suffix == ".csv" and chunk_dir is not None:
            manifest_path = chunk_dir / "split_manifest.json"
            if manifest_path.exists():
                expected = json.loads(manifest_path.read_text(encoding="utf-8"))["records"]
                verdict = "KHỚP" if expected == rows else "KHÔNG KHỚP"
                print(
                    f"records (split_manifest.json) = {expected:,} -> {verdict} với Spark count"
                )
        df.printSchema()
        df.show(5, truncate=False)
        print("EVIDENCE: Spark đọc raw thành công (count + schema + sample).")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
