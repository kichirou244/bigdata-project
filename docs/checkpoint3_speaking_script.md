# KỊCH BẢN THUYẾT TRÌNH CHECKPOINT 3 (PITCH 4 PHÚT)
**Đề tài**: Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube (113 Quốc gia)  
**Thời lượng**: ~35–45 giây / slide • Tổng: ~3,5 – 4 phút.

---

### SLIDE 1: TIÊU ĐỀ & MỤC TIÊU (30 giây)
> *"Kính chào thầy và các bạn, hôm nay nhóm YouTube Trending Analytics xin báo cáo Checkpoint 3: **Xây dựng Spark Processing Pipeline**.*  
> *Mục tiêu trọng tâm của nhóm hôm nay là: **Chứng minh pipeline chạy end-to-end hoàn chỉnh bằng một lệnh duy nhất**, bảo đảm tính đúng đắn về mặt dữ liệu, đã khắc phục nhận xét của thầy về **băm SHA-256 từng dòng**, và đo đạc mốc **Baseline ban đầu** để chuẩn bị cho việc tối ưu ở Buổi 9 và 10."*

---

### SLIDE 2: PIPELINE ARCHITECTURE (45 giây)
> *"Trên màn hình là kiến trúc luồng dữ liệu thực tế đang chạy trên Spark:*  
> *1. **Input**: Nhóm nạp dữ liệu từ 33 file CSV đã chuẩn hóa (tổng 6,09 triệu records từ 113 quốc gia).*  
> *2. **Processing**: Dữ liệu đi qua tầng ép kiểu và ánh xạ schema, thực hiện 3 bước transformation, sau đó **LEFT JOIN** với bảng chiều quốc gia `dim_country` và chạy qua bộ lọc kiểm tra chất lượng (Quality Gate).*  
> *3. **Output**: Dữ liệu được gom nhóm tính toán KPI theo tháng và ghi ra định dạng **Parquet** phân vùng theo châu lục (`continent`), kèm theo file CSV preview 50 dòng để kiểm tra nhanh.*  
> *Toàn bộ quy trình chạy tự động qua file `src/pipeline.py` hoặc file `run.bat` một chạm."*

---

### SLIDE 3: INPUT CONTRACT & TRANSFORMATIONS (45 giây)
> *"Ở Slide này là hợp đồng dữ liệu và các bước biến đổi:*  
> *- **Input Grain**: Mỗi dòng là 1 snapshot của 1 video tại 1 quốc gia trong 1 ngày, định danh bởi bộ 3 khóa `(video_id, country, trending_date)`.*  
> *- **3 Transformations nghiệp vụ**:*  
> *  1. Parse chuẩn ngày giờ UTC, dùng Regex loại bỏ emoji trong tiêu đề và `try_cast` an toàn các cột số.*  
> *  2. Lọc bỏ 209 dòng lỗi (0,12%) có views âm hoặc thiếu ID.*  
> *  3. **Đặc biệt, theo nhận xét của thầy ở Checkpoint 2**: Nhóm đã bổ sung hàm băm **SHA-256 từng dòng (`row_hash`)** cho toàn bộ dữ liệu, đồng thời dùng Window function tính tốc độ bùng nổ `views_per_hour = delta_views / delta_hours`.*  
> *- **Kết quả**: Từ 167.866 dòng input mẫu, làm sạch còn 167.657 dòng hợp lệ."*

---

### SLIDE 4: JOIN FACT-DIMENSION & DATA QUALITY (45 giây)
> *"Tiếp theo là chứng minh phép Join không làm sai lệch hay nổ dòng dữ liệu:*  
> *- **Join Contract**: Nhóm thực hiện `LEFT JOIN` giữa Fact và bảng `dim_country.csv` (113 quốc gia) theo mã `country_code`.*  
> *- **Chứng minh không nổ dòng**: Phía Dimension có 113/113 mã nước là duy nhất 100% (0 duplicate). Quan hệ là $M:1$. Số dòng trước và sau khi join đều là **167.657 dòng** (bảo toàn tuyệt đối, 0 dòng thừa).*  
> *- **Quality Evidence**: Số dòng unmatched là **0 dòng (0,00%)**; tỷ lệ Null ở các cột khóa là 0%.*  
> *- **Về mặt vận hành**: File raw gốc 8,59 GB đã được băm SHA-256 từng dòng cho toàn bộ **6.094.047 records** trong 97,9s và lưu trọn vẹn trong file `manifest.json` (424 MB)."*

---

### SLIDE 5: AGGREGATION & OUTPUT STORAGE (45 giây)
> *"Slide 5 thể hiện kết quả tổng hợp trả lời bài toán trong đề cương Đồ án 1:*  
> *- **Output Grain**: 1 dòng đại diện cho 1 quốc gia trong 1 tháng cụ thể thuộc 1 châu lục.*  
> *- **KPI nghiệp vụ**: Tính tổng số video độc nhất (`unique_videos`) và tốc độ tăng trưởng view mỗi giờ (`avg_views_per_hour`).*  
> *- **Kết quả phân tích**: Nhóm phát hiện ra các thị trường có tốc độ viral nhanh nhất thế giới là **Anh (UK)** và **Canada** (~63.900 views/giờ), kế tiếp là **UAE** và **Ấn Độ** (~55.000–59.000 views/giờ).*  
> *- **Lưu trữ**: Toàn bộ 226 nhóm KPI đã được ghi đè (`overwrite`) thành công vào thư mục Parquet phân vùng theo `continent`."*

---

### SLIDE 6: BASELINE, EXPLAIN PLAN & KẾ HOẠCH (40 giây)
> *"Cuối cùng là mốc đối chứng Baseline làm đầu vào cho Buổi 9 và 10:*  
> *- **Runtime Baseline**: Pipeline hoàn thành toàn bộ quy trình trong **23,13 giây**.*  
> *- **Phân tích Physical Plan (`explain_plan.txt`)**: Spark tự động áp dụng `BroadcastHashJoin Inner BuildRight` cho bảng Dimension 113 nước nên không tốn chi phí shuffle qua mạng. Tuy nhiên, vẫn còn **2 bước Exchange (Shuffle)** khi làm Window và Aggregation.*  
> *- **Kế hoạch Buổi 9–10**: Dựa trên mốc 23,13s hôm nay, nhóm sẽ:*  
> *  1. Cài đặt `persist()` / `cache()` cho bảng Fact sạch.*  
> *  2. Tinh chỉnh `shuffle.partitions` tối ưu theo số lõi CPU.*  
> *  3. Đo lường tỷ lệ % cải thiện tốc độ so với baseline.*  
> *Xin cảm ơn thầy và các bạn đã lắng nghe!"*
