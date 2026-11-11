"""Ghi toàn bộ 6.094.047 mã SHA-256 từng dòng vào manifest.json theo yêu cầu của GV."""
from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_DIR = ROOT / "data" / "work" / "split" / "trending_yt_videos_113_countries"
MANIFEST_PATH = ROOT / "data" / "raw" / "youtube_trending" / "ingest_date=2026-10-20" / "run_20261020T143013Z" / "manifest.json"


def main():
    print(f"[START] Collecting all row hashes from: {CHUNKS_DIR}")
    t0 = time.perf_counter()
    chunk_files = sorted(CHUNKS_DIR.glob("chunk_*.csv"))
    if not chunk_files:
        raise SystemExit(f"No chunk files found in {CHUNKS_DIR}")

    all_hashes = []
    cum_hasher = hashlib.sha256()

    for idx, cf in enumerate(chunk_files):
        with cf.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            _ = next(reader)  # skip header
            for row in reader:
                rec_str = ",".join(row)
                h = hashlib.sha256(rec_str.encode("utf-8")).hexdigest()
                cum_hasher.update(h.encode("ascii"))
                all_hashes.append(h)
        if (idx + 1) % 5 == 0 or idx == len(chunk_files) - 1:
            print(f"  ... processed chunk {idx+1}/{len(chunk_files)} -> {len(all_hashes):,} hashes ({time.perf_counter()-t0:.1f}s)")

    total_records = len(all_hashes)
    cumulative_hash = cum_hasher.hexdigest()
    print(f"[DONE HASHING] Total records: {total_records:,} in {time.perf_counter()-t0:.1f}s | Cumulative: {cumulative_hash[:16]}...")

    # Load existing manifest metadata
    base_meta = {}
    if MANIFEST_PATH.exists():
        try:
            raw_text = MANIFEST_PATH.read_text(encoding="utf-8")
            base_meta = json.loads(raw_text)
            # Remove any previous huge row_hashes list before updating
            if "row_hashing" in base_meta:
                base_meta["row_hashing"].pop("row_hashes", None)
            if "files" in base_meta and len(base_meta["files"]) > 0:
                if "row_hashing" in base_meta["files"][0]:
                    base_meta["files"][0]["row_hashing"].pop("row_hashes", None)
        except Exception:
            pass

    # Stream write manifest.json with all row hashes
    print(f"[WRITING] Writing full manifest to {MANIFEST_PATH} ...")
    t1 = time.perf_counter()

    with MANIFEST_PATH.open("w", encoding="utf-8") as mf:
        mf.write("{\n")
        mf.write('  "dataset": "youtube_trending",\n')
        mf.write('  "run_id": "run_20261020T143013Z",\n')
        mf.write(f'  "source": {json.dumps(base_meta.get("source", str(ROOT / "data/raw/trending_yt_videos_113_countries.csv")))},\n')
        mf.write('  "ingested_at_utc": "2026-10-20T14:30:13+00:00",\n')
        mf.write('  "bytes": 8591418141,\n')
        mf.write('  "sha256": "4310930bd2d18b66710249c3f33b2a6c0b627b61a1a65dc7e9a9a990d548ac12",\n')
        mf.write('  "destination": "data\\\\raw\\\\youtube_trending\\\\ingest_date=2026-10-20\\\\run_20261020T143013Z",\n')
        mf.write('  "status": "success",\n')
        mf.write('  "on_duplicate": "skip",\n')
        mf.write(f'  "records": {total_records},\n')
        mf.write('  "records_source": "rfc4180_counter",\n')
        mf.write('  "records_columns": 18,\n')
        mf.write('  "row_hashing_strategy": "sha256_per_record",\n')
        mf.write(f'  "cumulative_rows_hash": "{cumulative_hash}",\n')
        mf.write('  "note": "File manifest chứa toàn bộ 100% mã SHA-256 từng dòng theo yêu cầu của GV",\n')
        mf.write('  "row_hashes": [\n')

        # Stream the 6M hashes
        for i, h in enumerate(all_hashes):
            comma = "," if i < total_records - 1 else ""
            mf.write(f'    "{h}"{comma}\n')

        mf.write("  ]\n")
        mf.write("}\n")

    manifest_size_mb = MANIFEST_PATH.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Manifest updated: {manifest_size_mb:.2f} MB in {time.perf_counter()-t1:.1f}s")


if __name__ == "__main__":
    main()
