"""Ingestion job – Đồ án 2 Checkpoint 2 (YouTube Trending Analytics).

Copy file hoặc cả thư mục nguồn vào raw storage có tổ chức + ghi manifest truy vết.

Quy ước:  data/raw/<dataset>/ingest_date=YYYY-MM-DD/run_<UTC_TIMESTAMP>/

Rerun behavior (trả lời câu hỏi bắt buộc của checkpoint):
  * skip (mặc định)  – file cùng SHA-256 đã có trong raw -> SKIP, không tạo run mới;
                       chạy 3 lần -> raw giữ nguyên sau lần 1 (idempotent).
  * new-run          – luôn tạo run_id mới (append); trùng lặp nhận biết được theo run.
  * fail             – file trùng hash -> thoát mã lỗi, không ghi gì.
  * Nguồn hỏng (quality gate FAIL) -> fail fast, không tạo "raw" giả hợp lệ.

Chạy:
  python src/ingest_file.py --source "D:\\Downloads\\youtube_trends.tar.bz2" \
      --dataset youtube_trending [--raw-root data/raw] [--on-duplicate skip]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from split_csv import count_records

ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "logs" / "ingest.log"
ALLOWED_SUFFIX = {".csv", ".json", ".zip", ".bz2", ".gz", ".tar", ".txt", ".parquet"}
csv.field_size_limit(10**8)  # ô description có thể rất dài


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def head_is_multiline_csv(head: bytes) -> bool:
    """CSV có ô chứa newline không (1 record = N dòng vật lý)?

    So số record parse được (csv.reader) với số dòng vật lý trong phần đầu file:
    nếu parse được ÍT record hơn số dòng -> chắc chắn là CSV đa dòng.
    """
    text = head.decode("utf-8-sig", errors="replace")
    physical = text.count("\n")
    try:
        parsed = sum(1 for _ in csv.reader(io.StringIO(text)))
    except csv.Error:
        return True  # không parse sạch -> coi như CSV đa dòng (phải chuẩn hóa trước)
    return parsed < physical


def quality_gate(path: Path) -> tuple[list[str], dict]:
    """Kiểm tra tối thiểu trước khi chấp nhận ingestion. Trả (lỗi, thông tin rows)."""
    errors: list[str] = []
    info: dict = {
        "rows_estimate": None,
        "rows_estimate_kind": "unknown",
        "rows_estimate_note": "",
    }

    if not path.exists():
        return [f"không tồn tại: {path}"], info
    size = path.stat().st_size
    if size == 0:
        errors.append("bytes = 0 (file rỗng)")
    if path.suffix.lower() not in ALLOWED_SUFFIX:
        errors.append(f"extension không mong đợi: {path.suffix or '(không có)'}")
    try:
        with path.open("rb") as fh:
            head = fh.read(64 * 1024)
        if not head and size > 0:
            errors.append("không đọc được nội dung")
        elif path.suffix.lower() == ".csv" and head:
            if head_is_multiline_csv(head):
                # 1 record = N dòng vật lý -> đếm newline cho ra số ảo, KHÔNG dùng làm rows
                info["rows_estimate_kind"] = "multiline_csv"
                info["rows_estimate_note"] = (
                    "CSV nhiều dòng (ô 'description' chứa newline) -> số dòng vật lý KHÔNG "
                    "phải số record. Dùng --count-records hoặc src/verify_raw_records.py để "
                    "lấy số record thật (chuẩn RFC4180)."
                )
            else:
                lines = head.count(b"\n")
                info["rows_estimate"] = lines if len(head) >= size else round(lines * size / len(head))
                info["rows_estimate_kind"] = "physical_lines"
    except OSError as exc:
        errors.append(f"không mở được file: {exc}")
    return errors, info


def collect_sources(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(p for p in source.rglob("*") if p.is_file())
    return [source]


def previous_hashes(raw_root: Path, dataset: str) -> dict[str, str]:
    """Đọc mọi manifest đã có của dataset -> {sha256: destination}."""
    seen: dict[str, str] = {}
    for manifest in sorted((raw_root / dataset).glob("ingest_date=*/run_*/manifest.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in data.get("files", []):
            if entry.get("sha256"):
                seen.setdefault(entry["sha256"], entry.get("destination", ""))
    return seen


def make_run_id(dest_parent: Path) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"run_{stamp}"
    suffix = 1
    while (dest_parent / run_id).exists():
        suffix += 1
        run_id = f"run_{stamp}_{suffix}"
    return run_id


def rel_to_root(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest file/thư mục vào raw storage + manifest")
    parser.add_argument("--source", required=True, help="file hoặc thư mục nguồn")
    parser.add_argument("--dataset", default="youtube_trending", help="tên logic của dataset")
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"), help="gốc raw storage")
    parser.add_argument(
        "--on-duplicate",
        choices=["skip", "new-run", "fail"],
        default="skip",
        help="xử lý khi sha256 đã tồn tại trong raw (mặc định: skip = idempotent)",
    )
    parser.add_argument(
        "--count-records",
        action="store_true",
        help="đếm số record thật chuẩn RFC4180 (chậm với file lớn, dùng cho evidence)",
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    raw_root = Path(args.raw_root).expanduser().resolve()

    # --- 1. Thu thập nguồn ----------------------------------------------
    sources = collect_sources(source) if source.is_dir() else [source]
    if not sources:
        log(f"FAIL | dataset={args.dataset} | thư mục nguồn rỗng: {source}")
        return 1

    # --- 2. Quality gate (fail fast) -------------------------------------
    gate: dict[Path, tuple[list[str], dict]] = {}
    failed = False
    for path in sources:
        errors, info = quality_gate(path)
        gate[path] = (errors, info)
        for err in errors:
            log(f"GATE_FAIL | {path.name} | {err}")
            failed = True
    if failed:
        log(f"ABORT | dataset={args.dataset} | nguồn không đạt quality gate -> không tạo raw")
        return 1

    # --- 3. Hash + kiểm tra trùng lặp ------------------------------------
    seen = previous_hashes(raw_root, args.dataset)
    to_copy: list[Path] = []
    skipped: list[dict[str, str]] = []
    for path in sources:
        digest = sha256_of(path)
        if digest in seen and args.on_duplicate == "fail":
            log(f"FAIL | duplicate hash {digest[:12]}… ({path.name}) ở {seen[digest]}")
            return 1
        if digest in seen and args.on_duplicate == "skip":
            skipped.append({"name": path.name, "sha256": digest, "already_at": seen[digest]})
            continue
        to_copy.append(path)

    now = datetime.now(timezone.utc)
    if not to_copy:
        log(
            f"duplicate_skip | dataset={args.dataset} | {len(skipped)}/{len(sources)} file "
            f"đã có trong raw (sha256 khớp) -> raw storage KHÔNG thay đổi"
        )
        return 0

    # --- 4. Copy vào run mới ---------------------------------------------
    today = now.strftime("%Y-%m-%d")
    run_id = make_run_id(raw_root / args.dataset / f"ingest_date={today}")
    dest_dir = raw_root / args.dataset / f"ingest_date={today}" / run_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    for path in to_copy:
        target = dest_dir / path.name
        if target.exists():  # trùng tên trong cùng run -> prefix thư mục cha
            target = dest_dir / f"{path.parent.name}__{path.name}"
        shutil.copy2(path, target)
        info = gate[path][1]
        entry = {
            "name": target.name,
            "source": str(path),
            "bytes": target.stat().st_size,
            "sha256": sha256_of(target),
            "destination": rel_to_root(target),
            "rows_estimate": info["rows_estimate"],
            "rows_estimate_kind": info["rows_estimate_kind"],
        }
        if info["rows_estimate_note"]:
            entry["rows_estimate_note"] = info["rows_estimate_note"]
        if args.count_records and target.suffix.lower() == ".csv":
            counted = count_records(target)
            entry["records"] = counted["records"]
            entry["records_source"] = "rfc4180_counter"
            entry["records_columns"] = counted["columns"]
            entry["records_physical_lines"] = counted["physical_lines"]
            entry["records_multi_line_csv"] = counted["multi_line"]
            log(
                f"count_records | {target.name} | records={counted['records']:,} "
                f"| physical_lines={counted['physical_lines']:,} "
                f"| multi_line={counted['multi_line']}"
            )
        entries.append(entry)

    # --- 5. Manifest (giấy khai sinh của lần ingest) ----------------------
    total_bytes = sum(e["bytes"] for e in entries)
    combined = hashlib.sha256("".join(e["sha256"] for e in entries).encode()).hexdigest()
    manifest = {
        "dataset": args.dataset,
        "run_id": run_id,
        "source": str(source),
        "ingested_at_utc": now.isoformat(timespec="seconds"),
        # các trường phẳng khớp ví dụ trong slide (file đơn = file đó)
        "bytes": total_bytes,
        "sha256": entries[0]["sha256"] if len(entries) == 1 else combined,
        "destination": rel_to_root(dest_dir),
        "status": "success",
        "on_duplicate": args.on_duplicate,
        "files": entries,
        "skipped_duplicates": skipped,
    }
    if len(entries) == 1 and "records" in entries[0]:
        # file đơn -> số record thật đặt ở cấp manifest cho tiện tra cứu
        manifest["records"] = entries[0]["records"]
        manifest["records_source"] = entries[0]["records_source"]
    manifest_path = dest_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log(
        f"success | dataset={args.dataset} | run={run_id} | files={len(entries)} "
        f"(skipped={len(skipped)}) | bytes={total_bytes} | sha256={manifest['sha256'][:12]}… "
        f"| dest={rel_to_root(dest_dir)}"
    )
    log(f"manifest | {rel_to_root(manifest_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
