# Checkpoint 2 – Nội dung 6 slide

> Deck: `docs/Checkpoint2_Report_YouTube_Trending.pptx` (sinh bằng `python scripts/build_checkpoint_report.py`).
> Chỉ nội dung đã làm trong Checkpoint 2: **Source → Ingestion → Raw Storage**.
> Bản brief: `docs/Checkpoint2_Brief_Filled.docx`.

## Slide 1 – Tiêu đề

- ĐỒ ÁN 2 • CHECKPOINT 2
- **Environment → Ingestion → Raw Storage**
- Nhóm: YouTube Trending Analytics
- Đề tài: Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube
- Tag: `checkpoint-2`
- Footer: Buổi 6 · 20/10/2026 | 4 thành viên

## Slide 2 – Architecture update

Sơ đồ 3 bước, không có phần P3:

```
01 Kaggle CSV        8,59 GB · 113 nước · 6.094.047 record
02 ingest_file.py    quality gate + SHA-256 · copy nguyên bản
03 Raw storage       data/raw/…/run_…/ + manifest.json
```

- Trade-off: copy nguyên bản (tốn 8,59 GB đĩa) để đổi lấy khả năng truy vết và xử lý lại từ raw.

## Slide 3 – Environment evidence

- `python src\env_check.py`
- Python 3.12.10 · Java 17.0.20.1 · Spark 3.5.1 · Count 1000000 · `RESULT: PASS (exit 0)`
- Setup: `python -m venv .venv` → `pip install -r requirements.txt` → `python src\env_check.py`
- Execution mode: `local[*]` · Windows · Spark 3.5.1 + JDK 17 · 16 GB RAM · không Docker/cluster
- Blocker đã xử lý: thiếu `winutils.exe` khi ghi Parquet → `transform.py` tự set `HADOOP_HOME` + `PATH`.

## Slide 4 – Data source & ingestion

- Source: Kaggle – Trending YouTube Videos (113 countries), license ODC-By, tải 2026-10-20
- Scale: 8.591.418.141 bytes · 6.094.047 record · 18 cột · 113 quốc gia · snapshot 2023-10-26 → 2026-10-20
- Provenance: copy nguyên bản + SHA-256 + manifest; raw không sửa 1 byte; file lớn không commit
- Evidence:
  ```
  $ python src\ingest_file.py --source <csv> --dataset youtube_trending
  success | files=1 | bytes=8591418141 | sha256=4310930bd2d1… | run_20261020T143013Z

  $ python src\verify_raw_records.py
  records=6,094,047 | physical_lines=134,442,959 | multi_line=True
  ```

## Slide 5 – Raw storage & manifest

- Path: `data/raw/youtube_trending/ingest_date=2026-10-20/run_20261020T143013Z/`
  - `trending_yt_videos_113_countries.csv` (8.591.418.141 bytes)
  - `manifest.json`
- Không sửa 1 byte · size + SHA-256 khớp manifest
- Manifest: dataset, source, ingested_at, bytes, sha256, destination, records (6094047, RFC4180), status, amendments
- Log: `logs/env_check.txt` → PASS · `logs/ingest.log` → success + duplicate_skip

## Slide 6 – Rerun, blocker & next action

- Chạy ingest 3 lần: lần 1 tạo run + copy + manifest; lần 2–3 hash trùng → SKIP, raw giữ nguyên, đúng 1 run; hash khác → run mới (append); gate fail → exit 1.
- Blocker lớn nhất: schema nguồn thiếu `category_id`, `description` nhiều dòng → Spark đếm sai 17 lần; đã xử lý bằng `SRC_MAP` + `split_csv.py` + `verify_raw_records.py`. Owner: Phúc · trước Buổi 7.
- Evidence: tag `checkpoint-2` · `manifest.json` · `logs/env_check.txt` · `logs/ingest.log` · deck + brief.
- Trước Buổi 7: ingest snapshot mới để so sánh growth 2 kỳ; chốt đề cương Đồ án 3.
