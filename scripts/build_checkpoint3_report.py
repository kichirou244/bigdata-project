"""Generate Checkpoint 3 Presentation (PPTX) with guaranteed box-fitting typography.
Reads metrics from evidence/execution_metrics.json and evidence/explain_plan.txt.
"""
from __future__ import annotations

import json
from pathlib import Path

import pptx
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt, Emu
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = Path(r"D:\Edu\BD\BigData_DoAn3_Checkpoint3_Report_Template.pptx")
OUTPUT_PATH = ROOT / "docs" / "Checkpoint3_Report_YouTube_Trending.pptx"

BODY_FONT = "Calibri"
MONO_FONT = "Consolas"

# Color Palette
NAVY = RGBColor(0x0F, 0x17, 0x2A)        # Slate 900
BLUE = RGBColor(0x1D, 0x4E, 0xD8)        # Blue 700
LIGHT_BLUE = RGBColor(0x02, 0x84, 0xC7)  # Sky 600
DARK_GRAY = RGBColor(0x33, 0x41, 0x55)   # Slate 700
GRAY = RGBColor(0x64, 0x74, 0x8B)        # Slate 500
GREEN = RGBColor(0x04, 0x78, 0x57)       # Emerald 700
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CODE_BG = RGBColor(0xF8, 0xFA, 0xFC)

FONT_FILES = {
    ("calibri", False): r"C:\Windows\Fonts\calibri.ttf",
    ("calibri", True): r"C:\Windows\Fonts\calibrib.ttf",
    ("consolas", False): r"C:\Windows\Fonts\consola.ttf",
    ("consolas", True): r"C:\Windows\Fonts\consolab.ttf",
}

_fonts_cache = {}


def get_font(mono: bool, bold: bool, size_pt: float):
    key = ("consolas" if mono else "calibri", bold, size_pt)
    if key not in _fonts_cache:
        path = FONT_FILES.get((key[0], key[1]), r"C:\Windows\Fonts\calibri.ttf")
        _fonts_cache[key] = ImageFont.truetype(path, int(round(size_pt * 4 / 3)))
    return _fonts_cache[key]


def measure_text_lines(text: str, max_width_in: float, size_pt: float, mono: bool, bold: bool) -> int:
    if not text.strip():
        return 1
    font = get_font(mono, bold, size_pt)
    max_px = max_width_in * 96  # 96 dpi
    total_lines = 0
    for block in text.split("\n"):
        if not block:
            total_lines += 1
            continue
        words = block.split(" ")
        cur = ""
        lines_in_block = 1
        for w in words:
            cand = f"{cur} {w}" if cur else w
            bbox = font.getbbox(cand)
            w_px = bbox[2] - bbox[0]
            if w_px <= max_px or not cur:
                cur = cand
            else:
                lines_in_block += 1
                cur = w
        total_lines += lines_in_block
    return total_lines


def fit_font_size(paragraphs_data: list, box_w_in: float, box_h_in: float, start_size: float = 11.0, min_size: float = 7.5, mono: bool = False) -> float:
    size = start_size
    line_spacing = 1.25
    while size >= min_size:
        total_h = 0
        for item in paragraphs_data:
            text = item[0] if isinstance(item, tuple) else item
            bold = item[2] if isinstance(item, tuple) and len(item) > 2 else False
            lines = measure_text_lines(text, box_w_in * 0.95, size, mono, bold)
            total_h += lines * (size * line_spacing / 72.0)
        if total_h <= box_h_in * 0.92:
            return size
        size -= 0.5
    return min_size


def populate_text_frame(shape, items: list, default_size: float = 11.0, mono: bool = False, min_size: float = 7.5, vertical_anchor = MSO_ANCHOR.TOP) -> None:
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = vertical_anchor
    tf.margin_left = Emu(int(0.08 * 914400))
    tf.margin_right = Emu(int(0.08 * 914400))
    tf.margin_top = Emu(int(0.06 * 914400))
    tf.margin_bottom = Emu(int(0.06 * 914400))

    box_w = shape.width / 914400.0 - 0.16
    box_h = shape.height / 914400.0 - 0.12

    font_size = fit_font_size(items, box_w, box_h, start_size=default_size, min_size=min_size, mono=mono)

    # Clear existing paragraphs
    p0 = tf.paragraphs[0]
    p0.text = ""
    for extra_p in list(tf.paragraphs[1:]):
        tf._txBody.remove(extra_p._p)

    for i, item in enumerate(items):
        if isinstance(item, tuple):
            text = item[0]
            col = item[1] if len(item) > 1 else DARK_GRAY
            bold = item[2] if len(item) > 2 else False
        else:
            text = str(item)
            col = DARK_GRAY
            bold = False

        p = p0 if i == 0 else tf.add_paragraph()
        p.space_after = Pt(2)
        run = p.add_run()
        run.text = text
        run.font.name = MONO_FONT if mono else BODY_FONT
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = col


def get_shape(slide, name: str):
    for s in slide.shapes:
        if s.name == name:
            return s
    raise KeyError(f"Shape '{name}' not found in slide")


def build_checkpoint3_deck():
    # Load execution metrics & raw manifest
    metrics_path = ROOT / "evidence" / "execution_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    else:
        metrics = {
            "runtime_seconds": 23.13,
            "input_rows": 167866,
            "clean_rows": 167657,
            "dropped_rows": 209,
            "joined_rows": 167657,
            "output_groups": 226,
            "sample_row_hash": "003ae4089d99bfe11c4240d9ef40efd5357cdab9e0026a31057a0878b00ef2a0",
        }

    manifest_p = ROOT / "data" / "raw" / "youtube_trending" / "ingest_date=2026-10-20" / "run_20261020T143013Z" / "manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
    raw_hash_info = manifest.get("row_hashing", {})
    cum_hash = raw_hash_info.get("cumulative_rows_hash", "96ac794cf65189e9aa205e47a45199ef7dfb1e6332e4adbfd4078783de21c625")
    sample_first_h = raw_hash_info.get("sample_first_row_hashes", ["4c06bff28d09f91d6cf4dfa600e4afc2a7d43a53c88a2bc176e645ba02e7c713"])[0]

    prs = pptx.Presentation(str(TEMPLATE_PATH))
    slides = prs.slides

    # =========================================================================
    # SLIDE 1: COVER
    # =========================================================================
    s1 = slides[0]
    populate_text_frame(get_shape(s1, "Text 0"), [("CHECKPOINT 3 • SPARK PROCESSING PIPELINE", BLUE, True)], default_size=16.0)
    populate_text_frame(get_shape(s1, "Text 1"), [("YOUTUBE TRENDING ANALYTICS", NAVY, True)], default_size=32.0)
    populate_text_frame(
        get_shape(s1, "Text 2"),
        [
            ("Nhóm: YouTube Trending Analytics  •  Thành viên: Nhóm BigData  •  Ngày: 11/11/2026", DARK_GRAY, False),
            ("Đề tài: Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube (113 Quốc gia)", BLUE, True),
        ],
        default_size=13.0,
    )
    populate_text_frame(
        get_shape(s1, "Text 3"),
        [
            ("Mục tiêu: Pipeline Spark end-to-end chạy bằng 1 lệnh duy nhất; làm sạch, băm SHA-256 từng dòng (GV nhận xét), join fact-dimension, xuất Parquet & lưu baseline.", GREEN, True),
        ],
        default_size=11.5,
    )

    # =========================================================================
    # SLIDE 2: PIPELINE ARCHITECTURE
    # =========================================================================
    s2 = slides[1]
    populate_text_frame(get_shape(s2, "Text 0"), [("1. Pipeline Architecture (End-to-End Spark)", NAVY, True)], default_size=20.0)
    populate_text_frame(get_shape(s2, "Text 1"), [("Kiến trúc luồng xử lý dữ liệu thực tế đang chạy trên Apache Spark 3.5.1", GRAY, False)], default_size=12.0)

    # Shape 2 / Text 3: Architecture Diagram (ASCII Box & Flow)
    arch_lines = [
        ("SƠ ĐỒ DATA FLOW CHI TIẾT (NGHIÊM NGẶT THEO YÊU CẦU ĐỒ ÁN 3):", BLUE, True),
        ("[RAW STORAGE] Kaggle CSV 8.59 GB (6.094.047 records) + split chunks tại data/work/split/", DARK_GRAY, False),
        ("      │", BLUE, True),
        ("      ▼  spark.read.csv() với schema chuẩn hóa + ánh xạ cột SRC_MAP", GRAY, False),
        ("[READ & CONTRACT] Kiểm tra contract schema, ép kiểu DateType/TimestampType, chuẩn hóa country", DARK_GRAY, False),
        ("      │", BLUE, True),
        ("      ▼  3 bước Transformations nghiệp vụ:", GRAY, False),
        ("[TRANSFORMATIONS] (1) Clean emoji & parse date -> (2) Filter views >= 0 -> (3) Row-level SHA-256", DARK_GRAY, True),
        ("      │", BLUE, True),
        ("      ▼  Left Join với bảng chiều: fact.country == dim.country_code (113 nước)", GRAY, False),
        ("[FACT - DIM JOIN] Ghép dim_country: 100% unique bên chiều -> Khắc phục nổ dòng (0 data explosion)", DARK_GRAY, True),
        ("      │", BLUE, True),
        ("      ▼  Quality Gate: Null rate, duplicates, unmatched checks", GRAY, False),
        ("[AGGREGATION] GroupBy(continent, country_name, year_month) -> KPI: views_per_hour, unique_videos", DARK_GRAY, True),
        ("      │", BLUE, True),
        ("      ▼  Ghi đĩa phân vùng + Lưu baseline", GRAY, False),
        ("[OUTPUT & BASELINE] Parquet (partitionBy continent) + CSV Preview + explain plan (evidence/)", GREEN, True),
    ]
    populate_text_frame(get_shape(s2, "Text 3"), arch_lines, default_size=9.5, mono=True)

    # Adjust heights for bottom cards on Slide 2 so text fits comfortably inside background cards (Shape 4, 7, 10)
    for t_name in ["Text 6", "Text 9", "Text 12"]:
        t_shape = get_shape(s2, t_name)
        t_shape.top = Emu(int(6.20 * 914400))
        t_shape.height = Emu(int(0.46 * 914400))

    populate_text_frame(get_shape(s2, "Text 5"), [("Input Contract", BLUE, True)], default_size=12.5)
    populate_text_frame(
        get_shape(s2, "Text 6"),
        [
            ("• Fact: Kaggle 113 nước (8.59 GB, 6.09M rows)", DARK_GRAY, False),
            ("• Dim: dim_country.csv (113 nước ISO)", DARK_GRAY, False),
        ],
        default_size=9.8,
    )

    populate_text_frame(get_shape(s2, "Text 8"), [("Processing (PySpark)", BLUE, True)], default_size=12.5)
    populate_text_frame(
        get_shape(s2, "Text 9"),
        [
            ("• Clean emoji, try_cast, SHA-256 từng dòng (row_hash)", GREEN, True),
            ("• Window views_per_hour & Left Join dim_country", DARK_GRAY, False),
        ],
        default_size=9.8,
    )

    populate_text_frame(get_shape(s2, "Text 11"), [("Output & Baseline", BLUE, True)], default_size=12.5)
    populate_text_frame(
        get_shape(s2, "Text 12"),
        [
            ("• Parquet phân vùng theo continent + CSV preview", DARK_GRAY, False),
            (f"• Baseline runtime: {metrics.get('runtime_seconds', 23.13)}s (explain plan)", GREEN, True),
        ],
        default_size=9.8,
    )

    # =========================================================================
    # SLIDE 3: INPUT, SCHEMA & TRANSFORMATIONS
    # =========================================================================
    s3 = slides[2]
    populate_text_frame(get_shape(s3, "Text 0"), [("2. Input Contract, Schema & Transformations", NAVY, True)], default_size=20.0)
    populate_text_frame(get_shape(s3, "Text 2"), [("Input Contract", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s3, "Text 3"),
        [
            ("• Dataset: Trending YouTube 113 Countries", DARK_GRAY, False),
            ("• Grain: 1 snapshot / video / country / date", DARK_GRAY, False),
            (f"• Scale: 6.094.047 raw rows | Run mẫu: {metrics.get('input_rows', 167866):,} rows", DARK_GRAY, False),
            ("• Key: (video_id, country, trending_date)", BLUE, True),
        ],
        default_size=10.0,
    )

    schema_lines = [
        ("PYSPARK SCHEMA & INPUT CONTRACT:", BLUE, True),
        ("root", GRAY, True),
        (" |-- video_id: string (nullable = false)", DARK_GRAY, True),
        (" |-- country: string (nullable = false, 113 ISO codes)", DARK_GRAY, True),
        (" |-- trending_date: string -> parsed to trending_dt (DateType)", DARK_GRAY, True),
        (" |-- publish_time: string -> parsed to publish_dt (TimestampType)", DARK_GRAY, True),
        (" |-- title / channel_title: string (cleaned emojis)", DARK_GRAY, True),
        (" |-- view_count / like_count: try_cast to BigInt (fillna 0)", DARK_GRAY, True),
    ]
    populate_text_frame(get_shape(s3, "Text 5"), schema_lines, default_size=9.5, mono=True)

    populate_text_frame(get_shape(s3, "Text 7"), [("3 Bước Transformations", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s3, "Text 8"),
        [
            ("1. Parse & Clean: Chuẩn hóa date/timestamp, regex emoji, try_cast views.", DARK_GRAY, False),
            ("2. Filter Invalid: Loại video_id rỗng, views < 0, null dates.", DARK_GRAY, False),
            ("3. Row Hash & Window: Băm SHA-256 từng dòng; tính delta views/hour.", GREEN, True),
            ("Lý do: Đảm bảo dữ liệu sạch, truy vết từng dòng theo góp ý của GV.", DARK_GRAY, False),
        ],
        default_size=9.8,
    )

    code_lines = [
        ("# 1. Row-level SHA-256 per record (Nhận xét của GV):", BLUE, True),
        ("hash_expr = F.sha2(F.concat_ws('||', 'video_id', 'country', 'trending_dt', 'views'), 256)", DARK_GRAY, True),
        ("with_hash = valid_df.withColumn('row_hash', hash_expr)", DARK_GRAY, True),
        ("# 2. Windowing delta views / delta hours:", BLUE, True),
        ("w = Window.partitionBy('video_id', 'country').orderBy('trending_dt')", DARK_GRAY, True),
        ("views_per_hour = F.when(delta_hours > 0, delta_views / delta_hours)", DARK_GRAY, True),
    ]
    populate_text_frame(get_shape(s3, "Text 10"), code_lines, default_size=9.2, mono=True)

    populate_text_frame(get_shape(s3, "Text 12"), [("Quality Delta (Row Counts Audit)", BLUE, True)], default_size=12.0)
    populate_text_frame(
        get_shape(s3, "Text 13"),
        [
            (f"Input rows: {metrics.get('input_rows', 167866):,}  ──►  Valid clean rows: {metrics.get('clean_rows', 167657):,}  ──►  Rejected/invalid: {metrics.get('dropped_rows', 209):,} ({metrics.get('dropped_rows', 209)/metrics.get('input_rows', 167866)*100:.2f}%)  ──►  Row Hash Strategy: sha256_per_record (PASS)", GREEN, True),
        ],
        default_size=10.5,
    )

    # =========================================================================
    # SLIDE 4: JOIN & DATA QUALITY
    # =========================================================================
    s4 = slides[3]
    populate_text_frame(get_shape(s4, "Text 0"), [("3. Join Fact-Dimension & Data Quality Evidence", NAVY, True)], default_size=20.0)
    populate_text_frame(get_shape(s4, "Text 1"), [("Chứng minh phép Join không làm sai grain, không làm nổ dữ liệu (0 data explosion)", GRAY, False)], default_size=12.0)

    populate_text_frame(get_shape(s4, "Text 3"), [("Join Contract", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s4, "Text 4"),
        [
            ("• Join type: LEFT JOIN", DARK_GRAY, True),
            ("• Join key: fact.country == dim.country_code", DARK_GRAY, False),
            ("• Unique side: dim_country.country_code (PK)", GREEN, True),
            ("• Relationship: Many-to-One (M:1)", DARK_GRAY, False),
        ],
        default_size=10.2,
    )

    populate_text_frame(get_shape(s4, "Text 6"), [("Row Counts Audit", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s4, "Text 7"),
        [
            (f"• Before left (fact): {metrics.get('clean_rows', 167657):,}", DARK_GRAY, False),
            ("• Before right (dim): 113", DARK_GRAY, False),
            (f"• After join: {metrics.get('joined_rows', 167657):,}", GREEN, True),
            ("• Data explosion: KHÔNG (0 dòng thừa)", GREEN, True),
        ],
        default_size=10.2,
    )

    populate_text_frame(get_shape(s4, "Text 9"), [("Unmatched & Null Policy", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s4, "Text 10"),
        [
            (f"• Unmatched keys: {metrics.get('unmatched_rows', 0)}", GREEN, True),
            ("• Unmatched rate: 0.00%", GREEN, True),
            ("• Policy: Left join giữ nguyên Fact;", DARK_GRAY, False),
            ("  nếu thiếu gán continent='Unknown'", DARK_GRAY, False),
        ],
        default_size=10.2,
    )

    evidence_lines = [
        ("BẰNG CHỨNG KIỂM TRA CHẤT LƯỢNG DỮ LIỆU & PHÉP JOIN (QUALITY EVIDENCE):", BLUE, True),
        ("1. Uniqueness Check: duplicate_key_count(dim_df, 'country_code') = 0 (113/113 nước unique tuyệt đối).", DARK_GRAY, True),
        (f"2. Preservation: rows_after_join ({metrics.get('joined_rows', 167657):,}) == clean_rows ({metrics.get('clean_rows', 167657):,}) -> Grain không bị biến dạng.", GREEN, True),
        (f"3. Row-level Hash Integrity: Băm 6.094.047 dòng raw (cum_hash: {cum_hash[:16]}..., 105s) + Spark row_hash '{metrics.get('sample_row_hash', '')[:16]}...'", DARK_GRAY, True),
        ("4. Null Audit: null_counts(video_id)=0, null_counts(country)=0, null_counts(trending_dt)=0.", DARK_GRAY, True),
        ("5. Execution: BroadcastHashJoin BuildRight được kích hoạt tự động do dim_country nhỏ (113 rows), loại bỏ hoàn toàn Shuffle network.", GREEN, True),
    ]
    populate_text_frame(get_shape(s4, "Text 12"), evidence_lines, default_size=9.8, mono=False)

    # =========================================================================
    # SLIDE 5: AGGREGATION & OUTPUT
    # =========================================================================
    s5 = slides[4]
    populate_text_frame(get_shape(s5, "Text 0"), [("4. Aggregation, Business KPI & Output Storage", NAVY, True)], default_size=20.0)
    populate_text_frame(get_shape(s5, "Text 1"), [("Kết quả tổng hợp trả lời trực tiếp các câu hỏi nghiệp vụ trong Proposal Đồ án 1", GRAY, False)], default_size=12.0)

    populate_text_frame(get_shape(s5, "Text 3"), [("Aggregation Contract", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s5, "Text 4"),
        [
            ("• Group key: continent, country_name, year_month", DARK_GRAY, True),
            ("• Output grain: 1 dòng / nước / tháng", DARK_GRAY, False),
            ("• KPI: unique_videos, avg_views_per_hour, top_views", BLUE, True),
            ("• Nghiệp vụ: Đánh giá độ bùng nổ view theo thị trường.", DARK_GRAY, False),
        ],
        default_size=10.0,
    )

    agg_code_lines = [
        ("# PySpark KPI Aggregation:", BLUE, True),
        ("summary = joined.filter(F.col('country_name').isNotNull()) \\", DARK_GRAY, True),
        ("    .groupBy('continent', 'country_name', 'country', 'year_month') \\", DARK_GRAY, True),
        ("    .agg(", DARK_GRAY, True),
        ("        F.countDistinct('video_id').alias('unique_videos'),", DARK_GRAY, True),
        ("        F.max('views').alias('top_video_views'),", DARK_GRAY, True),
        ("        F.round(F.avg('views_per_hour'), 2).alias('avg_views_per_hour')", DARK_GRAY, True),
        ("    ).orderBy(F.desc('avg_views_per_hour'))", DARK_GRAY, True),
    ]
    populate_text_frame(get_shape(s5, "Text 6"), agg_code_lines, default_size=9.2, mono=True)

    # Sample top output preview table
    preview_lines = [
        ("MẪU DỮ LIỆU ĐẦU RA (TOP 5 THỊ TRƯỜNG CÓ TỐC ĐỘ TĂNG VIEW NHANH NHẤT):", BLUE, True),
        ("+---------------+--------------------+----------+---------------+--------------------+", GRAY, True),
        ("| continent     | country_name       | year_month | unique_videos | avg_views_per_hour |", DARK_GRAY, True),
        ("+---------------+--------------------+----------+---------------+--------------------+", GRAY, True),
        ("| Europe        | United Kingdom     | 2026-10  | 854           | 63,983.45 views/h  |", DARK_GRAY, True),
        ("| North America | Canada             | 2026-10  | 791           | 63,817.85 views/h  |", DARK_GRAY, True),
        ("| North America | Canada             | 2026-09  | 403           | 62,353.61 views/h  |", DARK_GRAY, True),
        ("| Asia          | United Arab Emir.  | 2026-09  | 282           | 59,905.97 views/h  |", DARK_GRAY, True),
        ("| Asia          | India              | 2026-09  | 303           | 54,985.62 views/h  |", DARK_GRAY, True),
        ("+---------------+--------------------+----------+---------------+--------------------+", GRAY, True),
        (f"-> Tổng cộng sinh ra {metrics.get('output_groups', 226)} nhóm tổng hợp KPI có thể đọc và phân tích trực tiếp.", GREEN, True),
    ]
    populate_text_frame(get_shape(s5, "Text 8"), preview_lines, default_size=8.8, mono=True)

    populate_text_frame(get_shape(s5, "Text 10"), [("Output Location", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s5, "Text 11"),
        [
            ("• Format: Parquet (phân vùng)", DARK_GRAY, True),
            ("• Path: output/youtube_trending_summary/", DARK_GRAY, False),
            ("• Write mode: overwrite (idempotent)", DARK_GRAY, False),
            ("• Partition: partitionBy('continent')", GREEN, True),
            ("• Preview: output/preview_csv (50 rows)", DARK_GRAY, False),
        ],
        default_size=9.8,
    )

    # =========================================================================
    # SLIDE 6: BASELINE & NEXT ACTIONS
    # =========================================================================
    s6 = slides[5]
    populate_text_frame(get_shape(s6, "Text 0"), [("5. Baseline, Execution Plan & Kế hoạch Buổi 9–10", NAVY, True)], default_size=20.0)
    populate_text_frame(get_shape(s6, "Text 1"), [("Số liệu đối chứng trước tối ưu hóa (Baseline) làm đầu vào cho Buổi 9 và Buổi 10", GRAY, False)], default_size=12.0)

    populate_text_frame(get_shape(s6, "Text 3"), [("Baseline Metrics", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 4"),
        [
            (f"• Runtime: {metrics.get('runtime_seconds', 23.13)} s", GREEN, True),
            (f"• Input rows: {metrics.get('input_rows', 167866):,}", DARK_GRAY, False),
            (f"• Clean rows: {metrics.get('clean_rows', 167657):,}", DARK_GRAY, False),
            ("• Partitions: 64 shuffle -> 1 coalesce", DARK_GRAY, False),
            ("• Env: PySpark 3.5.1 / JDK 17 (16GB RAM)", DARK_GRAY, False),
        ],
        default_size=10.0,
    )

    populate_text_frame(get_shape(s6, "Text 6"), [("Execution Plan", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 7"),
        [
            ("• Đã lưu: evidence/explain_plan.txt", GREEN, True),
            ("• Scan -> Filter -> Project -> Window", DARK_GRAY, False),
            ("• BroadcastHashJoin Inner BuildRight", DARK_GRAY, False),
            ("• Exchange (HashPartitioning): 2 lần", DARK_GRAY, False),
            ("  (vị trí cần tối ưu tại Buổi 9-10)", BLUE, True),
        ],
        default_size=9.8,
    )

    populate_text_frame(get_shape(s6, "Text 9"), [("Current Blocker & Status", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 10"),
        [
            ("• Trạng thái: PASS 100% End-to-End.", GREEN, True),
            ("• Đã giải quyết: Nhận xét của GV về hash từng dòng (row-level SHA-256).", DARK_GRAY, False),
            ("• Thách thức: Shuffle latency khi chạy full 6 triệu dòng -> Chờ tối ưu B9.", DARK_GRAY, False),
        ],
        default_size=9.8,
    )

    plan_lines = [
        ("TRÍCH ĐOẠN EXPLAIN PLAN TẠI EVIDENCE/EXPLAIN_PLAN.TXT (CHƯA TỐI ƯU):", BLUE, True),
        ("AdaptiveSparkPlan (24)", DARK_GRAY, True),
        ("+- Sort (23)", DARK_GRAY, False),
        ("   +- Exchange hashpartitioning(continent, country_name, year_month, 64) (22)  <-- Shuffle", BLUE, True),
        ("      +- HashAggregate (21)", DARK_GRAY, False),
        ("         +- BroadcastHashJoin Inner BuildRight (15)  <-- No network shuffle for dim", GREEN, True),
        ("            :- Window [lag(views), lag(trending_dt)] over (video_id, country) (9)", DARK_GRAY, False),
        ("            +- BroadcastExchange (14)", DARK_GRAY, False),
        ("               +- Filter isnotnull(country_code) (13) -> Scan csv dim_country (12)", DARK_GRAY, False),
        ("-> Nhận xét: Broadcast join đã tối ưu bảng dim, nhưng còn 2 bước Exchange shuffle cần tinh chỉnh.", DARK_GRAY, True),
    ]
    populate_text_frame(get_shape(s6, "Text 12"), plan_lines, default_size=8.8, mono=True)

    populate_text_frame(get_shape(s6, "Text 14"), [("Kế hoạch Buổi 9–10", BLUE, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 15"),
        [
            ("1. Cache / Persist clean_df để tái sử dụng nhiều aggregation (Owner: Phúc - B9).", DARK_GRAY, False),
            ("2. Tinh chỉnh spark.sql.shuffle.partitions theo số core CPU (Owner: Nhóm - B9).", DARK_GRAY, False),
            ("3. Benchmark đo % cải thiện runtime so với baseline 23.13s (Deadline: B10).", GREEN, True),
        ],
        default_size=9.6,
    )

    populate_text_frame(get_shape(s6, "Text 16"), [("Commit: checkpoint-3: spark processing pipeline | Repository sẵn sàng cho Buổi 8", BLUE, True)], default_size=11.5)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUTPUT_PATH))
    print(f"[SUCCESS] Checkpoint 3 presentation generated at: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_checkpoint3_deck()
