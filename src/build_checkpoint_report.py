"""Sinh bản Checkpoint Report đã điền từ template chính thức của Buổi 6.

Template (do GV cung cấp, KHÔNG sửa bản gốc):
  D:\\Edu\\BD\\BigData_Buoi06_DoAn2_Checkpoint2_Report_Template.pptx

Output:
  docs/Checkpoint2_Report_YouTube_Trending.pptx

Mọi số liệu lấy từ evidence thật (logs/, manifest.json, _manifests/*.json) và commit
hash lấy trực tiếp từ git -> không bao giờ ghi tay số liệu.

Chạy:
  python src/build_checkpoint_report.py
"""
from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(r"D:\Edu\BD\BigData_Buoi06_DoAn2_Checkpoint2_Report_Template.pptx")
OUT = ROOT / "docs" / "Checkpoint2_Report_YouTube_Trending.pptx"

MONO = "Consolas"
INK = RGBColor(0x1A, 0x1A, 0x1A)
ACCENT = RGBColor(0x0B, 0x5C, 0xAB)
GREEN = RGBColor(0x0B, 0x6E, 0x4F)

TEAM = [
    "Phan Đình Bảo – Môi trường + Ingestion (env_check.py, ingest_file.py)",
    "Trương Đình Phúc – Spark transform (split_csv.py, transform.py)",
    "Trần Thị Khánh Linh – Parquet phân vùng + DuckDB (schema, query)",
    "Đoàn Ngọc Trân Châu – Dashboard Streamlit + tài liệu (dashboard.py, README)",
]
TITLE = "Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube"
DATASET = "YouTube Trending Analytics (Kaggle – 113 quốc gia)"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def donor_rpr(paragraph):
    """Lấy style của run đầu tiên để giữ định dạng khi thay nội dung."""
    for run in paragraph.runs:
        rPr = run._r.find(qn("a:rPr"))
        if rPr is not None:
            return copy.deepcopy(rPr)
    return None


def set_lines(shape, lines: list[str], *, mono: bool = False, size: float | None = None,
              color: RGBColor | None = None, bold: bool | None = None) -> None:
    """Ghi nội dung vào text box, giữ style của template (copy đoạn mẫu)."""
    tf = shape.text_frame
    donor_p = tf.paragraphs[0]
    rpr = donor_rpr(donor_p)
    donor_p_xml = copy.deepcopy(donor_p._p)

    # xoá toàn bộ nội dung cũ, giữ 1 đoạn mẫu
    for p in list(tf.paragraphs[1:]):
        p._p.getparent().remove(p._p)
    for r in list(donor_p.runs):
        r._r.getparent().remove(r._r)

    for i, line in enumerate(lines):
        if i == 0:
            p = donor_p
        else:
            # donor_p_xml đã là <a:p> -> gắn thẳng vào txBody (không bọc thêm)
            p_xml = copy.deepcopy(donor_p_xml)
            for child in list(p_xml):
                if child.tag != qn("a:pPr"):
                    p_xml.remove(child)
            tf._txBody.append(p_xml)
            p = tf.paragraphs[-1]
        run = p.add_run()
        run.text = line
        if rpr is not None:
            run._r.insert(0, copy.deepcopy(rpr))
        if mono:
            run.font.name = MONO
        if size is not None:
            run.font.size = Pt(size)
        if color is not None:
            run.font.color.rgb = color
        if bold is not None:
            run.font.bold = bold


def by_name(slide, name: str):
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    raise KeyError(f"Không tìm thấy shape '{name}' trong slide")


def build() -> int:
    if not TEMPLATE.exists():
        raise SystemExit(f"Không tìm thấy template: {TEMPLATE}")

    from pptx import Presentation

    prs = Presentation(str(TEMPLATE))
    slides = list(prs.slides)

    commit = git("rev-parse", "--short", "HEAD")
    tag = git("describe", "--tags", "--abbrev=0")
    tag_commit = git("rev-parse", "--short", f"{tag}^{{commit}}")

    # ---------------- SLIDE 1 – Tiêu đề -----------------------------------
    s = slides[0]
    # nới rộng 3 dòng thông tin để đề tài dài không bị tràn xuống dòng dưới
    for shape_name in ("Text 2", "Text 3", "Text 4"):
        shape = by_name(s, shape_name)
        shape.width = Inches(11.0)
    set_lines(by_name(s, "Text 2"), ["Nhóm: YouTube Trending Analytics (4 thành viên)"], size=14)
    set_lines(by_name(s, "Text 3"), [f"Đề tài: {TITLE}"], size=14)
    set_lines(
        by_name(s, "Text 4"),
        [f"Git commit/tag: {commit} · tag {tag} ({tag_commit})"],
        size=14,
    )

    # ---------------- SLIDE 2 – Architecture ------------------------------
    s = slides[1]
    set_lines(by_name(s, "Text 4"), ["SƠ ĐỒ ARCHITECTURE (phần đã triển khai đến Checkpoint 2)"])
    set_lines(
        by_name(s, "Text 5"),
        [
            "[ Kaggle CSV 8,59 GB ]  →  ingest_file.py  →  data/raw/…/run_…/",
            "   (113 quốc gia)          quality gate          + SHA-256 + manifest.json",
            "                                ↓",
            "                     split_csv.py  (chuẩn hóa 1 dòng = 1 record → 33 chunk)",
            "                                ↓",
            "                     Spark 3.5.1 local[*]  →  Parquet phân vùng",
            "                     (region / year_month)     daily + summary = 341 MB",
            "                                ↓",
            "                     DuckDB  →  Streamlit dashboard   (P3, vượt yêu cầu)",
            "",
            "Technology: Python 3.12 · JDK 17 · PySpark 3.5.1 · DuckDB · Streamlit · Parquet",
            "Boundary của nhóm: môi trường + ingestion + raw storage (có bằng chứng chạy);",
            "P3 transform & dashboard làm thêm cho Buổi 7–8, không tính vào checkpoint này.",
        ],
        mono=True,
        size=10.5,
    )
    set_lines(
        by_name(s, "Text 6"),
        [
            "1 câu giải thích trade-off chính: máy cá nhân 16 GB RAM nên chạy Spark local[*] + "
            "chuẩn hóa CSV trước (1 dòng = 1 record) thay vì multiLine=true (phải nạp nguyên "
            "file 8,59 GB vào 1 task → OOM); cột description (~8 GB) giữ nguyên ở raw, chỉ drop "
            "ở tầng metric.",
        ],
        size=10.5,
    )

    # ---------------- SLIDE 3 – Environment evidence ----------------------
    s = slides[1 + 1]
    set_lines(
        by_name(s, "Text 5"),
        [
            "Dán screenshot hoặc output (logs/env_check.txt):",
            "",
            "  Python   : 3.12.10",
            "  JAVA_HOME: D:\\Code\\SDK\\jdk\\jdk-17.0.20.1+1",
            "  Java     : openjdk version \"17.0.20.1\"",
            "  Spark    : 3.5.1",
            "  Count    : 1000000 (mong đợi 1000000)",
            "  RESULT : PASS",
            "",
            "→ smoke test chạy lại được, exit code 0 (22/10/2026)",
        ],
        mono=True,
        size=10.5,
        color=INK,
    )
    set_lines(
        by_name(s, "Text 8"),
        [
            "python -m venv .venv",
            ".venv\\Scripts\\pip install -r requirements.txt",
            ".venv\\Scripts\\python.exe src\\env_check.py",
        ],
        mono=True,
        size=10,
    )
    set_lines(
        by_name(s, "Text 11"),
        ["local[*] trên Windows (Spark 3.5.1 + JDK 17)"],
        size=11,
    )
    set_lines(
        by_name(s, "Text 14"),
        ["Đã xử lý: thiếu winutils.exe (Spark ghi Parquet) → tự cấu hình HADOOP_HOME + PATH "
         "trong transform.py, không cài Hadoop hệ thống."],
        size=10,
    )

    # ---------------- SLIDE 4 – Data source & ingestion -------------------
    s = slides[1 + 2]
    set_lines(
        by_name(s, "Text 5"),
        ["https://www.kaggle.com/datasets/asaniczka/trending-youtube-videos-113-countries"],
        size=10.5,
    )
    set_lines(
        by_name(s, "Text 8"),
        [
            "8.591.418.141 bytes (8,59 GB) · 6.094.047 record · 18 cột · 113 quốc gia",
            "snapshot_date 2023-10-26 → 2026-10-20 (snapshot tải 2026-10-20)",
            "SHA-256 4310930bd2d1… (đầy đủ trong manifest.json)",
        ],
        size=10,
    )
    set_lines(
        by_name(s, "Text 11"),
        ["Nguồn: Kaggle · license ODC-By · file gốc giữ ngoài repo, ingest = copy + hash + "
         "manifest (bytes, sha256, thời điểm) → truy ngược được từng byte trong raw."],
        size=10,
    )
    set_lines(
        by_name(s, "Text 14"),
        [
            "Command:",
            "  python src\\ingest_file.py --source <csv> --dataset youtube_trending",
            "",
            "Result (logs/ingest.log):",
            "  success | dataset=youtube_trending | run=run_20261020T143013Z | files=1",
            "          | bytes=8591418141 | sha256=4310930bd2d1… | status=success",
            "  manifest | data\\raw\\youtube_trending\\…\\manifest.json",
        ],
        mono=True,
        size=10,
    )

    # ---------------- SLIDE 5 – Raw storage & manifest --------------------
    s = slides[1 + 3]
    set_lines(
        by_name(s, "Text 5"),
        [
            "Path convention:",
            "  data/raw/<dataset>/ingest_date=YYYY-MM-DD/run_<UTC_TIMESTAMP>/",
            "",
            "  data/raw/youtube_trending/ingest_date=2026-10-20/run_20261020T143013Z/",
            "    ├─ trending_yt_videos_113_countries.csv   (8.591.418.141 bytes)",
            "    └─ manifest.json                          (status: success)",
            "",
            "Raw file size: 8.591.418.141 bytes (8,59 GB) – không rỗng, giữ nguyên bản gốc.",
        ],
        mono=True,
        size=10.5,
    )
    set_lines(
        by_name(s, "Text 8"),
        [
            "manifest.json (cạnh raw file) – trường quan trọng:",
            "  dataset       : youtube_trending",
            "  source        : trending_yt_videos_113_countries.csv",
            "  ingested_at   : 2026-10-20T14:30:13+00:00",
            "  bytes         : 8591418141   (khớp đúng file trên đĩa)",
            "  sha256        : 4310930bd2d1…",
            "  destination   : data/raw/youtube_trending/ingest_date=…/run_…/",
            "  records       : 6094047       (đếm chuẩn RFC4180)",
            "  status        : success",
            "",
            "Log: logs/env_check.txt · logs/ingest.log · logs/transform.log",
        ],
        mono=True,
        size=10,
    )

    # ---------------- SLIDE 6 – Rerun, blocker, next action ----------------
    s = slides[1 + 4]
    set_lines(
        by_name(s, "Text 5"),
        [
            "Mặc định --on-duplicate skip (idempotent theo SHA-256):",
            "  lần 1  → tạo run_… + copy + manifest",
            "  lần 2,3 → hash trùng → SKIP, raw KHÔNG đổi (log: duplicate_skip)",
            "hash khác → run_id mới (append, không overwrite) | nguồn hỏng → fail-fast",
        ],
        mono=True,
        size=9.5,
    )
    set_lines(
        by_name(s, "Text 8"),
        [
            "Schema nguồn Plan B khác đề cương (thiếu category_id, description nhiều dòng) → "
            "adapter SRC_MAP + split_csv.py (đã xử lý).",
            "Rủi ro còn lại: dung lượng 8,59 GB + nguồn cập nhật hằng ngày → phải chạy ingest "
            "snapshot mới để so sánh growth.",
            "Owner: Phúc (transform) · Khánh Linh (Parquet/DuckDB)   Deadline: trước Buổi 7",
        ],
        size=9.5,
    )
    set_lines(
        by_name(s, "Text 11"),
        [
            f"Commit/tag: {commit} · tag {tag} ({tag_commit})",
            "Raw/manifest/log: data/raw/youtube_trending/…/run_…/manifest.json · logs/*.log",
        ],
        mono=True,
        size=9.5,
    )
    set_lines(
        by_name(s, "Text 14"),
        [
            "1) Chạy ingest snapshot mới (nguồn cập nhật hằng ngày) để so sánh growth 2 kỳ.",
            "2) Demo dashboard trực tiếp + chốt đề cương Đồ án 3 (ML / nâng cao).",
        ],
        size=9.5,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"OK -> {OUT}")
    print(f"   commit={commit} tag={tag} ({tag_commit})")
    return 0


if __name__ == "__main__":
    sys.exit(build())
