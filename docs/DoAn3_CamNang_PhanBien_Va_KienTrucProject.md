# CẨM NANG ĐỒ ÁN 3: SPARK PROCESSING PIPELINE
## HƯỚNG DẪN ÔN TẬP PHẢN BIỆN, Ý NGHĨA TỪNG FILE & CÂU HỎI VẤN ĐÁP CỦA GIẢNG VIÊN

> **Đề tài**: Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube (113 Quốc gia)  
> **Nhóm**: YouTube Trending Analytics  
> **Học phần**: Dữ liệu Lớn (Big Data) • Buổi 8 • Checkpoint 3  
> **Commit tag**: `checkpoint-3: spark processing pipeline`

---

## PHẦN 1: BẢN ĐỒ DỰ ÁN & Ý NGHĨA CHI TIẾT TỪNG FILE

Dưới đây là cấu trúc toàn bộ repository và vai trò chính xác của từng thư mục, từng file để trả lời khi thầy hỏi *"File này để làm gì?"*:

```text
E:\bigdata-project/
├── .gitattributes                     # [LFS] Cấu hình Git LFS theo dõi manifest.json (424 MB) để git push không bị lỗi 100MB
├── .gitignore                         # Quy tắc loại bỏ file rác, dữ liệu nặng; chỉ giữ lại log, manifest và code
├── README.md                          # Tài liệu hướng dẫn cài đặt môi trường, smoke test, lệnh chạy tái lập (reproducibility)
├── task.md                            # Checklist tiến độ công việc nhóm
├── run.bat                            # [1-Click Windows] Nhấp đúp chuột để chạy pipeline PySpark Checkpoint 3 tự động
├── run.sh                             # [1-Click Linux/Mac] Script bash chạy pipeline tự động
│
├── config/
│   └── config.json                    # File cấu hình tập trung: đường dẫn raw, dim_country, output, partitions, memory
│
├── data/
│   ├── raw/                           # TẦNG RAW STORAGE (Bảo toàn dữ liệu gốc, bất biến)
│   │   ├── dim_country.csv            # [Checkpoint 3] Bảng chiều 113 quốc gia (country_code, country_name, continent, tier)
│   │   └── youtube_trending/
│   │       └── ingest_date=2026-10-20/
│   │           └── run_20261020T143013Z/
│   │               ├── trending_yt_videos_113_countries.csv  # File raw gốc 8.59 GB (6.094.047 records)
│   │               └── manifest.json                         # [424 MB] Chứa đầy đủ 100% 6.094.047 mã SHA-256 từng dòng
│   ├── sample/                        # Dữ liệu synthetic nhỏ (GBvideos.csv, USvideos.csv) để test nhanh
│   ├── work/
│   │   └── split/
│   │       └── trending_yt_videos_113_countries/             # 33 chunks CSV đã chuẩn hóa (1 dòng = 1 record)
│   │           ├── chunk_00000.csv ... chunk_00032.csv
│   │           └── split_manifest.json
│   └── processed/                     # Dữ liệu Parquet đầu ra của Checkpoint 2
│
├── src/                               # MÃ NGUỒN PIPELINE CHÍNH
│   ├── pipeline.py                    # [TRÁI TIM ĐỒ ÁN 3] Pipeline Spark End-to-End: Read -> Clean -> Hash -> Join -> Agg -> Save
│   ├── quality_report.py              # [Checkpoint 3] Module kiểm tra chất lượng dữ liệu: null counts, duplicates, unmatched
│   ├── split_csv.py                   # Chuẩn hóa CSV đa dòng thành 1 dòng/record & băm SHA-256 từng dòng
│   ├── verify_raw_records.py          # Quét đếm số record chuẩn RFC4180 và cập nhật row_hashes vào manifest.json
│   ├── ingest_file.py                 # [Checkpoint 2] Tool ingest dữ liệu vào raw storage kèm Quality Gate
│   ├── env_check.py                   # [Checkpoint 2] Smoke test kiểm tra môi trường Spark 3.5.1, Java 17, Python
│   └── dashboard.py                   # [Serve] Giao diện Streamlit + DuckDB trực quan hóa dữ liệu (NFR3 query <= 2s)
│
├── evidence/                          # BẰNG CHỨNG THỰC THI (Deliverables D5 & D6)
│   ├── explain_plan.txt               # Bằng chứng Physical Plan từ df.explain("formatted")
│   └── execution_metrics.json         # File JSON ghi nhận runtime baseline (23.13s), số dòng clean, số nhóm agg
│
├── output/                            # KẾT QUẢ ĐẦU RA (Deliverable D4)
│   ├── youtube_trending_summary/      # Thư mục Parquet nén Snappy, phân vùng theo 'continent'
│   └── preview_csv/                   # File CSV preview 50 dòng kết quả đầu ra để kiểm tra bằng mắt thường
│
├── reports/
│   └── checkpoint3.md                 # Báo cáo kỹ thuật chi tiết Checkpoint 3 theo đúng mẫu form GV yêu cầu
│
├── docs/
│   ├── Checkpoint3_Brief_Filled.docx  # File Word Brief Checkpoint 3 điền sẵn, tick đầy đủ checkbox checklist & DoD
│   ├── Checkpoint3_Report_YouTube_Trending.pptx # Slide báo cáo 6 trang chuẩn form, màu sắc tương phản cao, chữ vừa khung
│   ├── Checkpoint2_Brief_Filled.docx  # Bản brief đã nộp của Checkpoint 2
│   └── Checkpoint2_Report_YouTube_Trending.pptx # Slide đã nộp của Checkpoint 2
│
├── scripts/                           # CÁC TOOL TỰ ĐỘNG HÓA TÀI LIỆU
│   ├── build_checkpoint3_report.py    # Script sinh slide PPTX Checkpoint 3 tự động, căn chỉnh font chữ bằng PIL
│   ├── build_checkpoint3_brief.py     # Script tự động điền file Word Checkpoint 3 Brief
│   └── populate_full_manifest_hashes.py # Script trích xuất và băm toàn bộ 6.094.047 dòng ghi vào manifest.json
│
└── logs/                              # NHẬT KÝ THỰC THI (Commit để làm bằng chứng chạy thật)
    ├── env_check.txt                  # Kết quả test môi trường PASS
    ├── ingest.log                     # Lịch sử nạp file, đếm record và băm SHA-256 (105.0s)
    └── pipeline.log                   # Lịch sử chạy pipeline PySpark Checkpoint 3
```

---

## PHẦN 2: BẢNG SỐ LIỆU "THẦN THÁNH" CẦN THUỘC LÒNG

Khi thầy hỏi bất kỳ con số nào về dataset hay kết quả chạy, bạn chỉ cần trả lời chính xác các số sau:

| Chỉ số / Tham số | Con số chính xác | Ý nghĩa nghiệp vụ |
| :--- | :--- | :--- |
| **Dung lượng file Raw** | **8.591.418.141 bytes** (~8,59 GB) | File CSV thô duy nhất tải từ Kaggle (113 nước). |
| **Số dòng vật lý raw** | **134.442.959 dòng** | Do trường `description` chứa ký tự xuống dòng (`\n`). |
| **Số record thật (RFC4180)** | **6.094.047 records** | Đếm chuẩn bằng `verify_raw_records.py` trong 105.0s. |
| **Số mã SHA-256 đã băm** | **6.094.047 mã hash** | Nằm trọn vẹn trong mảng `row_hashes` của `manifest.json`. |
| **Dung lượng manifest.json**| **424,26 MB** | Chứa 100% mã hash của từng dòng theo yêu cầu của thầy. |
| **Mã hash tích lũy (Cumulative)** | `8491700c3f12a45a...` | Mã băm rolling hash xác thực tính toàn vẹn của cả tập dữ liệu. |
| **Số chunk CSV chuẩn hóa** | **33 chunks** (~256 MB/chunk) | Chuẩn hóa 1 dòng = 1 record để nạp song song vào Spark. |
| **Số dòng chạy Baseline** | **167.866 records** (chunk 0) | Tập dữ liệu mẫu kiểm chứng tính đúng đắn ở Buổi 8. |
| **Số dòng sau Clean & Filter** | **167.657 records** | Loại bỏ 209 dòng lỗi (chiếm 0,12% - do views < 0 hoặc thiếu ID). |
| **Bảng chiều Dimension** | **113 quốc gia** (`dim_country.csv`) | Mã ISO 2 ký tự, tên nước, châu lục, phân tầng thị trường. |
| **Số dòng sau Join Fact-Dim** | **167.657 records** | Giữ nguyên 100% số dòng, **không nổ dòng (0 data explosion)**. |
| **Số dòng Unmatched** | **0 bản ghi** (0,00%) | 100% quốc gia khớp với bảng chiều Dimension. |
| **Số nhóm KPI Aggregation** | **226 nhóm** | Phân theo `continent` $\times$ `country_name` $\times$ `year_month`. |
| **Runtime Baseline Spark** | **23,13 giây** | Thời gian chạy pipeline end-to-end đo đạc làm mốc đối chứng. |
| **Execution Plan Operator** | `BroadcastHashJoin` | Tối ưu bảng dimension nhỏ, không tốn shuffle qua mạng. |

---

## PHẦN 3: BỘ 10 CÂU HỎI PHẢN BIỆN CHẮC CHẮN GIẢNG VIÊN SẼ HỎI & CÁCH TRẢ LỜI ĐIỂM 10

### Câu 1: "Mỗi dòng dữ liệu đầu vào (Input Grain) và đầu ra (Output Grain) đại diện cho cái gì?"
* **Trả lời Input Grain**: 
  > *"Thưa thầy, mỗi dòng dữ liệu đầu vào (Input) đại diện cho **1 snapshot (ảnh chụp thời điểm)** của **1 video YouTube** lọt vào tab thịnh hành tại **1 quốc gia cụ thể** trong **1 ngày cụ thể** (được định danh bởi bộ 3 khóa: `video_id`, `country`, `trending_date`)."*
* **Trả lời Output Grain**:
  > *"Đầu ra (Output) sau khi tổng hợp có grain là: **1 dòng đại diện cho 1 quốc gia trong 1 tháng cụ thể thuộc 1 châu lục** (`continent` $\times$ `country_name` $\times$ `year_month`), chứa các KPI về tổng số video độc nhất, lượng view trung bình và tốc độ tăng trưởng view mỗi giờ."*

---

### Câu 2: "Pipeline của nhóm chạy từ đâu đến đâu? Có chạy tự động bằng 1 lệnh duy nhất không?"
* **Trả lời**:
  > *"Thưa thầy, pipeline của nhóm chạy end-to-end hoàn chỉnh qua 6 giai đoạn:  
  > $\text{Raw Data (CSV)} \longrightarrow \text{Read \& Schema} \longrightarrow \text{Transformations} \longrightarrow \text{Join Fact-Dim} \longrightarrow \text{Quality Gate} \longrightarrow \text{Aggregation} \longrightarrow \text{Output (Parquet/CSV)}$.  
  > Pipeline chạy hoàn toàn tự động chỉ bằng **1 lệnh duy nhất**:  
  > `python src/pipeline.py --config config/config.json`  
  > Hoặc trên Windows nhóm đã đóng gói sẵn file `run.bat`, chỉ cần nhấp đúp là toàn bộ pipeline tự chạy và sinh đầy đủ evidence."*

---

### Câu 3: "Thầy từng nhận xét thay vì hash cả file to thì hash từng dòng, nhóm đã sửa thế nào? Khác biệt là gì?"
* **Trả lời**:
  > *"Thưa thầy, nhóm đã tiếp thu trọn vẹn nhận xét của thầy và triển khai băm từng dòng ở cả 2 tầng:*
  > 
  > 1. **Tại tầng Ingestion & Raw Storage**: Thay vì dùng hàm `sha256_of(file)` băm nguyên khối file 8,59 GB, nhóm đã nâng cấp file `src/split_csv.py` và `src/verify_raw_records.py` để duyệt qua từng record và băm SHA-256 cho **toàn bộ 6.094.047 dòng**. Toàn bộ 6 triệu mã hash này đã được ghi trực tiếp vào mảng `row_hashes` trong file `manifest.json` (dung lượng 424 MB). Ngoài ra nhóm tính thêm mã băm tích lũy `cumulative_rows_hash` để kiểm tra toàn vẹn cả tập dữ liệu.
  > 2. **Tại tầng PySpark Processing Pipeline**: Trong `src/pipeline.py`, nhóm tạo thêm cột **`row_hash`** trực tiếp trong Spark bằng biểu thức:  
  > `F.sha2(F.concat_ws('||', 'video_id', 'country', 'trending_dt', 'views', 'likes', 'comment_count'), 256)`.
  > 
  > *Khác biệt lớn nhất là: Nếu băm cả file to, chỉ cần 1 dòng thay đổi là toàn bộ hash file thay đổi, không thể biết dòng nào bị sửa hay trùng lặp. Khi băm từng dòng, hệ thống có thể kiểm soát tính duy nhất (deduplication), phát hiện dòng thay đổi (Change Data Capture) và truy vết nguồn gốc (lineage) của từng bản ghi độc lập."*

---

### Câu 4: "Nhóm thực hiện những transformations nào? Lý do nghiệp vụ của từng bước là gì?"
* **Trả lời**:
  > *"Thưa thầy, nhóm thực hiện 3 bước transformation cốt lõi trong hàm `transform_trending()` của file `pipeline.py`:
  > 1. **Bước 1 - Parse Schema & Làm sạch chuỗi**:
  >    - Parse `trending_date` thành `DateType` và `publish_time` thành `TimestampType` chuẩn UTC.
  >    - Dùng regex loại bỏ emoji và chuẩn hóa khoảng trắng thừa trong `title` và `channel_title`.
  >    - Ép kiểu an toàn bằng `try_cast` sang `BigInt` cho `views`, `likes`, `comment_count`, điền giá trị 0 cho null.  
  >    *Lý do nghiệp vụ*: Đồng nhất schema để thực hiện các phép tính toán học và sắp xếp theo trục thời gian.
  > 2. **Bước 2 - Lọc dữ liệu không hợp lệ (Quality Filter)**:
  >    - Lọc bỏ các dòng có `views < 0`, `video_id` bị rỗng/null, `trending_dt` bị null hoặc thiếu mã quốc gia.  
  >    *Lý do nghiệp vụ*: Loại bỏ 209 dòng dữ liệu rác (0,12%) do lỗi thu thập từ YouTube API, bảo vệ tính đúng đắn cho các bước thống kê sau.
  > 3. **Bước 3 - Sinh mã Row Hash & Tính năng tăng trưởng (Windowing)**:
  >    - Sinh cột `row_hash` băm SHA-256 từng dòng.
  >    - Khử trùng lặp snapshot theo bộ khóa `(video_id, country, trending_dt)`.
  >    - Dùng Window Function `partitionBy(video_id, country).orderBy(trending_dt)` để tính:  
  >      $\Delta\text{views} = \text{views} - \text{prev\_views}$ và $\Delta\text{hours} = \Delta t$, từ đó tính tốc độ tăng trưởng:  
  >      $\text{views\_per\_hour} = \Delta\text{views} / \Delta\text{hours}$.  
  >    *Lý do nghiệp vụ*: Đây là chỉ số chính xác nhất để đo độ viral (bùng nổ) của một video thịnh hành."*

---

### Câu 5: "Nhóm join Fact với Dimension nào? Khóa join là gì? Có bị nổ dòng (Data Explosion) không? Chứng minh thế nào?"
* **Trả lời**:
  > *"Thưa thầy:
  > - **Bảng Fact**: Là dữ liệu video thịnh hành đã làm sạch (`fact_trending`).
  > - **Bảng Dimension**: Là bảng thông tin địa lý quốc gia (`dim_country.csv`) gồm 113 quốc gia có các trường: `country_code`, `country_name`, `continent`, `sub_region`, `market_tier`.
  > - **Phép Join**: Sử dụng **`LEFT JOIN`** với điều kiện: `fact_trending.country == dim_country.country_code`.
  > - **Chứng minh KHÔNG nổ dòng**:
  >   1. Phía bảng dimension, nhóm đã dùng hàm `duplicate_key_count(dim_df, 'country_code')` và kiểm chứng kết quả bằng 0 (113/113 mã nước là khóa chính duy nhất).
  >   2. Quan hệ giữa Fact và Dim là **Many-to-One ($M:1$)**.
  >   3. Nhóm đo đạc số dòng: `rows_before_left = 167.657`, sau khi join `rows_after_join = 167.657`. Số dòng bảo toàn tuyệt đối 100%, không phát sinh bất kỳ dòng thừa nào."*

---

### Câu 6: "Các bản ghi không khớp (Unmatched records) được xử lý ra sao? Tỷ lệ bao nhiêu?"
* **Trả lời**:
  > *"Thưa thầy, nhóm kiểm tra bằng hàm `unmatched_count(joined_df, 'country_name')` và kết quả là **0 bản ghi** (tỷ lệ unmatched là **0,00%**), chứng minh bảng dimension bao phủ trọn vẹn 100% các quốc gia xuất hiện trong dữ liệu Fact.  
  > Chính sách xử lý (Policy) của nhóm là: Sử dụng `LEFT JOIN` để đảm bảo giữ nguyên 100% dữ liệu Fact; nếu trong tương lai xuất hiện mã quốc gia mới chưa có trong dimension, hệ thống sẽ tự động điền `continent = 'Unknown'` chứ không làm mất bản ghi Fact."*

---

### Câu 7: "Kết quả Aggregation này giải quyết câu hỏi nghiệp vụ nào đã đề ra ở Đề tài 1?"
* **Trả lời**:
  > *"Thưa thầy, ở Đồ án 1 nhóm đặt ra bài toán: 'Làm thế nào để nhà sáng tạo nội dung và marketer biết được video tăng trưởng nhanh nhất ở thị trường nào và thời điểm nào?'  
  > Phép aggregation của nhóm nhóm gom nhóm theo `continent`, `country_name`, `year_month` và tính:
  > 1. `unique_videos`: Số lượng video độc nhất lọt top trending tại từng quốc gia.
  > 2. `avg_views_per_hour`: Tốc độ tăng view trung bình mỗi giờ.
  > 3. `peak_views_per_hour`: Tốc độ bứt phá kỷ lục của video đạt đỉnh.
  > 
  > Kết quả chỉ ra rõ: Vương quốc Anh (UK) và Canada dẫn đầu về tốc độ tăng trưởng view trung bình (~63.900 views/giờ), tiếp theo là UAE và Ấn Độ (~55.000 - 59.000 views/giờ). Kết quả này trả lời trực tiếp bài toán tối ưu hóa thị trường mục tiêu đã nêu trong Proposal."*

---

### Câu 8: "Baseline hôm nay đo được là bao nhiêu? Nhìn vào Execution Plan `explain('formatted')` thấy những gì? Vì sao Buổi 8 CHƯA cần tối ưu?"
* **Trả lời**:
  > *"Thưa thầy:
  > - **Mốc Baseline đo được hôm nay**: Pipeline chạy end-to-end trên máy nhóm mất **23,13 giây** (đối với chunk mẫu 167.866 dòng) và **105,0 giây** khi quét băm toàn bộ file 8,59 GB.
  > - **Phân tích Execution Plan (`evidence/explain_plan.txt`)**:
  >   1. Thấy Spark tự động dùng **`BroadcastHashJoin Inner BuildRight`** cho bảng dimension `dim_country` vì bảng này rất nhỏ (113 dòng), không tốn chi phí Shuffle mạng.
  >   2. Thấy có **2 lần Exchange (HashPartitioning)**: 1 lần khi thực hiện Window function theo `(video_id, country)` và 1 lần khi làm Aggregation theo `(continent, country_name, year_month)`.
  > - **Vì sao hôm nay chưa tối ưu**: Theo đúng chuẩn mực Big Data và rubric Buổi 8, ưu tiên số 1 của Checkpoint 3 là **Tính đúng đắn (Correctness)** và **Khả năng tái lập (Reproducibility)**. Nhóm phải có một đường chạy chuẩn không lỗi và lưu lại mốc Baseline hôm nay thì sang Buổi 9 và Buổi 10 mới có cơ sở để đo lường tỷ lệ % cải thiện hiệu năng sau khi tối ưu partition, cache và shuffle."*

---

### Câu 9: "Tại sao nhóm lại có bước chia nhỏ CSV ra 33 chunks (`split_csv.py`) mà không để Spark đọc trực tiếp file 8.59 GB?"
* **Trả lời**:
  > *"Thưa thầy, đây là một vấn đề kỹ thuật thực tế rất lớn mà nhóm đã phát hiện và xử lý:*
  > 
  > *File gốc 8,59 GB của Kaggle có cột `description` chứa các ký tự xuống dòng (`\n`) nằm bên trong dấu ngoặc kép. Nếu để Spark đọc CSV mặc định ở chế độ đa luồng (`multiLine=false`), Spark sẽ coi mỗi ký tự xuống dòng là một record mới, dẫn đến đếm sai thành 134 triệu dòng (gấp 22 lần số record thật). Còn nếu bật `multiLine=true` trên 1 file đơn lẻ 8,59 GB, Spark bắt buộc phải đọc đơn luồng (single-thread), gây nghẽn RAM và nguy cơ Out-Of-Memory (OOM).*
  > 
  > *Vì vậy, nhóm đã viết `src/split_csv.py` để parse chuẩn RFC4180 và chuẩn hóa thành 33 chunks độc lập (mỗi dòng đúng nghĩa là 1 record). Nhờ đó, Spark có thể đọc song song trên toàn bộ các core CPU với `multiLine=false`, tốc độ đọc nhanh hơn gấp nhiều lần và hoàn toàn không bao giờ bị nghẽn RAM."*

---

### Câu 10: "Kế hoạch Buổi 9 và Buổi 10 nhóm sẽ làm gì để tối ưu hiệu năng?"
* **Trả lời**:
  > *"Thưa thầy, dựa trên mốc baseline 23,13s và Execution Plan hôm nay, sang Buổi 9 và 10 nhóm sẽ thực hiện 3 kỹ thuật tối ưu:*
  > 1. **Cache / Persist**: Áp dụng `.persist(StorageLevel.MEMORY_AND_DISK)` cho DataFrame `clean_df` để tái sử dụng cho nhiều phép aggregate mà không phải tính toán lại luồng Transform từ đầu.
  > 2. **Tối ưu Shuffle Partitions**: Hiện tại Spark đang dùng giá trị cấu hình `spark.sql.shuffle.partitions = 64`. Nhóm sẽ benchmark để tìm số partition tối ưu khớp với số vCPU thực tế của máy (ví dụ 8 hoặc 16 cores) để giảm overhead quản lý task.
  > 3. **Tối ưu Partitioning khi ghi đĩa**: Đánh giá chi phí phân vùng `partitionBy('continent')` so với phân vùng theo `year_month` để tối ưu tốc độ đọc của tầng Serve (Dashboard Streamlit)."*

---

## PHẦN 4: HƯỚNG DẪN THAO TÁC DEMO TRỰC TIẾP TRƯỚC MẶT GIẢNG VIÊN (4 PHÚT)

Khi đến lượt nhóm lên pitch hoặc thầy yêu cầu mở máy kiểm tra tại bàn:

### Bước 1: Trình diễn Pipeline chạy thật (1 phút)
Mở PowerShell tại thư mục `E:\bigdata-project\` và gõ:
```powershell
.\run.bat
# Hoặc gõ lệnh:
.venv\Scripts\python.exe src\pipeline.py --config config\config.json --limit-chunks 1
```
* **Chỉ vào màn hình terminal giải thích**:
  - `[INPUT]`: Fact 167.866 dòng, Dim 113 nước.
  - `[CLEAN]`: 167.657 dòng sạch, loại 209 dòng lỗi.
  - `[ROW_HASH]`: Băm SHA-256 từng dòng thành công.
  - `[JOIN]`: Joined 167.657 dòng, không nổ dòng, 0 unmatched.
  - `[BASELINE]`: Hoàn thành trong ~23 giây.

### Bước 2: Mở Slide Thuyết trình PPTX (1 phút)
Mở file:
`docs\Checkpoint3_Report_YouTube_Trending.pptx`
* Slide có màu sắc tương phản cao, Deep Slate Navy kết hợp Royal Blue và Emerald Green, chữ nằm gọn gàng 100% trong từng card.
* Trình bày 6 slide theo đúng cấu trúc: Architecture $\rightarrow$ Input/Transform $\rightarrow$ Join/Quality $\rightarrow$ Aggregation $\rightarrow$ Baseline.

### Bước 3: Cho thầy xem các file bằng chứng (Evidence) (2 phút)
1. **Mở file manifest băm 100% từng dòng**:
   - Đường dẫn: `data\raw\youtube_trending\ingest_date=2026-10-20\run_20261020T143013Z\manifest.json`.
   - Chỉ cho thầy thấy mảng `row_hashes` chứa đầy đủ 6.094.047 chuỗi băm (file 424 MB).
2. **Mở file Execution Plan**:
   - Đường dẫn: `evidence\explain_plan.txt`.
   - Chỉ cho thầy thấy `BroadcastHashJoin Inner BuildRight` và các bước `Exchange/Window`.
3. **Mở file Word Brief điền sẵn**:
   - Đường dẫn: `docs\Checkpoint3_Brief_Filled.docx`.
   - Đã tick sẵn toàn bộ checkbox `☑` và điền chi tiết các mục A, B, C, D, E, F, G.
