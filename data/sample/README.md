# Sample dữ liệu (DEV)

Hai file `USvideos.csv` / `GBvideos.csv` ở đây là **dữ liệu tổng hợp (synthetic)**,
tạo đúng schema của Kaggle `asaniczka/trending-youtube-videos-113-countries`
(16 cột, `trending_date` dạng `YY.DD.MM`, `publish_time` ISO-8601) **chỉ đểDevelop/test
pipeline khi chưa tải xong dữ liệu thật**.

Cố tình chứa case thử: video xuất hiện nhiều ngày (tính retention), views tăng giữa
các snapshot (tính growth), 1 dòng trùng lặp (test dedup), emoji trong title (test
làm sạch), ô likes trống (test null), video_id trùng nhau giữa US và GB (test
phân vùng theo region).

Khi có dữ liệu thật: chạy transform với `--input <thư mục CSV tải về>` là xong,
không cần sửa code.
