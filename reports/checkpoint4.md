# Báo cáo Checkpoint 4 – Benchmark & Tối ưu Pipeline

## A. Thông tin nhóm & Bối cảnh
- **Học phần**: Dữ liệu lớn (Big Data) – Buổi 10
- **Tên nhóm**: Nhóm 1 – YouTube Trending Analytics
- **Thành viên**:
  1. Trương Đình Phúc
  2. Phan Đình Bảo
  3. Trần Thị Khánh Linh
  4. Đoàn Ngọc Trân Châu
- **Đề tài**: Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube (113 Quốc gia)
- **Baseline Git commit**: `61a6456`
- **Optimized Git commit/tag**: `opt-v1.0`

---

## B. Thiết kế Benchmark (Baseline Setup)
- **Quy tắc thực nghiệm**:
  1. **Workload cố định**: 1 chunk chuẩn hóa `chunk_00000.csv` (256.0 MB, đúng 167.866 dòng thô).
  2. **Tài nguyên cố định**: Máy đơn `local[*]`, driver memory 4GB RAM, Win 11, JDK 17, Apache Spark 3.5.1.
  3. **Code path cố định**: Toàn bộ luồng xử lý từ CSV thô → Làm sạch regex & Date parsing → Băm SHA-256 từng dòng → Left Join `dim_country` → Window calculation (`views_per_hour`) → Aggregation theo (`continent`, `country_name`, `year_month`) → Ghi Parquet phân vùng.
  4. **Số lần đo**: Chạy độc lập 3 lần liên tiếp, lấy **Median** để loại trừ run-to-run variance và warm-up.

---

## C. Điểm nghẽn Hiệu năng (Bottleneck Evidence)
1. **Quan sát (Observation)**:
   - Trong cấu hình Checkpoint 3, tham số `spark.sql.shuffle.partitions` được đặt mặc định là **64**.
   - Với tập dữ liệu 1 chunk (~167.657 dòng sạch), Spark chia nhỏ shuffle thành 64 task, tức trung bình mỗi task chỉ xử lý khoảng 2.600 bản ghi (<15ms/task).
   - Chi phí điều phối của Spark Scheduler (Task Scheduling Delay, Metadata Exchange, Context Switch) trên máy cục bộ lớn hơn nhiều so với thời gian tính toán thực của CPU.
2. **Bằng chứng từ Execution Plan & Spark UI**:
   - Query Plan (`reports/explain-before.txt`) ghi nhận các toán tử trao đổi dữ liệu:
     `Exchange hashpartitioning(video_id#..., country#..., 64)` tại Stage Window và Stage GroupBy.
   - Spark UI cho thấy 64 task chạy đồng thời gây nghẽn hàng đợi luồng, chênh lệch giữa max task time và median task time đáng kể.
3. **Bottleneck Claim**:
   > *"Chúng tôi xác định điểm nghẽn chính trong pipeline hiện tại là **Scheduling Overhead** do số lượng `shuffle.partitions` (64) quá lớn so với dung lượng dữ liệu trên máy đơn `local[*]`, dẫn đến tình trạng phân mảnh task không cần thiết."*

---

## D. Giả thuyết Tối ưu (Hypothesis & Change)
- **Quy tắc thực nghiệm**: **One change at a time** (Chỉ thay đổi duy nhất một biến).
- **Mẫu giả thuyết chuẩn**:
  > *"Nếu pipeline bị chậm do scheduling overhead từ 64 shuffle partitions phân mảnh trên máy `local[*]`, thì khi giảm `spark.sql.shuffle.partitions` xuống đúng **8** (tương ứng với số core CPU vật lý của máy), tôi kỳ vọng giảm độ trễ điều phối task, loại bỏ phân mảnh metadata, giúp median runtime giảm rõ rệt (từ 15.21s xuống 8.88s), trong khi kết quả tính toán đầu ra giữ nguyên 100%."*
- **Biến thay đổi duy nhất**:
  - **Before**: `spark.sql.shuffle.partitions = 64`
  - **After**: `spark.sql.shuffle.partitions = 8`
- **Biến kiểm soát (Control)**: Cố định 100% input data, driver memory (4g), Spark version, join logic, window logic.

---

## E. Đo đạc Đối chứng (Before / After Measurement)
*Chi tiết các lần đo được lưu vết tại `reports/benchmark.csv` và `reports/benchmark_summary.json`.*

| Tiêu chí / Metric | Baseline (64 partitions) | Optimized (8 partitions) | Thay đổi ($\Delta$) | Ý nghĩa kỹ thuật |
| :--- | :---: | :---: | :---: | :--- |
| **Run 1** | 27.77 s | 9.24 s | -18.53 s | Lần chạy đầu (warm-up) |
| **Run 2** | 15.21 s | 8.32 s | -6.89 s | Chạy ổn định |
| **Run 3** | 14.44 s | 8.88 s | -5.56 s | Chạy ổn định |
| **Median Runtime** | **15.21 s** | **8.88 s** | **↓ 41.62% (-6.33 s)** | Tăng tốc đáng kể, giảm độ trễ điều phối |
| **Shuffle Partitions** | 64 partitions | 8 partitions | ↓ 87.5% | Khớp hoàn hảo với CPU cores |
| **Tasks / Shuffle Stage** | 64 tasks | 8 tasks | ↓ 56 tasks | Hạn chế context switch & metadata exchange |
| **Output Groups** | 226 nhóm KPI | 226 nhóm KPI | 0 (Bảo toàn 100%) | Đúng đắn tuyệt đối |
| **Top Video Views (KPI)** | 46.070.495 | 46.070.495 | 0 (Bảo toàn 100%) | Trùng khớp 100% |
| **Avg Views/Hour (KPI)** | 63.983,45 | 63.983,45 | 0 (Bảo toàn 100%) | Trùng khớp 100% |

---

## F. Kiểm tra Tính đúng đắn (Correctness Verification)
- **Nguyên tắc**: Tối ưu nhanh hơn nhưng sai kết quả = Regression (Thất bại).
- **Các Assertions đã kiểm chứng**:
  1. `assert input_rows_baseline == input_rows_opt`: Đúng 167.866 dòng. (**PASS**)
  2. `assert clean_rows_baseline == clean_rows_opt`: Đúng 167.657 dòng hợp lệ. (**PASS**)
  3. `assert joined_rows_baseline == joined_rows_opt`: Đúng 167.657 dòng sau join dim_country. (**PASS**)
  4. `assert summary_groups_baseline == summary_groups_opt`: Đúng 226 nhóm tổng hợp. (**PASS**)
  5. `assert top_video_views_baseline == top_video_views_opt`: Giá trị 46.070.495 lượt xem. (**PASS**)
  6. `assert avg_views_per_hour_baseline == avg_views_per_hour_opt`: 63.983,45 views/hour. (**PASS**)
- **Kết luận**: **CORRECTNESS PASS 100%**, không xảy ra bất kỳ regression nào.

---

## G. Quyết định Kỹ thuật (Technical Decision)
1. **Quyết định**: **KEEP**
   - Giữ lại cấu hình `spark.sql.shuffle.partitions = 8` cho pipeline trên môi trường máy đơn.
   - Lý do: Đem lại tốc độ xử lý nhanh hơn (+41.62%), loại bỏ lãng phí CPU scheduling và quản lý bộ nhớ đệm shuffle, trong khi tính đúng đắn được bảo toàn tuyệt đối.
2. **Giới hạn (Limitations)**:
   - Thử nghiệm được thực hiện trên môi trường máy trạm cá nhân (`local[*]`, 16GB RAM, 4GB driver memory) với 1 chunk (256 MB).
   - Khi triển khai trên cụm Spark Cluster thực tế với toàn bộ 8.59 GB (78.4 triệu bản ghi), tham số `shuffle.partitions` cần được tính toán lại theo công thức: $\text{Số partitions} = 2 \text{ đến } 3 \times \text{Tổng số executor cores}$ để tận dụng tối đa năng lực tính toán phân tán.
3. **Kế hoạch tiếp theo (Buổi 11)**:
   - Nghiên cứu tối ưu hóa định dạng lưu trữ (Parquet Snappy vs ORC vs Delta Lake).
   - Đánh giá khả năng phân vùng lưu trữ theo `continent` và `year_month` để phục vụ truy vấn Dashboard tức thời ($\le 2$ giây).
