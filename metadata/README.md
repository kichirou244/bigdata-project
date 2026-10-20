# Metadata

## Nguồn đang chạy (Checkpoint 2 – đã ingest)

- **Dataset**: Kaggle – Trending YouTube Videos (113 Countries), `asaniczka/trending-youtube-videos-113-countries`
- **License**: ODC-By · **Snapshot tải**: 2026-10-20 (nguồn cập nhật hằng ngày)
- **Quy mô**: 8.591.418.141 bytes (8,59 GB) / **6.094.047 bản ghi / 18 cột / 113 quốc gia**
- **Phạm vi thời gian**: `snapshot_date` 2023-10-26 → 2026-10-20
- **SHA-256**: `4310930bd2d1…` (đầy đủ trong manifest ingest)
- **File gốc**: `trending_yt_videos_113_countries.csv` (single combined CSV)
- **Schema thực tế**: `title, channel_name, daily_rank, daily_movement, weekly_movement,
  snapshot_date, country, view_count, like_count, comment_count, description, thumbnail_url,
  video_id, channel_id, video_tags, kind, publish_date, langauge` (typo `langauge` là của nguồn)
- **Lưu ý chất lượng**:
  - `description` chứa newline bên trong nháy kép → bắt buộc qua `src/split_csv.py`
    (1 dòng = 1 record) trước khi Spark đọc;
  - **không có `category_id` / `dislikes`** → transform để NULL, dashboard bỏ qua tab danh mục;
  - `publish_date` dạng `2026-10-09 00:00:00+00:00` → transform parse đa định dạng (cả
    định dạng cũ `2017-11-13T16:08:22.000Z` của Kaggle classic vẫn đọc được).
- **Ánh xạ schema** (`SRC_MAP` trong `transform.py`): `country→region`, `snapshot_date→trending_date`,
  `channel_name→channel_title`, `view_count→views`, `like_count→likes`,
  `video_tags→tags`, `thumbnail_url→thumbnail_link`, `publish_date→publish_time`.

## Plan A (nguồn mở rộng, chưa tải)

- **Illinois Data Bank** – Global YouTube Trending (2022–2025)
- **DOI**: 10.13012/B2IDB-9307654_V1 · **License**: CC BY 4.0
- **Quy mô đề xuất**: ~26,4 GB nén / 78,4 triệu bản ghi / 104 quốc gia / 4 khung chụp mỗi ngày
- **Schema chính**: `collection_date`, `region_code`, `rank`, `video_id`, `channel_id`,
  `channel_title`, `title`, `category_id`, `published_at`, `view_count`, `comment_count` (+ tệp `tags`)

## Truy vết

- **Manifest**: cạnh raw tại `data/raw/<dataset>/ingest_date=.../run_.../manifest.json`
  (sha256, bytes, kích thước file, thời điểm ingest).
- **Split manifest**: `data/work/split/<tên_file>/split_manifest.json`
  (số record, số chunk, bytes, duration).
- **Transform manifest**: `data/processed/youtube_trending/_manifests/run_*.json`
  (rows_in/clean/dropped, duration – evidence NFR2).
- **Log**: `logs/env_check.txt`, `logs/ingest.log`, `logs/transform.log`.
