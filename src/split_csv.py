"""Chuẩn hóa CSV đa dòng (1 dòng = 1 record) và chia chunk cho Spark."""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

csv.field_size_limit(10**8)
MAX_RECORD_BYTES = 20 * 1024 * 1024
VALIDATE_FIRST = 500


def count_records(source: Path) -> dict:
    header: list[str] = []
    in_quotes = False
    records = physical_lines = 0
    multi_line = pending = False

    with source.open("r", encoding="utf-8-sig", errors="replace") as src:
        for i, line in enumerate(src):
            physical_lines += 1
            content = line[:-1] if line.endswith("\n") else line
            odd = content.count('"') % 2
            if i == 0:
                header = next(csv.reader([content]))
                if odd:
                    raise SystemExit('header có số dấu " lẻ -> không phải CSV chuẩn RFC4180')
                continue
            if odd:
                in_quotes = not in_quotes
                multi_line = True
            if in_quotes:
                pending = True
                continue
            if content.strip() == "":
                continue
            records += 1
            pending = False
    if pending:
        raise SystemExit('CSV kết thúc giữa chừng một record (dấu " không cân bằng)')
    return {
        "records": records,
        "columns": len(header),
        "physical_lines": physical_lines,
        "multi_line": multi_line,
    }


def split_file(source: Path, out_dir: Path, chunk_mb: int = 256) -> dict:
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
    header = b""
    in_quotes = False
    buf: list[bytes] = []
    buf_bytes = records = written = 0
    chunks: list[dict] = []
    fh = None

    def roll() -> None:
        nonlocal fh, written
        if fh is not None:
            fh.close()
        name = f"chunk_{len(chunks):05d}.csv"
        fh = (out_dir / name).open("wb")
        chunks.append({"name": name, "records": 0, "bytes": 0})
        fh.write(header)
        written = len(header)

    def flush() -> None:
        nonlocal buf, buf_bytes, records, written
        record = b"".join(buf)
        buf, buf_bytes = [], 0
        if record in (b"", b"\n"):
            return
        if fh is None or (written >= target and chunks[-1]["records"] > 0):
            roll()
        fh.write(record)
        written += len(record)
        chunks[-1]["records"] += 1
        chunks[-1]["bytes"] = written
        records += 1
        if records % 1_000_000 == 0:
            print(f"  ... {records:,} records | chunk {written / 1e6:.0f} MB")

    with source.open("r", encoding="utf-8-sig", errors="replace") as src:
        for i, line in enumerate(src):
            content = line[:-1] if line.endswith("\n") else line
            odd = content.count('"') % 2
            if i == 0:
                header = (content + "\n").encode("utf-8")
                if odd:
                    raise SystemExit('header có số dấu " lẻ -> không phải CSV chuẩn RFC4180')
                roll()
                continue
            if odd:
                in_quotes = not in_quotes
            piece = (content + " " if in_quotes else content + "\n").encode("utf-8")
            buf.append(piece)
            buf_bytes += len(piece)
            if buf_bytes > MAX_RECORD_BYTES:
                print(f"WARN | record > {MAX_RECORD_BYTES} bytes tại dòng {i} -> force reset")
                in_quotes = False
            if not in_quotes:
                flush()
    if fh is not None:
        fh.close()

    expected = None
    for ch in chunks:
        with (out_dir / ch["name"]).open("r", encoding="utf-8", newline="") as fv:
            reader = csv.reader(fv)
            head = next(reader)
            expected = expected or len(head)
            if len(head) != expected:
                raise SystemExit(f"VALIDATE_FAIL | {ch['name']}: header {len(head)} != {expected}")
            for j, row in enumerate(reader):
                if j >= VALIDATE_FIRST:
                    break
                if len(row) != expected:
                    raise SystemExit(f"VALIDATE_FAIL | {ch['name']} dòng {j + 2}: {len(row)} cột")

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
        "status": "success",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"done | records={records:,} | columns={expected} | chunks={len(chunks)} "
        f"| {duration}s | -> {manifest_path}"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--chunk-mb", type=int, default=256)
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Không tìm thấy file: {source}")
    split_file(source, Path(args.out_dir).expanduser().resolve(), args.chunk_mb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
