# Dữ liệu Lớn – Đồ án 2 · Checkpoint 2

**Đề tài:** Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành trên YouTube (YouTube Trending Analytics)
**Pipeline:** Environment → Ingestion → Raw Storage → Transform (P3, Spark) → Serve (DuckDB/Streamlit)

| Thông tin | Giá trị |
|---|---|
| **Dataset đang chạy** | Kaggle – Trending YouTube Videos (113 Countries), **8,59 GB / 6.094.047 bản ghi / 113 quốc gia / 2023-10-26 → 2026-10-20**, ODC-By, snapshot tải 2026-10-20 |
| Plan A (mở rộng) | Illinois Data Bank – Global YouTube Trending (2022–2025), 26,4 GB / 78,4 triệu bản ghi / 104 quốc gia, CC BY 4.0, DOI `10.13012/B2IDB-9307654_V1` |
| Quy ước raw | `data/raw/<dataset>/ingest_date=YYYY-MM-DD/run_<UTC_TIMESTAMP>/` |
| Trạng thái commit | `tag: checkpoint-2` |

---

## 1. Cấu trúc repo

```
bigdata-project/
├─ README.md              ← file này
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ src/
│  ├─ env_check.py        ← smoke test môi trường (evidence ENV)
│  ├─ ingest_file.py      ← ingestion job + manifest (evidence INGEST/TRACE)
│  ├─ read_raw_sample.py  ← Spark đọc & inspect raw (evidence RAW)
│  ├─ split_csv.py        ← chuẩn hóa CSV description đa dòng → chunk (pre-P3)
│  ├─ transform.py        ← P3: Spark transform → Parquet phân vùng (FR1–FR4)
│  └─ dashboard.py        ← Serve: Streamlit + DuckDB (NFR3 query ≤ 2s)
├─ data/
│  ├─ raw/                ← raw storage (KHÔNG commit nội dung)
│  ├─ sample/             ← sample SYNTHETIC để dev (đã commit cho GV chạy thử)
│  ├─ work/               ← CSV chunk đã chuẩn hóa (derived, KHÔNG commit)
│  └─ processed/          ← Parquet đầu ra của transform (KHÔNG commit)
├─ logs/                  ← env_check.txt, ingest.log (KHÔNG commit nội dung)
├─ metadata/              ← ghi chú schema/định nghĩa cột (commit được)
└─ docs/                  ← slide, báo cáo
```

## 2. Setup môi trường (≤ 10 phút)

Yêu cầu: **Python 3.10–3.12**, **JDK 17** (đặt `JAVA_HOME`), mạng tải dependency.

```powershell
# PowerShell – kiểm tra trước
python --version      # 3.10+
java -version         # 17 (jdk)

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2b. Windows: winutils.exe *(bắt buộc khi Spark GHI file)*

Spark **đọc** file chạy bình thường nhưng **ghi Parquet sẽ lỗi** nếu thiếu winutils của Hadoop:

- `java.io.FileNotFoundException: HADOOP_HOME and hadoop.home.dir are unset`
- `java.lang.UnsatisfiedLinkError: NativeIO$Windows.access0`

Cách xử lý (mỗi máy clone repo về chạy 1 lần – thư mục `hadoop/` không được commit):

```powershell
New-Item -ItemType Directory -Force hadoop\bin | Out-Null
Invoke-WebRequest https://raw.githubusercontent.com/cdarlint/winutils/master/hadoop-3.3.6/bin/winutils.exe -OutFile hadoop\bin\winutils.exe
Invoke-WebRequest https://raw.githubusercontent.com/cdarlint/winutils/master/hadoop-3.3.6/bin/hadoop.dll -OutFile hadoop\bin\hadoop.dll
```

`src/transform.py` tự trỏ `HADOOP_HOME` + `PATH` vào `hadoop/bin` khi chạy →
không cần set biến môi trường toàn cục.

## 3. Smoke test (evidence ENV)

```powershell
python src/env_check.py
```
- **PASS** = in ra `Spark: <version>` + `Count: 1000000` + `RESULT: PASS`, process thoát mã 0.
- Output được append vào **`logs/env_check.txt`** → nộp/screenshot làm evidence.
- FAIL? Sửa theo tầng: OS/path → `java -version` + `JAVA_HOME` → `python --version`/venv → `import pyspark` → `SparkSession`.

## 4. Tải dữ liệu (evidence SOURCE) – ✅ 2026-10-20

**Đang dùng – Kaggle (Plan B):** `asaniczka/trending-youtube-videos-113-countries`, license ODC-By

```powershell
kaggle datasets download -d asaniczka/trending-youtube-videos-113-countries -p <thư mục tải>
```

| Thuật ngữ | Giá trị |
|---|---|
| File | `trending_yt_videos_113_countries.csv` |
| Snapshot tải | 2026-10-20 (dữ liệu cập nhật hằng ngày) |
| Dung lượng | 8.591.418.141 bytes (**8,59 GB**) |
| Số dòng/cột | **6.094.047 record / 18 cột / 113 quốc gia** |
| Phạm vi | `snapshot_date` 2023-10-26 → 2026-10-20 |
| SHA-256 | `4310930bd2d1…` (đầy đủ trong manifest ingest) |

> File tải về **ngoài repo**; đã ingest vào raw storage (mục 5) → data/raw KHÔNG commit.
> Plan A (Illinois 26,4 GB, DOI `10.13012/B2IDB-9307654_V1`, CC BY 4.0) giữ làm nguồn mở rộng.

## 5. Ingestion (evidence INGEST + RAW + TRACE) – ✅ đã chạy

```powershell
# ĐÃ CHẠY 2026-10-20 với file Kaggle 8,59 GB:
python src/ingest_file.py --source "E:\bigdata-project\data\raw\trending_yt_videos_113_countries.csv" --dataset youtube_trending
# -> data\raw\youtube_trending\ingest_date=2026-10-20\run_20261020T143013Z\ + manifest.json
# -> logs/ingest.log: "success | files=1 | bytes=8591418141 | sha256=4310930bd2d1…"

# Cả thư mục (vd. sau khi giải nén nhiều CSV theo quốc gia) vẫn dùng được:
python src/ingest_file.py --source "<thư mục CSV>" --dataset youtube_trending
```

Job làm gì: quality gate (tồn tại / bytes > 0 / đọc được / extension hợp lệ) → tính **SHA-256** → copy nguyên bản vào `data/raw/<dataset>/ingest_date=.../run_.../` → ghi **`manifest.json`** + append `logs/ingest.log`.

Manifest gồm: `dataset, source, ingested_at_utc, bytes, sha256, destination, status` (+ `rows_estimate` cho CSV).

## 6. Rerun behavior – câu hỏi bắt buộc của checkpoint

> *"Nếu chạy ingestion job 3 lần liên tiếp, raw storage thay đổi thế nào?"*

| Mode | Chạy lần 1 | Chạy lần 2 & 3 |
|---|---|---|
| `--on-duplicate skip` **(mặc định, idempotent)** | Tạo run mới + copy + manifest | Phát hiện `sha256` đã có → **SKIP, không tạo run mới, raw giữ nguyên**, log ghi `duplicate_skip` |
| `--on-duplicate new-run` | Tạo run mới | Vẫn tạo run mới (append) – phân biệt được bằng `run_id`, không overwrite |
| `--on-duplicate fail` | Tạo run mới | Thoát mã lỗi, không ghi gì |

→ **Trả lời ngắn:** mặc định là *skip-if-same-hash*: chạy 3 lần cùng file → raw storage **không thay đổi sau lần 1** (idempotent); file mới/có version mới (hash khác) → tạo `run_id` mới, không bao giờ overwrite. Source hỏng → fail fast, không tạo raw giả.

## 7. Spark đọc sample raw (evidence cuối buổi)

```powershell
python src/read_raw_sample.py                    # tự tìm file raw mới nhất từ manifest
python src/read_raw_sample.py --path <csv_path>  # chỉ định cụ thể
```

Output: `rows = ...`, `printSchema()`, 5 dòng đầu → copy vào slide/raw evidence.

## 8. Exit ticket (trả lời sẵn)

1. **Lệnh kiểm tra environment:** `python src/env_check.py` (kết quả trong `logs/env_check.txt`).
2. **Version/snapshot dữ liệu:** DOI `10.13012/B2IDB-9307654_V1` (Illinois, bản 2022–2025) + ghi `ingested_at_utc` và SHA-256 của từng file vào manifest.
3. **Chạy ingest 3 lần:** mặc định idempotent – hash trùng thì skip → raw không nhân bản; hash khác → run mới (append), không overwrite (xem mục 6).
4. **Rủi ro trước Buổi 7 (ĐÃ XẢY RA & ĐÃ XỬ LÝ):** Plan A 26,4 GB tải chậm → fallback Plan B Kaggle. Schema Plan B **khác** Plan A (không có `category_id`/`dislikes`, `description` nhiều dòng) → xử lý bằng **`SRC_MAP` adapter** + **`split_csv.py`**: đổi/blend nguồn không cần sửa logic FR; owner: ______.

## 9. Checklist đối chiếu rubric Checkpoint 2

- [x] ENV: `logs/env_check.txt` có `RESULT: PASS`
- [x] SOURCE: URL/DOI + snapshot + license ghi trong README/metadata
- [x] INGEST: `src/ingest_file.py` chạy ≥ 1 lần thành công
- [x] RAW: `data/raw/youtube_trending/ingest_date=2026-10-20/run_20261020T143013Z/` có file không rỗng (8,59 GB)
- [x] TRACE: `manifest.json` khớp file raw (bytes/sha256) + `logs/ingest.log`
- [x] REPO: README + commit + `tag: checkpoint-2`
- [x] (Vượt yêu cầu) P3 transform + dashboard đã chạy trên dữ liệu thật (mục 10–11)
- [ ] Mỗi thành viên trả lời được phần mình phụ trách (xem Plan & roles trong Proposal)

---

## 10. P3 – Pipeline xử lý (Transform) ✅ đã chạy trên dữ liệu thật

```powershell
# BƯỚC 0 (chỉ file CSV lớn có description nhiều dòng) – chuẩn hóa → 33 chunk:
.venv\Scripts\python.exe src\split_csv.py `
  --source "data\raw\youtube_trending\ingest_date=2026-10-20\run_20261020T143013Z\trending_yt_videos_113_countries.csv" `
  --out-dir data\work\split\trending_yt_videos_113_countries

# Transform (tự lấy run raw mới nhất; tái sử dụng chunk nếu đã có split_manifest.json):
.venv\Scripts\python.exe src\transform.py
```

Làm gì: đọc CSV — **adapter tự nhận schema nguồn** (`view_count→views`,
`country→region`, `snapshot_date→trending_date`, `publish_date→publish_time` đa định dạng;
file ≥ 64 MB tự qua `split_csv.py` → 1 dòng = 1 record, Spark đọc song song không OOM) →
drop cột nặng (`description` ≈ 8 GB giữ nguyên ở raw) → dedup theo key FR2
(**video_id + region + trending_date**) → tính **số ngày trụ hạng** và
**tốc độ tăng trưởng view** (Δviews/Δgiờ giữa hai snapshot) → Parquet phân vùng.

**Kết quả trên dữ liệu thật (2026-10-20):**

| Chỉ số | Giá trị |
|---|---|
| rows_in → rows_clean | **6.094.047 → 6.074.658** (bỏ 19.389 dòng trùng) |
| daily / summary | 6.074.658 / 1.592.208 dòng |
| Phạm vi | 113 quốc gia · snapshot 2023-10-26 → 2026-10-20 |
| Parquet daily | 341 MB (nén từ 8,59 GB CSV) |
| **Duration** | **282 s (4,7 phút) ≤ NFR2 600 s** |

```
data/processed/youtube_trending/
├─ daily/     region=US/year_month=2023-05/part-*.parquet   ← snapshot hằng ngày
├─ summary/   region=US/part-*.parquet                       ← 1 dòng/video/region
└─ _manifests/run_*.json                                     ← duration + row counts (evidence NFR2)
```

## 11. Dashboard (Serve) ✅ trên dữ liệu thật

```powershell
.venv\Scripts\streamlit.exe run src\dashboard.py
```

4 tab: 🏆 số ngày trụ hạng · 🚀 tốc độ tăng trưởng theo giờ đăng · 📺 top kênh & danh mục ·
📈 xu hướng theo ngày. Có bộ lọc region + Top N; **thời gian query hiển thị trên UI**
làm bằng chứng NFR3 (≤ 2 giây) – DuckDB đọc trực tiếp Parquet phân vùng, warm-up lúc
app khởi động để số đo là query thật.

**Đo trên dữ liệu thật (113 quốc gia):** query **19–549 ms**; AppTest: 0 exception,
5 chart — tab danh mục tự ẩn (`category_id` không có trong nguồn Kaggle).
