# Báo cáo Checkpoint 3 – Spark Processing Pipeline

## A. Thông tin nhóm
- **Tên nhóm**: YouTube Trending Analytics
- **Đề tài**: Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube (113 Quốc gia)
- **Tag/Commit**: `checkpoint-3: spark processing pipeline`
- **Môi trường**: Python 3.12 · PySpark 3.5.1 · JDK 17 · Windows 11 · Local[*] (16 GB RAM)

---

## B. Pipeline Architecture
```text
[RAW STORAGE]              [READ & SCHEMA]           [TRANSFORMATIONS]            [JOIN FACT-DIM]              [QUALITY & AGG]              [OUTPUT & BASELINE]
CSV chunks / Raw 8.59 GB ──► Explicit types   ──► 1. Parse date/time & emoji ──► Left Join dim_country ──► Quality gate checks ──► Parquet partitioned
                             Mapping SRC_MAP       2. Filter invalid rows        Key: country == code      GroupBy: continent,    (by continent)
                                                   3. Row-level SHA-256          Unique dim side           country_name, yyyy-mm  + CSV preview
                                                      + Window views_per_hour    (0 data explosion)        KPI: avg_views/hour    + explain plan
```

---

## C. Input Contract
- **Dataset Fact**: `trending_yt_videos_113_countries.csv` (chia 33 chunks chuẩn hóa tại `data/work/split/`).
- **Dataset Dimension**: `dim_country.csv` (113 quốc gia, mã ISO 2 ký tự, tên nước, châu lục, phân tầng thị trường).
- **Format**: CSV UTF-8 RFC4180.
- **Grain**: Mỗi dòng là 1 snapshot của 1 video lọt top thịnh hành tại 1 quốc gia trong 1 ngày cụ thể.
- **Khóa định danh (Key)**: `video_id`, `country`, `trending_date`.
- **Row count**:
  - Toàn bộ raw: 6.094.047 records (8,59 GB).
  - Baseline run mẫu (1 chunk chuẩn): 167.866 records.

---

## D. Transformations (≥ 3 bước)
1. **Clean & Parse Schema**:
   - Parse `trending_dt` và `publish_dt` thành định dạng DateType và TimestampType chuẩn UTC.
   - Loại bỏ emoji và chuẩn hóa khoảng trắng thừa trong `title`, `channel_title` bằng regex.
   - Ép kiểu số an toàn bằng `try_cast` cho `views`, `likes`, `comment_count`; điền giá trị mặc định 0.
2. **Filter Invalid Records**:
   - Loại bỏ các bản ghi không hợp lệ: `video_id` rỗng/null, `views < 0` hoặc null, `trending_dt` null, `country` rỗng.
   - Kết quả: Giữ lại 167.657 dòng hợp lệ, loại 209 dòng lỗi (0.12%).
3. **Row Hashing & Feature Derivation (Thực hiện nhận xét của GV)**:
   - **`row_hash`**: Tính mã băm SHA-256 cho **từng dòng** dữ liệu ngay trong Spark:
     `F.sha2(F.concat_ws("||", "video_id", "country", "trending_dt", "views", "likes", "comment_count"), 256)`.
   - Khử trùng lặp snapshot theo `(video_id, country, trending_dt)`.
   - Dùng Window Function (`partitionBy(video_id, country).orderBy(trending_dt)`) tính `views_per_hour = delta_views / delta_hours`.
   - Trích xuất `year_month` (`yyyy-MM`) và `publish_hour` (giờ đăng video).

---

## E. Join Validation (Fact – Dimension)
- **Join contract**:
  - **Left table**: `fact_trending` (Dữ liệu thịnh hành đã làm sạch).
  - **Right table**: `dim_country` (Bảng chiều thông tin quốc gia, châu lục).
  - **Join type**: `LEFT JOIN`.
  - **Join key**: `fact.country == dim.country_code`.
- **Uniqueness & Tránh nổ dòng**:
  - Phía dimension: `country_code` là khóa chính duy nhất (113 dòng unique, 0 duplicate keys).
  - Quan hệ: Many-to-One ($M:1$).
- **Row count đối chứng**:
  - `Rows before left`: 167.657
  - `Rows before right`: 113
  - `Rows after join`: 167.657 (Bảo toàn 100% số dòng, không bị nổ dòng).
  - `Unmatched records`: 0 (100% quốc gia khớp với bảng dimension).

---

## F. Aggregation & Output
- **Output grain**: `continent` $\times$ `country_name` $\times$ `year_month`.
- **Business KPI**:
  - `unique_videos`: Số lượng video khác nhau lọt top trending.
  - `total_snapshots`: Tổng số lượt xuất hiện trên tab thịnh hành.
  - `avg_views`: Lượng xem trung bình của video trending.
  - `avg_views_per_hour`: Tốc độ tăng trưởng view trung bình mỗi giờ (chỉ số đánh giá độ viral).
  - `peak_views_per_hour`: Tốc độ bứt phá view cao nhất của video đạt đỉnh.
- **Output storage**:
  - **Parquet**: `output/youtube_trending_summary/` (phân vùng theo `continent`).
  - **CSV Preview**: `output/preview_csv/` (chứa 50 bản ghi mẫu để kiểm tra nhanh).

---

## G. Quality Evidence & Baseline
- **Data Quality & Row-level Hashing (Thực hiện nhận xét của GV)**:
  - Băm SHA-256 từng dòng trên tầng Raw: Quét 134.442.959 dòng vật lý, băm trọn vẹn **6.094.047 records** trong **105.0 giây** qua `src/verify_raw_records.py`.
  - `cumulative_rows_hash`: `96ac794cf65189e9aa205e47a45199ef7dfb1e6332e4adbfd4078783de21c625` (đã lưu vết trong `manifest.json`).
  - Mẫu hash dòng đầu: `4c06bff28d09f91d6cf4dfa600e4afc2a7d43a53c88a2bc176e645ba02e7c713`.
  - Mẫu hash dòng cuối: `68c6b207ab2fa74b233992a6ed5b5de83e21b95c96996b5ff9f0adca69798d44`.
  - Băm SHA-256 từng dòng trên tầng PySpark: Sinh cột `row_hash` cho 100% bản ghi làm sạch.
  - Null rate ở các cột khóa chính: 0.0%.
  - Dimension key duplicate: 0.
  - Unmatched keys: 0.
- **Baseline Measurements**:
  - **Runtime**: **23.13 giây** (đo đạc end-to-end từ đọc raw đến lưu Parquet).
  - **Partitions**: 64 shuffle partitions -> 1 partition output sau repartition/partitionBy.
  - **Execution Plan**: Đã trích xuất và lưu tại `evidence/explain_plan.txt` (chứa chi tiết Scan, Filter, Project, BroadcastHashJoin, HashAggregate, Window, Sort).
  - **Execution Metrics**: Đã lưu tại `evidence/execution_metrics.json`.

---

## H. Blocker & Kế hoạch Buổi 9–10
- **Blocker hiện tại**: Không còn blocker về tính đúng đắn (correctness) và tính tái lập (reproducibility). Pipeline đã chạy thành công 100% bằng một lệnh.
- **Kế hoạch Buổi 9–10 (Tối ưu hóa hiệu năng dựa trên baseline hôm nay)**:
  1. Điều chỉnh `spark.sql.shuffle.partitions` phù hợp với số core CPU thực tế để giảm độ trễ shuffle.
  2. Ứng dụng `broadcast()` join tường minh cho bảng dimension `dim_country` thay vì để Spark optimizer tự suy diễn.
  3. Áp dụng `persist()` / `cache()` hợp lý khi tái sử dụng DataFrame `clean_df` cho nhiều aggregation khác nhau.
  4. Benchmark so sánh tốc độ trước và sau tối ưu dựa trên mốc baseline hôm nay.
