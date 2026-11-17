# Experiment Log – Checkpoint 4 Pipeline Tuning

Nhật ký theo dõi các thử nghiệm tối ưu hóa hiệu năng pipeline theo chuẩn Big Data Buổi 10.
Mỗi thử nghiệm là một bản ghi độc lập, không điều chỉnh nhiều thông số cùng lúc.

---

## Experiment 1 (E01) – Thử nghiệm Caching `clean_df`
- **Mục tiêu**: Đánh giá tác động của `clean_df.persist(StorageLevel.MEMORY_AND_DISK)` nhằm tránh tính toán lại DAG qua các action `.count()`.
- **Cấu hình**: `local[*]`, driver 4g, shuffle.partitions = 64, workload = chunk_00000.csv (256 MB).
- **Kết quả đo**:
  - Baseline Median: 15.35 s (Runs: [30.23, 15.35, 14.49])
  - Optimized Median: 22.74 s (Runs: [23.82, 22.53, 22.74])
  - Speedup: -48.14% (Chậm hơn 7.39s)
- **Phân tích nguyên nhân**:
  - `clean_df` chứa nhiều cột text và mã băm SHA-256 kích thước lớn. Chi phí tuần tự hóa (serialization) và ghi đệm vào bộ nhớ RAM/đĩa lớn hơn chi phí tính toán lại trên dữ liệu 1 chunk.
  - Phù hợp với cảnh báo trong bài học: *"Cache không phải cứ bật lên là nhanh – nếu overhead cache lớn hơn recompute thì pipeline sẽ chậm đi."*
- **Quyết định**: **REVERT**.

---

## Experiment 2 (E02) – Tối ưu Phân vùng Shuffle (Shuffle Partitions Tuning)
- **Mục tiêu**: Giảm chi phí điều phối task (Scheduling Overhead) bằng cách hạ `spark.sql.shuffle.partitions` từ 64 xuống 8 (khớp với số CPU cores vật lý).
- **Cấu hình**: `local[*]`, driver 4g, workload = chunk_00000.csv (256 MB).
- **Thay đổi duy nhất**: `spark.sql.shuffle.partitions`: 64 → 8.
- **Dấu hiệu thực thi kỳ vọng (Execution Signal)**:
  - Spark UI: Số task ở mỗi Shuffle Stage giảm từ 64 xuống 8.
  - Plan: `Exchange hashpartitioning(..., 8)`.
- **Kết quả đo**:
  - Chạy đo đối chứng 3 runs baseline vs 3 runs optimized.
  - Tính đúng đắn: 100% khớp dữ liệu, 0 lỗi regression.
- **Quyết định**: **KEEP**.
