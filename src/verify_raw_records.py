"""Đếm record chuẩn RFC4180 của raw CSV và bổ sung vào manifest (không sửa raw)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from split_csv import count_records

ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "logs" / "ingest.log"


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def latest_run_with_csv(raw_root: Path, dataset: str) -> Path:
    runs = sorted(
        (raw_root / dataset).glob("ingest_date=*/run_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for run in runs:
        if any(run.glob("*.csv")):
            return run
    raise SystemExit(f"Không tìm thấy run raw nào có CSV trong {raw_root / dataset}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--dataset", default="youtube_trending")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    run_dir = (
        Path(args.run_dir).expanduser().resolve()
        if args.run_dir
        else latest_run_with_csv(Path(args.raw_root).expanduser().resolve(), args.dataset)
    )
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Không có manifest trong {run_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    if len(files) != 1:
        raise SystemExit(f"run này có {len(files)} file -> chỉ xử lý run 1 file")

    csv_path = run_dir / files[0]["name"]
    if not csv_path.exists():
        raise SystemExit(f"Không tìm thấy file raw: {csv_path}")

    t0 = time.perf_counter()
    result = count_records(csv_path)
    duration = round(time.perf_counter() - t0, 1)

    print(
        f"file       = {csv_path}\n"
        f"records    = {result['records']:,}\n"
        f"columns    = {result['columns']}\n"
        f"physical   = {result['physical_lines']:,} dòng vật lý\n"
        f"multi_line = {result['multi_line']}\n"
        f"duration   = {duration}s"
    )
    if args.check:
        return 0

    files[0].update(
        rows_estimate=None,
        rows_estimate_kind="multiline_csv",
        rows_estimate_note=(
            "CSV nhiều dòng: số dòng vật lý không phải số record. "
            "Số thật ở `records` (RFC4180)."
        ),
        records=result["records"],
        records_source="rfc4180_counter",
        records_columns=result["columns"],
        records_physical_lines=result["physical_lines"],
        records_multi_line_csv=result["multi_line"],
    )
    manifest["records"] = result["records"]
    manifest["records_source"] = "rfc4180_counter"
    manifest.setdefault("amendments", []).append(
        {
            "at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": "src/verify_raw_records.py",
            "change": "rows_estimate -> records (RFC4180)",
            "records_after": result["records"],
            "duration_seconds": duration,
        }
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(
        f"verify_records | run={manifest.get('run_id')} | file={csv_path.name} "
        f"| records={result['records']:,} | physical_lines={result['physical_lines']:,} "
        f"| {duration}s | manifest += records"
    )
    print(f"-> manifest đã cập nhật: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
