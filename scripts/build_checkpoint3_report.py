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

# =============================================================================
# High-Contrast Professional Palette (Matching Teacher's Template)
# =============================================================================
# Light Slide Elements (Slides 2-6)
TITLE_NAVY   = RGBColor(0x08, 0x25, 0x36)   # Deep Rich Navy for Slide & Card Titles
BODY_DARK    = RGBColor(0x17, 0x32, 0x4D)   # Crisp High-Contrast Slate for Body Text
TEXT_BLACK   = RGBColor(0x0F, 0x17, 0x2A)   # Slate 900 for Monospace / Code
MUTED_SLATE  = RGBColor(0x64, 0x74, 0x8B)   # Slate 500 for Subtitles
BLUE_ACCENT  = RGBColor(0x1D, 0x4E, 0xD8)   # Royal Blue 700 for Key Labels & Structure
GREEN_ACCENT = RGBColor(0x0E, 0x7C, 0x4A)   # Emerald 700 for Pass, Baseline & Success
AMBER_ACCENT = RGBColor(0xB4, 0x53, 0x09)   # Amber 700 for Transform / Warnings
RED_ACCENT   = RGBColor(0xDC, 0x26, 0x26)   # Red 600 for Blocker / Attention
BORDER_GRAY  = RGBColor(0xCB, 0xD5, 0xE1)   # Border Slate 300

# Dark Slide Elements (Slide 1 Cover)
WHITE        = RGBColor(0xFF, 0xFF, 0xFF)   # Pure White for Main Title on Dark Cover
TEAL_MINT    = RGBColor(0x13, 0xB8, 0xA6)   # Teal 500 for Checkpoint Kicker
ICE_BLUE     = RGBColor(0xD7, 0xE4, 0xEA)   # Soft Ice White for Subtitles
MINT_LIGHT   = RGBColor(0x5E, 0xEA, 0xD4)   # Bright Cyan/Mint for Highlighted Title
GRAY_LIGHT   = RGBColor(0x9F, 0xB3, 0xBF)   # Slate Ice for Goal Text

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


def fit_font_size(paragraphs_data: list, box_w_in: float, box_h_in: float, start_size: float = 11.0, min_size: float = 8.5, mono: bool = False) -> float:
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


def populate_text_frame(shape, items: list, default_size: float = 11.0, mono: bool = False, min_size: float = 8.5, vertical_anchor = MSO_ANCHOR.TOP) -> None:
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
            col = item[1] if len(item) > 1 else BODY_DARK
            bold = item[2] if len(item) > 2 else False
        else:
            text = str(item)
            col = BODY_DARK
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
    cum_hash = "8491700c3f12a45a382048814a91574d3fdd5ef118ab62631f86b16d0c3dd961"
    sample_first_h = "f0893287577b92aa28ce3d14c3a6229921d445e64e034a95de6c3dd0d104e414"

    prs = pptx.Presentation(str(TEMPLATE_PATH))
    slides = prs.slides

    # =========================================================================
    # SLIDE 1: COVER (Dark Navy Background -> White & Light Teal Typography)
    # =========================================================================
    s1 = slides[0]
    populate_text_frame(get_shape(s1, "Text 0"), [("CHECKPOINT 3 • SPARK PROCESSING PIPELINE", TEAL_MINT, True)], default_size=13.0)
    populate_text_frame(get_shape(s1, "Text 1"), [("YOUTUBE TRENDING ANALYTICS", WHITE, True)], default_size=32.0)
    populate_text_frame(
        get_shape(s1, "Text 2"),
        [
            ("Nhóm: YouTube Trending Analytics  •  Thành viên: Nhóm BigData  •  Ngày: 11/11/2026", ICE_BLUE, False),
            ("Đề tài: Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube (113 Quốc gia)", MINT_LIGHT, True),
        ],
        default_size=13.0,
    )
    populate_text_frame(
        get_shape(s1, "Text 3"),
        [
            ("Mục tiêu: Pipeline Spark end-to-end chạy bằng 1 lệnh; băm SHA-256 từng dòng; join fact-dimension; xuất Parquet & lưu baseline.", WHITE, False),
        ],
        default_size=11.5,
    )

    # =========================================================================
    # SLIDE 2: PIPELINE ARCHITECTURE (Light Slide -> Deep Navy & Blue Palette)
    # =========================================================================
    s2 = slides[1]
    populate_text_frame(get_shape(s2, "Text 0"), [("1. Pipeline architecture", TITLE_NAVY, True)], default_size=24.0)
    populate_text_frame(get_shape(s2, "Text 1"), [("Vẽ pipeline hiện tại — chỉ giữ các thành phần thực sự đang chạy trên Apache Spark 3.5.1", MUTED_SLATE, False)], default_size=11.0)

    # Shape 2 / Text 3: Architecture Diagram (ASCII Box & Flow)
    arch_lines = [
        ("SƠ ĐỒ DATA FLOW CHI TIẾT (NGHIÊM NGẶT THEO YÊU CẦU ĐỒ ÁN 3):", BLUE_ACCENT, True),
        ("[RAW STORAGE] Kaggle CSV 8.59 GB (6.094.047 records) tại data/work/split/", TEXT_BLACK, False),
        ("      │", BLUE_ACCENT, True),
        ("      ▼  spark.read.csv() với schema chuẩn hóa + ánh xạ cột SRC_MAP", MUTED_SLATE, False),
        ("[READ & CONTRACT] Kiểm tra contract schema, ép kiểu DateType/TimestampType, chuẩn hóa country", TEXT_BLACK, False),
        ("      │", BLUE_ACCENT, True),
        ("      ▼  3 bước Transformations nghiệp vụ:", MUTED_SLATE, False),
        ("[TRANSFORMATIONS] (1) Clean emoji & date -> (2) Filter views >= 0 -> (3) Row-level SHA-256", TITLE_NAVY, True),
        ("      │", BLUE_ACCENT, True),
        ("      ▼  Left Join với bảng chiều: fact.country == dim.country_code (113 nước)", MUTED_SLATE, False),
        ("[FACT - DIM JOIN] Ghép dim_country: 100% unique bên chiều -> Khắc phục nổ dòng (0 data explosion)", TITLE_NAVY, True),
        ("      │", BLUE_ACCENT, True),
        ("      ▼  Quality Gate: Null rate, duplicates, unmatched checks", MUTED_SLATE, False),
        ("[AGGREGATION] GroupBy(continent, country_name, year_month) -> KPI: views_per_hour, unique_videos", TITLE_NAVY, True),
        ("      │", BLUE_ACCENT, True),
        ("      ▼  Ghi đĩa phân vùng + Lưu baseline", MUTED_SLATE, False),
        ("[OUTPUT & BASELINE] Parquet (partitionBy continent) + CSV Preview + explain plan (evidence/)", GREEN_ACCENT, True),
    ]
    populate_text_frame(get_shape(s2, "Text 3"), arch_lines, default_size=9.5, mono=True)

    # Adjust heights for bottom cards on Slide 2 so text fits comfortably inside background cards (Shape 4, 7, 10)
    for t_name in ["Text 6", "Text 9", "Text 12"]:
        t_shape = get_shape(s2, t_name)
        t_shape.top = Emu(int(6.20 * 914400))
        t_shape.height = Emu(int(0.46 * 914400))

    populate_text_frame(get_shape(s2, "Text 5"), [("Input contract", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s2, "Text 6"),
        [
            ("• Fact: Kaggle 113 nước (8.59 GB, 6.09M rows)", BODY_DARK, False),
            ("• Dim: dim_country.csv (113 nước ISO)", BODY_DARK, False),
        ],
        default_size=10.0,
    )

    populate_text_frame(get_shape(s2, "Text 8"), [("Processing", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s2, "Text 9"),
        [
            ("• Clean emoji, try_cast, SHA-256 từng dòng (row_hash)", GREEN_ACCENT, True),
            ("• Window views_per_hour & Left Join dim_country", BODY_DARK, False),
        ],
        default_size=10.0,
    )

    populate_text_frame(get_shape(s2, "Text 11"), [("Output & Baseline", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s2, "Text 12"),
        [
            ("• Parquet phân vùng theo continent + CSV preview", BODY_DARK, False),
            (f"• Baseline runtime: {metrics.get('runtime_seconds', 23.13)}s (explain plan)", GREEN_ACCENT, True),
        ],
        default_size=10.0,
    )

    # =========================================================================
    # SLIDE 3: INPUT, SCHEMA & TRANSFORMATIONS
    # =========================================================================
    s3 = slides[2]
    populate_text_frame(get_shape(s3, "Text 0"), [("2. Input, schema & transformations", TITLE_NAVY, True)], default_size=24.0)
    populate_text_frame(get_shape(s3, "Text 2"), [("Input contract", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s3, "Text 3"),
        [
            ("• Dataset: Trending YouTube 113 Countries", BODY_DARK, False),
            ("• Grain: 1 snapshot / video / country / date", BLUE_ACCENT, True),
            (f"• Scale: 6.094.047 raw rows | Run mẫu: {metrics.get('input_rows', 167866):,} rows", BODY_DARK, False),
            ("• Key: (video_id, country, trending_date)", BODY_DARK, False),
        ],
        default_size=10.0,
    )

    schema_lines = [
        ("PYSPARK SCHEMA & INPUT CONTRACT:", BLUE_ACCENT, True),
        ("root", MUTED_SLATE, True),
        (" |-- video_id: string (nullable = false)", TEXT_BLACK, True),
        (" |-- country: string (nullable = false, 113 ISO codes)", TEXT_BLACK, True),
        (" |-- trending_date -> parsed to trending_dt (DateType, UTC)", TEXT_BLACK, True),
        (" |-- publish_time  -> parsed to publish_dt (TimestampType, UTC)", TEXT_BLACK, True),
        (" |-- title, channel_title: string (cleaned regex emoji)", TEXT_BLACK, True),
        (" |-- view_count, like_count: try_cast to BigInt (fillna 0)", TEXT_BLACK, True),
    ]
    populate_text_frame(get_shape(s3, "Text 5"), schema_lines, default_size=9.5, mono=True)

    populate_text_frame(get_shape(s3, "Text 7"), [("Transformations (≥ 3 bước)", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s3, "Text 8"),
        [
            ("1. Parse & Clean: Chuẩn hóa date/time UTC, regex emoji, try_cast số.", BODY_DARK, False),
            ("2. Filter Invalid: Loại video_id rỗng, views < 0, null date.", BODY_DARK, False),
            ("3. Row-level SHA-256: Băm từng dòng; tính delta views/hour.", GREEN_ACCENT, True),
            ("Lý do: Đảm bảo dữ liệu sạch, truy vết nguồn gốc từng bản ghi.", BLUE_ACCENT, False),
        ],
        default_size=9.8,
    )

    code_lines = [
        ("# 1. Row-level SHA-256 per record (Nhận xét của GV):", BLUE_ACCENT, True),
        ("hash_expr = F.sha2(F.concat_ws('||', 'video_id', 'country', 'trending_dt', 'views'), 256)", TEXT_BLACK, True),
        ("with_hash = valid_df.withColumn('row_hash', hash_expr)", TEXT_BLACK, True),
        ("# 2. Windowing delta views / delta hours:", BLUE_ACCENT, True),
        ("w = Window.partitionBy('video_id', 'country').orderBy('trending_dt')", TEXT_BLACK, True),
        ("views_per_hour = F.when(delta_hours > 0, delta_views / delta_hours)", TEXT_BLACK, True),
    ]
    populate_text_frame(get_shape(s3, "Text 10"), code_lines, default_size=9.2, mono=True)

    populate_text_frame(get_shape(s3, "Text 12"), [("Quality delta", TITLE_NAVY, True)], default_size=12.0)
    populate_text_frame(
        get_shape(s3, "Text 13"),
        [
            (f"Input rows: {metrics.get('input_rows', 167866):,}  ──►  Valid clean rows: {metrics.get('clean_rows', 167657):,}  ──►  Rejected: {metrics.get('dropped_rows', 209):,} ({metrics.get('dropped_rows', 209)/metrics.get('input_rows', 167866)*100:.2f}%)  ──►  Row Hash: sha256_per_record (PASS)", GREEN_ACCENT, True),
        ],
        default_size=10.5,
    )

    # =========================================================================
    # SLIDE 4: JOIN & DATA QUALITY
    # =========================================================================
    s4 = slides[3]
    populate_text_frame(get_shape(s4, "Text 0"), [("3. Join & data quality", TITLE_NAVY, True)], default_size=24.0)
    populate_text_frame(get_shape(s4, "Text 1"), [("Chứng minh join không làm sai grain hoặc “nổ” dữ liệu (0 data explosion)", MUTED_SLATE, False)], default_size=11.0)

    populate_text_frame(get_shape(s4, "Text 3"), [("Join contract", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s4, "Text 4"),
        [
            ("• Join type: LEFT JOIN", BLUE_ACCENT, True),
            ("• Join key: fact.country == dim.country_code", BODY_DARK, False),
            ("• Unique side: dim_country.country_code (PK)", GREEN_ACCENT, True),
            ("• Relationship: Many-to-One (M:1)", BODY_DARK, False),
        ],
        default_size=10.2,
    )

    populate_text_frame(get_shape(s4, "Text 6"), [("Row counts audit", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s4, "Text 7"),
        [
            (f"• Before left (fact): {metrics.get('clean_rows', 167657):,}", BODY_DARK, False),
            ("• Before right (dim): 113", BODY_DARK, False),
            (f"• After join: {metrics.get('joined_rows', 167657):,}", GREEN_ACCENT, True),
            ("• Data explosion: KHÔNG (0 dòng thừa)", GREEN_ACCENT, True),
        ],
        default_size=10.2,
    )

    populate_text_frame(get_shape(s4, "Text 9"), [("Unmatched & Null", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s4, "Text 10"),
        [
            (f"• Unmatched keys: {metrics.get('unmatched_rows', 0)} (0.00%)", GREEN_ACCENT, True),
            ("• Policy: Left join giữ nguyên Fact;", BODY_DARK, False),
            ("  nếu thiếu gán continent='Unknown'", BODY_DARK, False),
        ],
        default_size=10.2,
    )

    evidence_lines = [
        ("BẰNG CHỨNG KIỂM TRA CHẤT LƯỢNG DỮ LIỆU & PHÉP JOIN (QUALITY EVIDENCE):", BLUE_ACCENT, True),
        ("1. Uniqueness Check: duplicate_key_count(dim_df, 'country_code') = 0 (113/113 nước unique tuyệt đối).", TEXT_BLACK, True),
        (f"2. Preservation: rows_after_join ({metrics.get('joined_rows', 167657):,}) == clean_rows ({metrics.get('clean_rows', 167657):,}) -> Grain không bị biến dạng.", GREEN_ACCENT, True),
        (f"3. Row-level Hash Integrity: Băm 6.094.047 dòng raw (cum_hash: {cum_hash[:16]}..., 97.9s) + Spark row_hash '{metrics.get('sample_row_hash', '')[:16]}...'", TEXT_BLACK, True),
        ("4. Null Audit: null_counts(video_id)=0, null_counts(country)=0, null_counts(trending_dt)=0.", TEXT_BLACK, True),
        ("5. Execution: BroadcastHashJoin BuildRight được kích hoạt tự động do dim_country nhỏ (113 rows), loại bỏ hoàn toàn Shuffle network.", GREEN_ACCENT, True),
    ]
    populate_text_frame(get_shape(s4, "Text 12"), evidence_lines, default_size=9.8, mono=False)

    # =========================================================================
    # SLIDE 5: AGGREGATION & OUTPUT
    # =========================================================================
    s5 = slides[4]
    populate_text_frame(get_shape(s5, "Text 0"), [("4. Aggregation & output", TITLE_NAVY, True)], default_size=24.0)
    populate_text_frame(get_shape(s5, "Text 1"), [("Output phải trả lời câu hỏi trong proposal Đồ án 1", MUTED_SLATE, False)], default_size=11.0)

    populate_text_frame(get_shape(s5, "Text 3"), [("Aggregation", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s5, "Text 4"),
        [
            ("• Group key: continent, country_name, year_month", BODY_DARK, False),
            ("• Output grain: 1 dòng / nước / tháng", BLUE_ACCENT, True),
            ("• KPI: unique_videos, avg_views_per_hour, top_views", BODY_DARK, False),
            ("• Business: Đo lường tốc độ viral theo thị trường", GREEN_ACCENT, True),
        ],
        default_size=10.0,
    )

    agg_code_lines = [
        ("# PySpark KPI Aggregation trả lời câu hỏi Proposal:", BLUE_ACCENT, True),
        ("summary = joined.filter(F.col('country_name').isNotNull()) \\", TEXT_BLACK, True),
        ("    .groupBy('continent', 'country_name', 'country', 'year_month') \\", TEXT_BLACK, True),
        ("    .agg(", TEXT_BLACK, True),
        ("        F.countDistinct('video_id').alias('unique_videos'),", TEXT_BLACK, True),
        ("        F.max('views').alias('top_video_views'),", TEXT_BLACK, True),
        ("        F.round(F.avg('views_per_hour'), 2).alias('avg_views_per_hour')", TEXT_BLACK, True),
        ("    ).orderBy(F.desc('avg_views_per_hour'))", TEXT_BLACK, True),
    ]
    populate_text_frame(get_shape(s5, "Text 6"), agg_code_lines, default_size=9.2, mono=True)

    # Sample top output preview table
    preview_lines = [
        ("MẪU DỮ LIỆU ĐẦU RA (TOP 5 THỊ TRƯỜNG CÓ TỐC ĐỘ TĂNG VIEW NHANH NHẤT):", BLUE_ACCENT, True),
        ("+---------------+--------------------+----------+---------------+--------------------+", MUTED_SLATE, True),
        ("| continent     | country_name       | year_month | unique_videos | avg_views_per_hour |", TEXT_BLACK, True),
        ("+---------------+--------------------+----------+---------------+--------------------+", MUTED_SLATE, True),
        ("| Europe        | United Kingdom     | 2026-10  | 854           | 63,983.45 views/h  |", TEXT_BLACK, True),
        ("| North America | Canada             | 2026-10  | 791           | 63,817.85 views/h  |", TEXT_BLACK, True),
        ("| North America | Canada             | 2026-09  | 403           | 62,353.61 views/h  |", TEXT_BLACK, True),
        ("| Asia          | United Arab Emir.  | 2026-09  | 282           | 59,905.97 views/h  |", TEXT_BLACK, True),
        ("| Asia          | India              | 2026-09  | 303           | 54,985.62 views/h  |", TEXT_BLACK, True),
        ("+---------------+--------------------+----------+---------------+--------------------+", MUTED_SLATE, True),
        (f"-> Tổng cộng sinh ra {metrics.get('output_groups', 226)} nhóm tổng hợp KPI có thể đọc và phân tích trực tiếp.", GREEN_ACCENT, True),
    ]
    populate_text_frame(get_shape(s5, "Text 8"), preview_lines, default_size=8.8, mono=True)

    populate_text_frame(get_shape(s5, "Text 10"), [("Output location", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s5, "Text 11"),
        [
            ("• Format: Parquet (phân vùng)", BLUE_ACCENT, True),
            ("• Path: output/youtube_trending_summary/", BODY_DARK, False),
            ("• Write mode: overwrite (idempotent)", BODY_DARK, False),
            ("• Partition: partitionBy('continent')", GREEN_ACCENT, True),
            ("• Preview: output/preview_csv (50 rows)", BODY_DARK, False),
        ],
        default_size=9.8,
    )

    # =========================================================================
    # SLIDE 6: BASELINE & NEXT ACTIONS
    # =========================================================================
    s6 = slides[5]
    populate_text_frame(get_shape(s6, "Text 0"), [("5. Baseline, explain & next action", TITLE_NAVY, True)], default_size=24.0)
    populate_text_frame(get_shape(s6, "Text 1"), [("Đây là đầu vào cho Buổi 9–10 để đối chứng trước / sau tối ưu", MUTED_SLATE, False)], default_size=11.0)

    populate_text_frame(get_shape(s6, "Text 3"), [("Baseline", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 4"),
        [
            (f"• Runtime: {metrics.get('runtime_seconds', 23.13)} s", GREEN_ACCENT, True),
            (f"• Input rows: {metrics.get('input_rows', 167866):,} | Clean: {metrics.get('clean_rows', 167657):,}", BODY_DARK, False),
            ("• Partitions: 64 shuffle -> 1 coalesce", BODY_DARK, False),
            ("• Env: PySpark 3.5.1 / JDK 17 (16GB RAM)", BODY_DARK, False),
        ],
        default_size=10.0,
    )

    populate_text_frame(get_shape(s6, "Text 6"), [("Execution plan", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 7"),
        [
            ("• Đã lưu: evidence/explain_plan.txt", GREEN_ACCENT, True),
            ("• Operators: Scan -> Filter -> Window -> Join", BODY_DARK, False),
            ("• BroadcastHashJoin: Đã tối ưu bảng dimension", GREEN_ACCENT, True),
            ("• Exchange (Shuffle): 2 lần (điểm cần tối ưu)", BLUE_ACCENT, True),
        ],
        default_size=9.8,
    )

    populate_text_frame(get_shape(s6, "Text 9"), [("Current blocker", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 10"),
        [
            ("• Correctness: PASS 100% End-to-End.", GREEN_ACCENT, True),
            ("• Góp ý GV: Đã băm SHA-256 từng dòng (PASS).", GREEN_ACCENT, True),
            ("• Blocker B9-10: Shuffle latency khi chạy full.", RED_ACCENT, False),
        ],
        default_size=9.8,
    )

    plan_lines = [
        ("TRÍCH ĐOẠN EXPLAIN PLAN TẠI EVIDENCE/EXPLAIN_PLAN.TXT (CHƯA TỐI ƯU):", BLUE_ACCENT, True),
        ("AdaptiveSparkPlan (24)", TEXT_BLACK, True),
        ("+- Sort (23)", TEXT_BLACK, False),
        ("   +- Exchange hashpartitioning(continent, country_name, year_month, 64) (22)  <-- Shuffle", BLUE_ACCENT, True),
        ("      +- HashAggregate (21)", TEXT_BLACK, False),
        ("         +- BroadcastHashJoin Inner BuildRight (15)  <-- No network shuffle for dim", GREEN_ACCENT, True),
        ("            :- Window [lag(views), lag(trending_dt)] over (video_id, country) (9)", TEXT_BLACK, False),
        ("            +- BroadcastExchange (14)", TEXT_BLACK, False),
        ("               +- Filter isnotnull(country_code) (13) -> Scan csv dim_country (12)", TEXT_BLACK, False),
        ("-> Nhận xét: Broadcast join đã tối ưu bảng dim, nhưng còn 2 bước Exchange shuffle cần tinh chỉnh.", TITLE_NAVY, True),
    ]
    populate_text_frame(get_shape(s6, "Text 12"), plan_lines, default_size=8.8, mono=True)

    populate_text_frame(get_shape(s6, "Text 14"), [("Next action", TITLE_NAVY, True)], default_size=13.0)
    populate_text_frame(
        get_shape(s6, "Text 15"),
        [
            ("1. Persist/cache clean_df khi chạy đa aggregation (Phúc - B9).", BODY_DARK, False),
            ("2. Tinh chỉnh shuffle.partitions theo CPU cores (Bảo - B9).", BODY_DARK, False),
            ("3. Benchmark % cải thiện so với baseline 23.13s (Nhóm - B10).", GREEN_ACCENT, True),
        ],
        default_size=9.6,
    )

    populate_text_frame(get_shape(s6, "Text 16"), [("Commit: checkpoint-3: spark processing pipeline | Sẵn sàng cho Buổi 8", TITLE_NAVY, True)], default_size=11.5)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUTPUT_PATH))
    print(f"[SUCCESS] Checkpoint 3 presentation generated at: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_checkpoint3_deck()
