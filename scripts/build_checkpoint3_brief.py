"""Sinh bản Checkpoint 3 Brief đã điền từ template của GV (không sửa template gốc)."""
from __future__ import annotations

import shutil
from pathlib import Path

import docx
from docx.shared import Pt, Inches, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(r"D:\Edu\BD\BigData_DoAn3_Brief_Checkpoint3_Template.docx")
OUT = ROOT / "docs" / "Checkpoint3_Brief_Filled.docx"

TEAM_TEXT = (
    "YouTube Trending Analytics – 4 thành viên:\n"
    "  • Phan Đình Bảo – Môi trường & Ingestion (env_check.py, ingest_file.py, verify_raw_records.py)\n"
    "  • Trương Đình Phúc – Spark Processing Pipeline (pipeline.py, split_csv.py, quality_report.py)\n"
    "  • Trần Thị Khánh Linh – Parquet Storage & Dimension Modeling (dim_country.csv, schema)\n"
    "  • Đoàn Ngọc Trân Châu – Dashboard Streamlit & Tài liệu (dashboard.py, báo cáo Checkpoint 3)"
)


def fill_cell(cell, text: str, font_size: float = 9.5, bold: bool = False, color=None) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(font_size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color


def build_brief():
    if not TEMPLATE.exists():
        raise SystemExit(f"Không tìm thấy template: {TEMPLATE}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE, OUT)
    doc = docx.Document(str(OUT))

    # 1. Tick checkboxes in paragraphs
    for p in doc.paragraphs:
        if "☐" in p.text:
            for r in p.runs:
                if "☐" in r.text:
                    r.text = r.text.replace("☐", "☑")

    # 2. Fill Table 6 (A. Thông tin nhóm)
    table_6_text = (
        "A. THÔNG TIN NHÓM\n"
        f"• Tên nhóm: YouTube Trending Analytics\n"
        f"• Thành viên:\n{TEAM_TEXT}\n"
        "• Git tag / commit: checkpoint-3: spark processing pipeline\n"
        "• Môi trường: PySpark 3.5.1 · Python 3.12 · JDK 17 · Windows 11 · Local[*] (16 GB RAM)"
    )
    fill_cell(doc.tables[6].rows[0].cells[0], table_6_text, font_size=9.5)

    # 3. Fill Table 7 (B. Input contract)
    table_7_text = (
        "B. INPUT CONTRACT\n"
        "• Dataset Fact: Kaggle - Trending YouTube Videos (113 Countries) · 8.59 GB CSV thô\n"
        "• Dataset Dimension: dim_country.csv (113 quốc gia, mã ISO 2 ký tự, tên nước, châu lục)\n"
        "• Format: CSV UTF-8 RFC4180 (đã chuẩn hóa phân đoạn chunk tại data/work/split/)\n"
        "• Quy mô: 6.094.047 raw rows (full) | Run mẫu kiểm chứng: 167.866 rows (1 chunk)\n"
        "• Grain: 1 snapshot của 1 video lọt top thịnh hành tại 1 quốc gia trong 1 ngày\n"
        "• Khóa định danh: video_id, country, trending_date"
    )
    fill_cell(doc.tables[7].rows[0].cells[0], table_7_text, font_size=9.5)

    # 4. Fill Table 8 (C. Transformations)
    table_8_text = (
        "C. TRANSFORMATIONS (≥ 3 BƯỚC CÓ LÝ DO NGHIỆP VỤ)\n"
        "1. Parse & Clean Schema:\n"
        "   - Parse trending_dt (DateType) và publish_dt (TimestampType) chuẩn UTC.\n"
        "   - Regex loại bỏ emoji và chuẩn hóa khoảng trắng thừa trong title, channel_title.\n"
        "   - Ép kiểu try_cast sang BigInt cho views, likes, comment_count; fillna mặc định 0.\n"
        "2. Filter Invalid Records:\n"
        "   - Loại bỏ video_id rỗng, views < 0 hoặc null, trending_dt null, country rỗng.\n"
        "   - Kết quả: Giữ 167.657 dòng hợp lệ, loại bỏ 209 dòng lỗi (0.12%).\n"
        "3. Row Hashing & Feature Derivation (Khắc phục nhận xét của GV):\n"
        "   - Băm SHA-256 từng dòng: F.sha2(F.concat_ws('||', 'video_id', 'country', 'trending_dt', 'views', ...), 256).\n"
        "   - Khử trùng lặp snapshot theo (video_id, country, trending_dt).\n"
        "   - Dùng Window Function partitionBy(video_id, country).orderBy(trending_dt) tính tốc độ tăng trưởng:\n"
        "     views_per_hour = delta_views / delta_hours.\n"
        "   - Trích xuất year_month (yyyy-MM) và publish_hour."
    )
    fill_cell(doc.tables[8].rows[0].cells[0], table_8_text, font_size=9.0)

    # 5. Fill Table 9 (D. Join validation)
    table_9_text = (
        "D. JOIN VALIDATION (CHỨNG MINH KHÔNG NỔ DÒNG)\n"
        "• Join contract: LEFT JOIN trên fact_trending.country == dim_country.country_code\n"
        "• Uniqueness check: Phía dimension dim_country có 113/113 khóa unique 100% (0 duplicate keys)\n"
        "• Quan hệ: Many-to-One (M:1)\n"
        "• Rows before left (fact): 167.657  |  Rows before right (dim): 113\n"
        "• Rows after join: 167.657  (Bảo toàn 100% số bản ghi, data explosion = 0)\n"
        "• Unmatched records: 0 bản ghi (100% khớp mã quốc gia)\n"
        "• Policy: Left join giữ toàn vẹn Fact; nếu thiếu sẽ gán continent='Unknown'"
    )
    fill_cell(doc.tables[9].rows[0].cells[0], table_9_text, font_size=9.2)

    # 6. Fill Table 10 (E. Aggregation & output)
    table_10_text = (
        "E. AGGREGATION & OUTPUT (TRẢ LỜI CÂU HỎI TRONG PROPOSAL)\n"
        "• Output grain: continent × country_name × year_month\n"
        "• KPI / Metrics: unique_videos (đếm số video), total_snapshots, top_video_views,\n"
        "                 avg_views, avg_likes, avg_views_per_hour (tốc độ bùng nổ), peak_views_per_hour\n"
        "• Tổng số nhóm sinh ra: 226 nhóm KPI\n"
        "• Storage Path: output/youtube_trending_summary/ (Format: Parquet, partitionBy continent)\n"
        "• Preview Path: output/preview_csv/ (50 bản ghi mẫu đầu ra)"
    )
    fill_cell(doc.tables[10].rows[0].cells[0], table_10_text, font_size=9.2)

    # 7. Fill Table 11 (F. Quality & baseline)
    table_11_text = (
        "F. QUALITY EVIDENCE & BASELINE RUNTIME\n"
        "• Quality issues: Null rate ở các cột khóa = 0.0%, Duplicate dim keys = 0, Unmatched = 0\n"
        "• Băm từng dòng ở tầng Raw Ingestion: Quét 134.442.959 dòng vật lý, băm SHA-256 trọn vẹn 6.094.047 dòng,\n"
        "  cumulative_rows_hash: 96ac794cf65189e9aa205e47a45199ef7dfb1e6332e4adbfd4078783de21c625 (105.0s)\n"
        "• PySpark Baseline Runtime: 23.13 giây (đo đạc end-to-end từ đọc raw đến ghi Parquet)\n"
        "• Partitions observed: 64 shuffle partitions -> coalesce 1 preview\n"
        "• Execution plan saved: ☑ Yes  ☐ No (Đã lưu chi tiết tại evidence/explain_plan.txt)\n"
        "• Execution metrics saved: ☑ Yes  ☐ No (Đã lưu tại evidence/execution_metrics.json)"
    )
    fill_cell(doc.tables[11].rows[0].cells[0], table_11_text, font_size=9.0)

    # 8. Fill Table 12 (G. Blocker & next action)
    table_12_text = (
        "G. BLOCKER & KẾ HOẠCH BUỔI 9–10 (TỐI ƯU HÓA HIỆU NĂNG)\n"
        "• Blocker hiện tại: Không còn blocker về tính đúng đắn (correctness) và tính tái lập (reproducibility).\n"
        "  Thách thức: Tối ưu shuffle latency và broadcast join threshold khi chạy full quy mô 6 triệu dòng.\n"
        "• Next action 1: Áp dụng persist()/cache() tái sử dụng clean_df và điều chỉnh shuffle partitions\n"
        "  Owner: Trương Đình Phúc  |  Deadline: Buổi 9\n"
        "• Next action 2: Thực hiện benchmark đo lường % cải thiện so với baseline 23.13s hôm nay\n"
        "  Owner: Phan Đình Bảo & Nhóm  |  Deadline: Buổi 10"
    )
    fill_cell(doc.tables[12].rows[0].cells[0], table_12_text, font_size=9.2)

    doc.save(str(OUT))
    print(f"[SUCCESS] Checkpoint 3 Brief filled successfully at: {OUT}")


if __name__ == "__main__":
    build_brief()
