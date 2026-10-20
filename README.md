# Dữ liệu Lớn – Đồ án 2 · Checkpoint 2

**Đề tài:** Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành trên YouTube (YouTube Trending Analytics)
**Pipeline giai đoạn này:** Environment → Ingestion → Raw Storage
**Chưa cần:** ETL phức tạp, dashboard, ML, tối ưu Spark.

| Thông tin | Giá trị |
|---|---|
| Dataset chính (A) | Illinois Data Bank – Global YouTube Trending (2022–2025), **26,4 GB / 78,4 triệu bản ghi / 104 quốc gia**, CC BY 4.0, DOI `10.13012/B2IDB-9307654_V1` |
| Plan B (B) | Kaggle – Trending Youtube Video Statistics (113 Countries), 8,36 GB, ODC-By |
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
│  ├─ transform.py        ← P3: Spark transform → Parquet phân vùng (FR1–FR4)
│  └─ dashboard.py        ← Serve: Streamlit + DuckDB (NFR3 query ≤ 2s)
├─ data/
│  ├─ raw/                ← raw storage (KHÔNG commit nội dung)
│  ├─ sample/             ← sample SYNTHETIC để dev khi chưa tải data thật
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

## 4. Tải dữ liệu (evidence SOURCE)

**Plan A – Illinois Data Bank (26,4 GB):** truy cập `https://doi.org/10.13012/B2IDB-9307654_V1` → đăng nhập → tải `youtube_trends.tar.bz2` (qua link DOI hoặc Globus, mất vài giờ depending on mạng).
**Plan B – Kaggle (8,36 GB):**

```powershell
kaggle datasets download -d asaniczka/trending-youtube-videos-113-countries -p D:\Downloads
```

> Ghi lại: URL/DOI, ngày tải (snapshot), dung lượng file, giấy phép (CC BY 4.0 / ODC-By).
> File tải về để **ngoài repo** (data/raw không được commit – chỉ commit code + manifest/log).

## 5. Ingestion (evidence INGEST + RAW + TRACE)

```powershell
# File đơn (vd: archive tải về)
python src/ingest_file.py --source "D:\Downloads\youtube_trends.tar.bz2" --dataset youtube_trending

# Cả thư mục (vd: sau khi giải nén ra nhiều CSV theo quốc gia)
python src/ingest_file.py --source "D:\Downloads\youtube_trends" --dataset youtube_trending
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
4. **Rủi ro trước Buổi 7:** tải 26,4 GB chậm/đứt mạng → fallback Plan B Kaggle 8,36 GB (schema gần giống, không đổi pipeline); owner: ______.

## 9. Checklist đối chiếu rubric Checkpoint 2

- [ ] ENV: `logs/env_check.txt` có `RESULT: PASS`
- [ ] SOURCE: URL/DOI + snapshot + license ghi trong README/metadata
- [ ] INGEST: `src/ingest_file.py` chạy ≥ 1 lần thành công
- [ ] RAW: `data/raw/youtube_trending/ingest_date=.../run_.../` có file không rỗng
- [ ] TRACE: `manifest.json` khớp file raw (bytes/sha256) + `logs/ingest.log`
- [ ] REPO: README + commit + `tag: checkpoint-2`
- [ ] Mỗi thành viên trả lời được phần mình phụ trách (xem Plan & roles trong Proposal)

---

## 10. P3 – Pipeline xử lý (Transform) *(dựng sẵn, chờ data thật)*

```powershell
# Develop với sample synthetic trước:
.venv\Scripts\python.exe src\transform.py --input data\sample

# Chạy thật khi đã ingest xong (tự lấy run raw mới nhất từ manifest):
.venv\Scripts\python.exe src\transform.py
```

Làm gì: đọc đa file CSV (region lấy từ tên file `XXvideos.csv`) → làm sạch
(dedup, parse `YY.DD.MM`, try_cast số, strip emoji, lọc null) → tính **số ngày trụ hạng**
và **tốc độ tăng trưởng view** (Δviews/Δgiờ giữa hai snapshot) → ghi Parquet phân vùng:

```
data/processed/youtube_trending/
├─ daily/     region=US/year_month=2023-05/part-*.parquet   ← snapshot hằng ngày
├─ summary/   region=US/part-*.parquet                       ← 1 dòng/video/region
└─ _manifests/run_*.json                                     ← duration + row counts (evidence NFR2)
```

## 11. Dashboard (Serve)

```powershell
streamlit run src\dashboard.py
```

4 tab: 🏆 số ngày trụ hạng · 🚀 tốc độ tăng trưởng theo giờ đăng · 📺 top kênh & danh mục ·
📈 xu hướng theo ngày. Có bộ lọc region + Top N; **thời gian query hiển thị trên UI**
làm bằng chứng NFR3 (≤ 2 giây) – DuckDB đọc trực tiếp Parquet phân vùng.
