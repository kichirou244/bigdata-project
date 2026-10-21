"""Chuẩn hóa & chia nhỏ CSV lớn trước khi đưa vào Spark (pre-processing P3).

Vấn đề: file CSV tải từ Kaggle (8 GB) có ô ``description`` chứa newline
bên trong nháy kép (1 record = NHIỀU dòng vật lý):

  * đọc multiline=false (mặc định, splittable, song song)  -> vỡ dòng, sai dữ liệu;
  * đọc multiline=true    -> Spark phải nạp NGUYÊN file vào bộ nhớ 1 task -> OOM (máy 16GB).

Giải pháp: quét 1 lần, tách ranh giới record bằng **parity dấu nháy kép**
(chuẩn RFC4180 – mọi dấu ``"`` lồng trong ô đều nhân đôi ``""``), gộp các dòng
cùng record và thay newline trong ô bằng SPACE. Đầu ra là CSV "1 dòng = 1 record":

  * Spark đọc song song bình thường (không cần multiLine, không OOM);
  * giữ nguyên toàn bộ cột/giá trị, chỉ đổi newline -> space trong ``description``.

Đầu ra:
  <out-dir>/chunk_00000.csv, ...   (mỗi chunk có lại header)
  <out-dir>/split_manifest.json    # records, chunks, bytes, duration (evidence)

Chạy:
  python src/split_csv.py --source "data/raw/youtube_trending/ingest_date=.../run_.../file.csv" \
      --out-dir data/work/split/trending_yt_videos_113_countries [--chunk-mb 256]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

csv.field_size_limit(10**8)  # description có thể rất dài

MAX_RECORD_BYTES = 20 * 1024 * 1024  # guard: lệch nháy -> dừng sớm thay vì trộn cả file
VALIDATE_FIRST = 500                  # số record kiểm tra cột/ chunk


def count_records(source: Path) -> dict:
    """Đếm record chuẩn RFC4180 trong CSV (1 record có thể nhiều dòng vật lý).

    Dùng cùng thuật toán parity dấu nháy kép như split_file() nhưng KHÔNG ghi file,
    chỉ quét 1 lần -> trả về số record thật (không phải số dòng vật lý).

    Trả về dict: records, columns, physical_lines, multi_line.
    """
    header: list[str] = []
    in_quotes = False
    records = 0
    physical_lines = 0
    multi_line = False
    pending = False  # đang giữ dòng thuộc record chưa kết thúc

    with source.open("r", encoding="utf-8-sig", errors="replace") as src:
        for i, line in enumerate(src):
            physical_lines += 1
            content = line[:-1] if line.endswith("\n") else line
            odd = content.count('"') % 2
            if i == 0:  # header
                header = next(csv.reader([content]))
                if odd:
                    raise SystemExit("header có số dấu \" lẻ -> không phải CSV chuẩn RFC4180")
                continue
            if odd:
                in_quotes = not in_quotes
                multi_line = True
            if in_quotes:  # dòng nằm TRONG ô -> record chưa kết thúc
                pending = True
                continue
            if content.strip() == "":
                continue
            records += 1
            pending = False
    if pending:  # file bị cắt giữa record -> cảnh báo, không tự sửa
        raise SystemExit("CSV kết thúc giữa chừng một record (dấu \" không cân bằng)")
    return {
        "records": records,
        "columns": len(header),
        "physical_lines": physical_lines,
        "multi_line": multi_line,
    }


def split_file(source: Path, out_dir: Path, chunk_mb: int = 256) -> dict:
    """Tách source thành các chunk 1-dòng-1-record. Idempotent (có manifest -> skip)."""
    manifest_path = out_dir / "split_manifest.json"
    if manifest_path.exists():
        print(f"skip | {out_dir} đã có split_manifest.json")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("chunk_*.csv"):
        old.unlink()

    target = chunk_mb * 1024 * 1024
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    header: bytes | None = None
    in_quotes = False
    buf: list[bytes] = []
    buf_bytes = 0
    records = 0
    chunks: list[dict] = []
    fh = None
    written = 0

    def roll() -> None:
        nonlocal fh, written
        if fh is not None:
            fh.close()
        name = f"chunk_{len(chunks):05d}.csv"
        fh = (out_dir / name).open("wb")
        chunks.append({"name": name, "records": 0, "bytes": 0})
        fh.write(header)  # type: ignore[arg-type]
        written = len(header or b"")

    def flush() -> None:
        nonlocal buf, buf_bytes, records, written
        record = b"".join(buf)
        buf, buf_bytes = [], 0
        if record in (b"", b"\n"):  # dòng trống -> bỏ
            return
        if fh is None or (written >= target and chunks[-1]["records"] > 0):
            roll()
        assert fh is not None
        fh.write(record)
        written += len(record)
        chunks[-1]["records"] += 1
        chunks[-1]["bytes"] = written
        records += 1
        if records % 1_000_000 == 0:
            print(f"  ... {records:,} records | chunk hiện tại {written / 1e6:.0f} MB")

    with source.open("r", encoding="utf-8-sig", errors="replace") as src:
        for i, line in enumerate(src):
            # universal newlines đã dịch \r\n / \r -> \n
            content = line[:-1] if line.endswith("\n") else line
            odd = content.count('"') % 2
            if i == 0:  # header
                header = (content + "\n").encode("utf-8")
                if odd:
                    raise SystemExit("header có số dấu \" lẻ -> không phải CSV chuẩn RFC4180")
                roll()
                continue
            if odd:
                in_quotes = not in_quotes
            if in_quotes:  # dòng nằm TRONG ô -> nối tiếp bằng space
                piece = (content + " ").encode("utf-8")
            else:  # record kết thúc ở dòng này
                piece = (content + "\n").encode("utf-8")
            buf.append(piece)
            buf_bytes += len(piece)
            if buf_bytes > MAX_RECORD_BYTES:
                print(
                    f"WARN | record > {MAX_RECORD_BYTES} bytes tại dòng {i} -> force reset "
                    "(nguồn có dấu \" không chuẩn, kiểm tra lại)"
                )
                in_quotes = False
            if not in_quotes:
                flush()
    if fh is not None:
        fh.close()

    # --- Validate: mọi chunk phải đủ & đồng nhất số cột -------------------
    expected = None
    for ch in chunks:
        with (out_dir / ch["name"]).open("r", encoding="utf-8", newline="") as fv:
            reader = csv.reader(fv)
            head = next(reader)
            if expected is None:
                expected = len(head)
            if len(head) != expected:
                raise SystemExit(f"VALIDATE_FAIL | {ch['name']}: header {len(head)} cột != {expected}")
            for j, row in enumerate(reader):
                if j >= VALIDATE_FIRST:
                    break
                if len(row) != expected:
                    raise SystemExit(
                        f"VALIDATE_FAIL | {ch['name']} dòng {j + 2}: {len(row)} cột "
                        f"(kỳ vọng {expected}) -> nguồn có dấu \" không chuẩn"
                    )

    duration = round(time.perf_counter() - t0, 1)
    manifest = {
        "source": str(source),
        "stage": "pre-split-normalize",
        "started_at_utc": started.isoformat(timespec="seconds"),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_seconds": duration,
        "records": records,
        "columns": expected,
        "chunk_mb": chunk_mb,
        "source_bytes": source.stat().st_size,
        "total_bytes": sum(c["bytes"] for c in chunks),
        "chunks": chunks,
        "transform_note": "newline trong ô đã -> space; 1 dòng vật lý = 1 record",
        "status": "success",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"done | records={records:,} | columns={expected} | chunks={len(chunks)} "
        f"| {duration}s | -> {manifest_path}"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Chuẩn hóa CSV nhiều dòng + chia chunk cho Spark")
    parser.add_argument("--source", required=True, help="file CSV nguồn")
    parser.add_argument("--out-dir", required=True, help="thư mục xuất các chunk")
    parser.add_argument("--chunk-mb", type=int, default=256, help="dung lượng mỗi chunk (MB)")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Không tìm thấy file: {source}")
    split_file(source, Path(args.out_dir).expanduser().resolve(), args.chunk_mb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
