# Checkpoint 2 – Nội dung 6 slide (điền vào template PPTX)

> Chèn vào `BigData_Buoi06_DoAn2_Checkpoint2_Report_Template.pptx`, ≤ 4 phút.
> Số liệu lấy từ evidence thật: `logs/`, `_manifests/`, tag `checkpoint-2`.

---

## SLIDE 1 – Tiêu đề

- **Đề tài:** Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube
  (YouTube Trending Analytics)
- **Nhóm:** _________________________ (Lớp: __________)
- **Thành viên & vai trò:**
  - Phan Đình Bảo – Môi trường + Ingestion (src/env_check.py, src/ingest_file.py)
  - Trương Đình Phúc – Spark transform (src/split_csv.py, src/transform.py)
  - Trần Thị Khánh Linh – Parquet phân vùng + DuckDB (schema, query)
  - Đoàn Ngọc Trân Châu – Dashboard Streamlit + tài liệu (src/dashboard.py, README)
- **Git:** commit `fb4c171` · **tag `checkpoint-2`** · repo có README evidence checklist

---

## SLIDE 2 – Architecture update (phần ĐÃ triển khai)

```
[Kaggle 8,59 GB CSV] → ingest_file.py → raw/ (copy + SHA-256 manifest)
        → split_csv.py (chuẩn hóa description đa dòng → 33 chunk)
        → Spark 3.5.1 local[*] (adapter schema, dedup FR2, FR3)
        → Parquet partition region/year_month (daily + summary, 341 MB)
        → DuckDB (NFR3 19–549 ms) → Streamlit dashboard
```

- **Technology:** Python 3.12 · JDK 17 · PySpark 3.5.1 (local[*]) · DuckDB · Streamlit · Parquet
- **Trade-off chính:** máy cá nhân 16 GB RAM → dùng local mode + pre-split CSV
  (1 dòng = 1 record) thay vì `multiLine=true` (phải nạp cả file 8 GB vào 1 task → OOM);
  drop cột `description` (~8 GB) khỏi tầng metric, raw vẫn giữ nguyên vẹn.

---

## SLIDE 3 – Environment evidence

- **EVIDENCE** (dán output `logs/env_check.txt`):
  - Python 3.12.x · Java 17 (Temurin) · PySpark 3.5.1 · Parquet ghi/đọc OK → `RESULT: PASS`
- **SETUP COMMAND:**
  ```
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  .venv\Scripts\python.exe src\env_check.py
  ```
- **EXECUTION MODE:** `local[*]` trên Windows (winutils Hadoop 3.3.6 cho Parquet-write, xem README 2b)
- **BLOCKER:** đã qua — winutils/hadoop.dll thiếu → tự cấu hình `HADOOP_HOME` + `PATH`
  trong `transform.py` (không cần cài Hadoop hệ thống).

---

## SLIDE 4 – Data source & ingestion

- **SOURCE:** `kaggle.com/datasets/asaniczka/trending-youtube-videos-113-countries` ·
  license **ODC-By** · snapshot **2026-10-20** (nguồn tự cập nhật hằng ngày)
- **SCALE / VERSION:** **8.591.418.141 bytes (8,59 GB)** · **6.094.047 bản ghi / 18 cột / 113 quốc gia** ·
  `snapshot_date` 2023-10-26 → 2026-10-20 · SHA-256 `4310930bd2d1…` (trong manifest)
- **PROVENANCE:** file gốc giữ ngoài repo; ingest = copy + hash + ghi manifest
  (bytes, sha256, thời điểm) → truy ngược được nguồn của từng byte trong raw.
- **COMMAND + RESULT** (dán `logs/ingest.log`):
  ```
  python src\ingest_file.py --source "...trending_yt_videos_113_countries.csv" --dataset youtube_trending
  → success | files=1 | bytes=8591418141 | sha256=4310930bd2d1… | run_20261020T143013Z
  ```

---

## SLIDE 5 – Raw storage & manifest

- **Path + convention:**
  ```
  data/raw/youtube_trending/ingest_date=2026-10-20/run_20261020T143013Z/
  ├─ trending_yt_videos_113_countries.csv   (8.591.418.141 bytes)
  └─ manifest.json                          (status: success)
  ```
- **Manifest fields:** `dataset, source, ingest_date, run_id, files[{name, bytes, sha256}],
  total_bytes, started/finished_utc, status` → khớp 1-1 với file trên đĩa.
- **Minh chứng đọc lại:** `python src\read_raw_sample.py` → Spark đọc được schema,
  số dòng, 5 dòng đầu từ chính file trong raw.
- **Bổ sung P3:** `data/work/split/.../split_manifest.json` (6.094.047 record → 33 chunk,
  204,8 s) và `data/processed/.../_manifests/run_*.json` (duration 282 s ≤ NFR2).

---

## SLIDE 6 – Rerun, blocker, next action

- **RERUN** (chạy 3 lần cùng file, `--on-duplicate skip` mặc định):
  - Lần 1: tạo run + copy + manifest · Lần 2 & 3: hash trùng → **SKIP**, raw giữ nguyên
    (log `duplicate_skip`) → **idempotent**;
  - file hash khác → run mới (append, không overwrite) · file hỏng → fail-fast, không tạo raw giả.
- **BLOCKER lớn nhất:** nguồn Plan B có schema khác đề cương (không `category_id`, `description`
  nhiều dòng) → giải pháp adapter `SRC_MAP` + `split_csv.py`; **owner: Phúc** (xong 2026-10-20).
- **EVIDENCE links:** README mục 1–11 · `logs/*.log` · `_manifests/*.json` · tag `checkpoint-2`.
- **TRƯỚC BUỔI 7:** chạy ingest snapshot mới (dữ liệu cập nhật hằng ngày) để so sánh
  growth giữa 2 snapshot; demo dashboard trực tiếp; chốt slide cuối Đồ án 3 (kế hoạch ML/Nâng cao).
