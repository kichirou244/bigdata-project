# Checkpoint 2 — Script thuyết trình 4 phút

> **Cách dùng:** mỗi slide là một khối. Lúc tập đọc cả bài; lúc lên thuyết trình chỉ liếc phần **NÓI** và **CHUYỂN**.
> Tổng: **3:55** — dư 5 giây.

## Bảng chạy nhanh

| Mốc | Slide | Người | Trên màn hình |
|---|---|---|---|
| 0:00 | 1 | Bảo | Slide 1 |
| 0:15 | 2 | Phúc | Slide 2 — chỉ tay 3 ô |
| 0:50 | 3 | Bảo | Slide 3 |
| 1:25 | 4 | Phúc | Slide 4 + `logs/ingest.log` |
| 2:20 | 5 | Linh | Slide 5 + mở `manifest.json` |
| 3:05 | 6 | Linh → Châu | Slide 6 |

## Số liệu nói miệng (chỉ cần nhớ cột trái)

| Nói miệng | Giá trị thật trên slide |
|---|---|
| "8,59 GB" | 8.591.418.141 bytes |
| "hơn 6 triệu record" / "6.094.047 record" | 6.094.047 |
| "134 triệu dòng vật lý" | 134.442.959 |
| "run ngày 20 tháng 10" | `run_20261020T143013Z` |
| "mã hash khớp manifest" | `sha256 4310930bd2d1…` |

> Không đọc mã hash, không đọc đường dẫn dài. Chỉ nói "khớp manifest".

---

## SLIDE 1 — 0:00–0:15 · Bảo

**Màn hình:** slide 1.

**NÓI:**
1. Em chào thầy và cả lớp. Nhóm em là YouTube Trending Analytics, bốn thành viên.
2. Đề tài: phân tích xu hướng và tốc độ tăng trưởng video thịnh hành trên YouTube.
3. Báo cáo Checkpoint 2 gồm ba phần: môi trường, ingestion và raw storage. Code đã tag `checkpoint-2`.

**CHUYỂN:** "Mời thầy xem kiến trúc nhóm em đã chạy."

---

## SLIDE 2 — 0:15–0:50 · Phúc

**Màn hình:** slide 2. Chỉ tay lần lượt vào ô 01 → 02 → 03.

**NÓI:**
1. Đây là kiến trúc nhóm em **đã chạy thật**, không phải sơ đồ kế hoạch.
2. Bước một: file CSV từ Kaggle — 8,59 GB, 113 quốc gia, hơn 6 triệu record.
3. Bước hai: script ingest kiểm tra file, tính SHA-256 rồi copy nguyên bản.
4. Bước ba: lưu vào raw storage theo ngày và theo run, kèm `manifest.json`.

**CHỐT:** "Bọn em chọn copy nguyên bản — tốn 8,59 GB đĩa — để đổi lấy khả năng truy vết và xử lý lại từ raw."

**CHUYỂN:** "Để chứng minh chạy được, mời thầy xem phần môi trường."

---

## SLIDE 3 — 0:50–1:25 · Bảo

**Màn hình:** slide 3.

**NÓI:**
1. Môi trường chỉ cần một lệnh: `python src/env_check.py`.
2. Kết quả **PASS**: Python 3.12, Java 17, Spark 3.5.1; phép đếm thử một triệu dòng ra đúng một triệu.
3. Nhóm chạy local trên Windows, 16 GB RAM — không Docker, không cluster.
4. Lỗi đã xử lý: Spark thiếu `winutils` khi ghi Parquet, nên script tự trỏ `HADOOP_HOME` và `PATH`.

**CHUYỂN:** "Môi trường ổn rồi, phần tiếp theo là dữ liệu và cách ingest."

---

## SLIDE 4 — 1:25–2:20 · Phúc

**Màn hình:** slide 4.

**NÓI:**
1. Nguồn là bộ Trending YouTube Videos 113 countries trên Kaggle, license ODC-By, tải ngày 20 tháng 10.
2. Quy mô: 8,59 GB, hơn 6 triệu record, 18 cột, 113 quốc gia.
3. Lệnh ingest chạy thành công: một file, có SHA-256 và run ID.
4. Nhóm đếm lại bằng script riêng theo chuẩn RFC 4180: đúng 6.094.047 record.
5. File có 134 triệu dòng vật lý vì cột `description` nhiều dòng. Đọc CSV kiểu mặc định thì Spark đếm sai 17 lần, nên nhóm chuẩn hóa trước khi đọc.
6. Raw giữ nguyên một byte; file lớn không commit, chỉ commit manifest và log.

**NẾU BỊ HỎI "SAO KHÔNG DÙNG MULTILINE?":** "Multiline bắt Spark nạp nguyên file 8,59 GB vào một task — máy 16 GB sẽ OOM. Tách trước vừa đúng, vừa đọc song song được."

**CHUYỂN:** "Vậy raw storage được tổ chức thế nào?"

---

## SLIDE 5 — 2:20–3:05 · Linh

**Màn hình:** slide 5. Mở `manifest.json` khi nói đến dòng thứ ba.

**NÓI:**
1. Đây là đường dẫn thật: raw, dataset youtube_trending, ngày 20 tháng 10, run 14 giờ 30.
2. Trong đó có file CSV 8,59 GB và `manifest.json`.
3. Manifest ghi nguồn, thời điểm, số byte, mã hash, nơi lưu, số record và trạng thái.
4. Kích thước và mã hash khớp một-một với file trên đĩa, nên truy ngược được từng byte.
5. Log có `env_check` PASS và `ingest` success, kèm `duplicate_skip`.

**CHỐT:** "Mời thầy xem manifest thật ạ."

**CHUYỂN:** "Phần cuối là chạy lại và blocker."

---

## SLIDE 6 — 3:05–3:55 · Linh → Châu

**Màn hình:** slide 6.

### Linh — Rerun (khoảng 25 giây)

**NÓI:**
1. Câu hỏi checkpoint: chạy ingest ba lần thì raw thế nào? Nhóm em chạy thật ba lần.
2. Lần một: tạo run và copy file.
3. Lần hai, lần ba: hash trùng nên bỏ qua — raw vẫn đúng một run, tức là idempotent.
4. Nếu hash khác: tạo run mới, không ghi đè. Nếu file nguồn lỗi: thoát mã 1, không tạo raw giả.

**BÀN GIAO:** "Phần blocker, mời bạn Châu."

### Châu — Blocker & next (khoảng 25 giây)

**NÓI:**
1. Blocker lớn nhất: nguồn lệch schema đề cương — thiếu `category_id`, `description` nhiều dòng. Nhóm đã xử lý bằng `SRC_MAP`, `split_csv` và `verify_raw_records`. Bạn Phúc phụ trách, trước Buổi 7.
2. Trước Buổi 7: ingest thêm một snapshot để so growth hai kỳ, và chốt đề cương Đồ án 3.
3. Bằng chứng: tag `checkpoint-2`, manifest, log, deck và brief. Em xin hết ạ.

---

## Nếu bị hỏi

| Câu hỏi | Trả lời trong 1 hơi | Người |
|---|---|---|
| Một lệnh kiểm tra môi trường? | `python src/env_check.py` — PASS, log ở `logs/env_check.txt`. | Bảo |
| Xác định version/snapshot bằng gì? | Ngày tải + SHA-256 + `snapshot_date` trong manifest; hash trùng là cùng version. | Phúc |
| Chạy ingest 3 lần thì sao? | Lần 1 ghi, lần 2–3 skip do hash trùng — vẫn 1 run, idempotent. | Linh |
| Rủi ro lớn nhất? | Nguồn cập nhật hằng ngày nên snapshot đổi; Phúc xử lý trước Buổi 7. | Châu |
| Sao không dùng HDFS/cluster? | Batch 8,59 GB trên 1 máy 16 GB; local + manifest đủ và dễ tái tạo hơn. | Phúc |

> Không biết thì nói: "Phần này bạn … phụ trách, bạn trả lời giúp ạ." Đừng đoán.

## 3 lỗi cần tránh

1. **Đọc chữ trên slide** → chỉ nói 1 ý mỗi slide, số liệu để trên slide.
2. **Nói "máy em chạy được"** → mở log hoặc manifest cho thầy xem.
3. **Sa vào giải thích Spark/Parquet** → chỉ trả lời khi được hỏi.

## Nếu trễ giờ, cắt theo thứ tự

1. Bỏ câu trade-off ở slide 2.
2. Bỏ phần "Trước Buổi 7" ở slide 6.
3. Rút gọn manifest ở slide 5 còn: "hash và size khớp file trên đĩa".

Giữ lại bằng mọi giá: **PASS môi trường**, **6.094.047 record**, **chạy 3 lần vẫn 1 run**, **blocker + owner**.
