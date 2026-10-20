# Metadata

Ghi chú tại đây (commit được):

- **Dataset**: Illinois Data Bank – Global YouTube Trending (2022–2025)
- **DOI**: 10.13012/B2IDB-9307654_V1 · **License**: CC BY 4.0
- **Quy mô**: ~26,4 GB nén (tar.bz2) / 78,4 triệu bản ghi / 104 quốc gia / 4 khung chụp mỗi ngày
- **Schema chính**: `collection_date`, `region_code`, `rank`, `video_id`, `channel_id`, `channel_title`, `title`, `category_id`, `published_at`, `view_count`, `comment_count` (+ tệp `tags`)
- **Plan B**: Kaggle `asaniczka/trending-youtube-videos-113-countries` (8,36 GB, ODC-By)
- **Lưu ý chất lượng**: trùng lặp theo (video_id, region_code, collection_date); emoji/ký tự đặc biệt trong title gây lỗi encoding.
- **Manifest**: nằm cạnh raw tại `data/raw/<dataset>/ingest_date=.../run_.../manifest.json`; log ingest tại `logs/ingest.log`.
