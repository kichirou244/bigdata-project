"""Xác minh số record thật của raw CSV và bổ sung vào manifest (evidence TRACE).

VÌ SAO CẦN:
    `ingest_file.py` ước lượng rows bằng cách đếm newline trong 64 KB đầu file.
    Với CSV có ô chứa newline (ô `description` của nguồn Kaggle), 1 record = N dòng
    vật lý -> ước lượng ra số ảo (128.341.650 thay vì 6.094.047).
    Công cụ này đếm lại bằng thuật toán parity dấu nháy kép (chuẩn RFC4180) và
    GHI BỔ SUNG `records` vào manifest kèm audit trail.

    - KHÔNG sửa raw data (CSV trong raw giữ nguyên byte-for-byte).
    - Manifest chỉ được BỔ SUNG trường + ghi lại thay đổi trong `amendments[]`.
    - Mọi thao tác được ghi vào logs/ingest.log để truy vết.

Chạy:
  python src/verify_raw_records.py                       # run raw mới nhất
  python src/verify_raw_records.py --run-dir <thư mục run>
  python src/verify_raw_records.py --check               # chỉ kiểm tra, không ghi
"""
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
    parser = argparse.ArgumentParser(description="Đếm record thật của raw CSV + bổ sung manifest")
    parser.add_argument("--run-dir", help="thư mục run cụ thể (mặc định: run mới nhất)")
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--dataset", default="youtube_trending")
    parser.add_argument(
        "--check",
        action="store_true",
        help="chỉ in kết quả, không ghi vào manifest/log",
    )
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
        raise SystemExit(
            f"run này có {len(files)} file -> tool này chỉ xử lý run 1 file "
            "(điều chỉnh nếu cần)"
        )

    csv_path = run_dir / files[0]["name"]
    if not csv_path.exists():
        raise SystemExit(f"Không tìm thấy file raw: {csv_path}")

    t0 = time.perf_counter()
    result = count_records(csv_path)
    duration = round(time.perf_counter() - t0, 1)

    print(f"file       = {csv_path}")
    print(f"records    = {result['records']:,}")
    print(f"columns    = {result['columns']}")
    print(f"physical   = {result['physical_lines']:,} dòng vật lý")
    print(f"multi_line = {result['multi_line']}")
    print(f"duration   = {duration}s")

    if args.check:
        return 0

    old_estimate = files[0].get("rows_estimate")
    amendment = {
        "at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "src/verify_raw_records.py",
        "change": (
            "rows_estimate (ước lượng theo dòng vật lý) -> records (đếm chuẩn RFC4180)"
        ),
        "rows_estimate_before": old_estimate,
        "rows_estimate_kind": files[0].get("rows_estimate_kind", "physical_lines"),
        "records_after": result["records"],
        "records_source": "rfc4180_counter",
        "duration_seconds": duration,
    }

    files[0]["rows_estimate"] = None
    files[0]["rows_estimate_kind"] = "multiline_csv"
    files[0]["rows_estimate_note"] = (
        "CSV nhiều dòng (ô 'description' chứa newline) -> số dòng vật lý KHÔNG phải số record. "
        "Số record thật xem `records` (đếm chuẩn RFC4180 bởi src/verify_raw_records.py)."
    )
    files[0]["records"] = result["records"]
    files[0]["records_source"] = "rfc4180_counter"
    files[0]["records_columns"] = result["columns"]
    files[0]["records_physical_lines"] = result["physical_lines"]
    files[0]["records_multi_line_csv"] = result["multi_line"]

    manifest["records"] = result["records"]
    manifest["records_source"] = "rfc4180_counter"
    manifest.setdefault("amendments", []).append(amendment)

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(
        f"verify_records | run={manifest.get('run_id')} | file={csv_path.name} "
        f"| records={result['records']:,} | physical_lines={result['physical_lines']:,} "
        f"| multi_line={result['multi_line']} | {duration}s "
        f"| manifest += records (amendments[{len(manifest['amendments'])}])"
    )
    print(f"-> manifest đã cập nhật: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
