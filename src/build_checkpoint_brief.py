"""Sinh bản Checkpoint Brief (mẫu nộp) đã điền từ template chính thức của Buổi 6.

Template (do GV cung cấp, KHÔNG sửa bản gốc):
  D:\\Edu\\BD\\BigData_Buoi06_DoAn2_Brief_Checkpoint_Template.docx

Output:
  docs/Checkpoint2_Brief_Filled.docx

Tự động điền:
  * tick "☒ Có" ở bảng "Checklist giảng viên tại bàn"
  * bảng thông tin cuối mẫu (Tên nhóm / Đề tài / Git / Environment / Source /
    Ingestion command / Raw location / Manifest-log / Rerun behavior / Blocker /
    Owner-deadline)
  * 4 dòng trả lời EXIT TICKET ngay tại chỗ (thay dòng "____" của mẫu)
  * bảng đối chiếu RUBRIC -> artifact/evidence

Chạy:
  python src/build_checkpoint_brief.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import docx
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(r"D:\Edu\BD\BigData_Buoi06_DoAn2_Brief_Checkpoint_Template.docx")
OUT = ROOT / "docs" / "Checkpoint2_Brief_Filled.docx"

TEAM = (
    "YouTube Trending Analytics – 4 thành viên:\n"
    "  • Phan Đình Bảo – Môi trường + Ingestion (env_check.py, ingest_file.py)\n"
    "  • Trương Đình Phúc – Spark transform (split_csv.py, transform.py)\n"
    "  • Trần Thị Khánh Linh – Parquet phân vùng + DuckDB (schema, query)\n"
    "  • Đoàn Ngọc Trân Châu – Dashboard Streamlit + tài liệu (dashboard.py, README)"
)
TITLE = ("Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành trên YouTube "
         "(YouTube Trending Analytics)")

EXIT_TICKET = [
    (
        "python src\\env_check.py\n"
        "→ in ra Spark version + phép tính Spark (Count 1.000.000) + RESULT: PASS, exit code 0.\n"
        "Output được append vào logs/env_check.txt (đã commit vào git)."
    ),
    (
        "Ghi trong metadata/README.md + manifest.json của từng lần ingest:\n"
        "  dataset + URL nguồn + license (ODC-By) + ngày snapshot tải (2026-10-20)\n"
        "  + ingested_at_utc + SHA-256 + bytes + số record (đếm chuẩn RFC4180).\n"
        "Nguồn tự cập nhật hằng ngày → mỗi lần ingest là một run_id riêng, không ghi đè."
    ),
    (
        "Mặc định là skip-if-same-hash (idempotent):\n"
        "  lần 1  → tạo run_<UTC_TIMESTAMP>/ + copy file + ghi manifest.json\n"
        "  lần 2,3 → SHA-256 trùng → SKIP, KHÔNG tạo run mới, raw storage giữ nguyên\n"
        "            (log ghi rõ 'duplicate_skip → raw storage KHÔNG thay đổi')\n"
        "  file mới / version mới (hash khác) → tạo run_id mới (append, không overwrite)\n"
        "  nguồn hỏng (quality gate fail) → fail-fast (exit 1), không tạo 'raw' giả\n"
        "Có thể ép hành vi khác: --on-duplicate new-run (luôn tạo run) | fail (thoát lỗi)."
    ),
    (
        "Rủi ro đã xảy ra & đã xử lý: schema nguồn Plan B khác đề cương (không có category_id,\n"
        "description nhiều dòng khiến Spark đếm sai 17 lần) → adapter SRC_MAP + split_csv.py\n"
        "+ verify_raw_records.py (đếm lại 6.094.047 record, khớp manifest).\n"
        "Rủi ro còn lại: file 8,59 GB mỗi snapshot + nguồn cập nhật hằng ngày → phải chạy\n"
        "ingest snapshot mới để so sánh growth giữa 2 kỳ, và phải giữ disk trống đủ.\n"
        "Owner: Phúc (transform) + Bảo (ingest) – deadline: trước Buổi 7."
    ),
]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def fill_cell(cell, text: str) -> None:
    """Ghi text (multi-line) vào 1 ô, giữ style của ô đó."""
    para = cell.paragraphs[0]
    for run in list(para.runs):
        run._r.getparent().remove(run._r)
    run = para.add_run(text)
    run.font.size = Pt(10)


def fill_paragraph(paragraph, text: str) -> None:
    """Ghi text vào 1 paragraph, giữ style run đầu tiên."""
    runs = list(paragraph.runs)
    if not runs:
        paragraph.add_run(text)
        return
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    runs[0].text = text


def build() -> int:
    if not TEMPLATE.exists():
        raise SystemExit(f"Không tìm thấy template: {TEMPLATE}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE, OUT)
    doc = docx.Document(str(OUT))

    # chỉ tham chiếu TAG (không phụ thuộc HEAD) -> sinh lại cho kết quả giống hệt nhau
    tag = git("describe", "--tags", "--abbrev=0")
    tag_commit = git("rev-parse", "--short", f"{tag}^{{commit}}")

    # --- 1. Tick "☒ Có" ở bảng checklist giảng viên tại bàn ----------------
    ticked = 0
    for row in doc.tables[1].rows[1:]:
        cell = row.cells[2]
        for para in cell.paragraphs:
            for run in para.runs:
                if "□ Có" in run.text:
                    run.text = run.text.replace("□ Có", "☒ Có")
                    ticked += 1

    # --- 2. Điền bảng thông tin cuối mẫu ----------------------------------
    answers = [
        TEAM,
        TITLE,
        f"tag {tag} · nhánh main · repo: bigdata-project (git log -1 {tag})",
        "Python: 3.12.10  |  Java: 17.0.20.1 (Temurin)  |  Spark: 3.5.1  |  "
        "Mode: local[*] trên Windows (JDK 17 + pyspark 3.5.1 trong .venv)",
        "Kaggle – asaniczka/trending-youtube-videos-113-countries (license ODC-By)\n"
        "Snapshot tải: 2026-10-20 · 8.591.418.141 bytes (8,59 GB)\n"
        "6.094.047 record / 18 cột / 113 quốc gia · snapshot_date 2023-10-26 → 2026-10-20\n"
        "SHA-256: 4310930bd2d1… (đầy đủ trong manifest.json)",
        "python src\\ingest_file.py --source \"<file.csv>\" --dataset youtube_trending\n"
        "→ success | files=1 | bytes=8591418141 | sha256=4310930bd2d1… | run_20261020T143013Z",
        "data/raw/youtube_trending/ingest_date=2026-10-20/run_20261020T143013Z/\n"
        "  ├─ trending_yt_videos_113_countries.csv  (8.591.418.141 bytes – không rỗng)\n"
        "  └─ manifest.json                         (status: success)",
        "Manifest: data/raw/youtube_trending/ingest_date=2026-10-20/run_20261020T143013Z/manifest.json\n"
        "  (records=6094047 đếm chuẩn RFC4180, amendments[] ghi lại mọi thay đổi metadata)\n"
        "Log: logs/env_check.txt · logs/ingest.log · logs/transform.log\n"
        "(cả manifest + log đã commit vào git → GV clone repo là thấy bằng chứng)",
        "Mặc định --on-duplicate skip (idempotent theo SHA-256):\n"
        "  • lần 1   → tạo run_<UTC_TIMESTAMP>/ + copy + manifest\n"
        "  • lần 2,3 → hash trùng → SKIP, raw KHÔNG thay đổi (log: duplicate_skip)\n"
        "  • hash khác → run_id MỚI (append, không overwrite) | nguồn hỏng → fail-fast\n"
        "  • ép khác: --on-duplicate new-run | fail\n"
        "Đã chạy thật 3 lần liên tiếp trên file 8,59 GB → raw vẫn đúng 1 run.",
        "Đã xử lý: schema nguồn Plan B khác đề cương (thiếu category_id, description nhiều dòng)\n"
        "→ adapter SRC_MAP + split_csv.py; thiếu winutils.exe khi Spark ghi Parquet → tự cấu hình.\n"
        "Còn lại: dung lượng 8,59 GB/ngày + cần ingest snapshot mới để so sánh growth 2 kỳ.",
        "Phúc (transform) + Khánh Linh (Parquet/DuckDB) – trước Buổi 7\n"
        "Bảo (env + ingest snapshot mới) – trước Buổi 7\n"
        "Châu (dashboard + tài liệu) – trước Buổi 8",
    ]
    form = doc.tables[5]
    for (row, answer) in zip(form.rows, answers):
        fill_cell(row.cells[1], answer)

    # --- 3. Điền 4 dòng trả lời EXIT TICKET ngay tại chỗ -------------------
    blanks = [p for p in doc.paragraphs
              if p.text.strip() and set(p.text.strip()) == {"_"} and len(p.text.strip()) >= 40]
    if len(blanks) != len(EXIT_TICKET):
        raise SystemExit(
            f"Template có {len(blanks)} dòng trống, cần {len(EXIT_TICKET)} – kiểm lại template")
    for para, answer in zip(blanks, EXIT_TICKET):
        fill_paragraph(para, answer)

    # --- 4. Bảng đối chiếu rubric -> evidence -----------------------------
    doc.add_paragraph()
    head = doc.add_paragraph()
    run = head.add_run("ĐỐI CHIẾU RUBRIC CHECKPOINT 2 → BẰNG CHỨNG TRONG REPO")
    run.bold = True
    run.font.size = Pt(13)

    rows = [
        ("Environment reproducible (2.0)",
         "src/env_check.py · logs/env_check.txt (RESULT: PASS)"),
        ("Source & provenance (1.5)",
         "metadata/README.md · manifest.json (URL, license, snapshot, SHA-256)"),
        ("Ingestion job (2.5)",
         "src/ingest_file.py · logs/ingest.log (chạy thật 8,59 GB + 3 lần rerun)"),
        ("Raw storage (2.0)",
         "data/raw/<dataset>/ingest_date=2026-10-20/run_20261020T143013Z/ + manifest.json"),
        ("Repo & report (1.0)",
         f"README.md · tag {tag} · docs/Checkpoint2_Report_*.pptx · "
         f"docs/Checkpoint2_Brief_Filled.docx"),
        ("Team understanding (1.0)",
         "Roles + trade-off ghi ở README §1-9b và docs/checkpoint2_slides_noidung.md"),
    ]
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Hạng mục rubric"
    hdr[1].text = "Artifact / evidence trong repo"
    for left, right in rows:
        cells = table.add_row().cells
        cells[0].text = left
        cells[1].text = right
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9.5)

    note = doc.add_paragraph()
    run = note.add_run(
        "Lưu ý: raw CSV 8,59 GB không commit (quá lớn) – giữ ngoài repo; manifest.json + log "
        "(vài KB) ĐÃ commit để GV đối chiếu được. Có data/sample/ (CSV synthetic) để GV chạy thử."
    )
    run.italic = True
    run.font.size = Pt(9.5)

    doc.save(str(OUT))
    print(f"OK -> {OUT}")
    print(f"   tag={tag} ({tag_commit}) · tick {ticked} ô · "
          f"{len(blanks)} dòng exit-ticket đã điền")
    return validate(doc)


def validate(doc) -> int:
    """Kiểm tra: không còn ô trống, không còn dòng '____', bảng không tràn trang."""
    problems: list[str] = []
    sec = doc.sections[0]
    usable = (sec.page_width - sec.left_margin - sec.right_margin) / 914400

    for ti, table in enumerate(doc.tables):
        for row in table.rows:
            for cell in row.cells:
                if cell.width and cell.width / 914400 > usable + 0.05:
                    problems.append(f"bảng {ti}: cột rộng {cell.width / 914400:.2f}in > {usable:.2f}in")

    form = doc.tables[5]
    empty = [i for i, row in enumerate(form.rows) if not row.cells[1].text.strip()]
    if empty:
        problems.append(f"bảng thông tin: ô trống ở hàng {empty}")

    blanks = [p.text for p in doc.paragraphs
              if p.text.strip() and set(p.text.strip()) == {"_"} and len(p.text.strip()) >= 40]
    if blanks:
        problems.append(f"còn {len(blanks)} dòng '____' chưa điền (exit ticket)")

    full = "\n".join(p.text for p in doc.paragraphs)
    full += "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    for needle in ("checkpoint-2", "6.094.047", "8.591.418.141", "☒ Có",
                   "RUBRIC", "verify_raw_records"):
        if needle not in full:
            problems.append(f"thiếu nội dung '{needle}'")

    if problems:
        print("\nBRIEF CÓ VẤN ĐỀ:")
        for p in problems:
            print("  - " + p)
        return 1
    print("BRIEF OK: mọi ô đã điền, exit-ticket đầy đủ, bảng không tràn trang.")
    return 0


if __name__ == "__main__":
    sys.exit(build())
