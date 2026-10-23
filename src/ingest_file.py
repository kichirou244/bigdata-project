"""Copy nguồn vào raw storage + ghi manifest. Mặc định skip nếu SHA-256 đã tồn tại."""
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
csv.field_size_limit(10**8)


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
    text = head.decode("utf-8-sig", errors="replace")
    physical = text.count("\n")
    try:
        parsed = sum(1 for _ in csv.reader(io.StringIO(text)))
    except csv.Error:
        return True
    return parsed < physical


def quality_gate(path: Path) -> tuple[list[str], dict]:
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
                info["rows_estimate_kind"] = "multiline_csv"
                info["rows_estimate_note"] = (
                    "CSV nhiều dòng: số dòng vật lý không phải số record. "
                    "Dùng src/verify_raw_records.py (RFC4180) để lấy số thật."
                )
            else:
                lines = head.count(b"\n")
                info["rows_estimate"] = lines if len(head) >= size else round(lines * size / len(head))
                info["rows_estimate_kind"] = "physical_lines"
    except OSError as exc:
        errors.append(f"không mở được file: {exc}")
    return errors, info


def collect_sources(source: Path) -> list[Path]:
    return sorted(p for p in source.rglob("*") if p.is_file()) if source.is_dir() else [source]


def previous_hashes(raw_root: Path, dataset: str) -> dict[str, str]:
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
    run_id, suffix = f"run_{stamp}", 1
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
    parser.add_argument("--source", required=True)
    parser.add_argument("--dataset", default="youtube_trending")
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--on-duplicate", choices=["skip", "new-run", "fail"], default="skip")
    parser.add_argument("--count-records", action="store_true")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    raw_root = Path(args.raw_root).expanduser().resolve()

    sources = collect_sources(source)
    if not sources:
        log(f"FAIL | dataset={args.dataset} | thư mục nguồn rỗng: {source}")
        return 1

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
            "đã có trong raw (sha256 khớp) -> raw storage KHÔNG thay đổi"
        )
        return 0

    today = now.strftime("%Y-%m-%d")
    dest_dir = raw_root / args.dataset / f"ingest_date={today}" / make_run_id(
        raw_root / args.dataset / f"ingest_date={today}"
    )
    dest_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    for path in to_copy:
        target = dest_dir / path.name
        if target.exists():
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
            entry.update(
                records=counted["records"],
                records_source="rfc4180_counter",
                records_columns=counted["columns"],
                records_physical_lines=counted["physical_lines"],
                records_multi_line_csv=counted["multi_line"],
            )
            log(f"count_records | {target.name} | records={counted['records']:,}")
        entries.append(entry)

    total_bytes = sum(e["bytes"] for e in entries)
    combined = hashlib.sha256("".join(e["sha256"] for e in entries).encode()).hexdigest()
    manifest = {
        "dataset": args.dataset,
        "run_id": dest_dir.name,
        "source": str(source),
        "ingested_at_utc": now.isoformat(timespec="seconds"),
        "bytes": total_bytes,
        "sha256": entries[0]["sha256"] if len(entries) == 1 else combined,
        "destination": rel_to_root(dest_dir),
        "status": "success",
        "on_duplicate": args.on_duplicate,
        "files": entries,
        "skipped_duplicates": skipped,
    }
    if len(entries) == 1 and "records" in entries[0]:
        manifest["records"] = entries[0]["records"]
        manifest["records_source"] = entries[0]["records_source"]

    manifest_path = dest_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    log(
        f"success | dataset={args.dataset} | run={dest_dir.name} | files={len(entries)} "
        f"(skipped={len(skipped)}) | bytes={total_bytes} | sha256={manifest['sha256'][:12]}… "
        f"| dest={rel_to_root(dest_dir)}"
    )
    log(f"manifest | {rel_to_root(manifest_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
