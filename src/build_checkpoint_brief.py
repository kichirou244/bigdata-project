"""Sinh bản Checkpoint Brief (mẫu nộp) đã điền từ template chính thức của Buổi 6.

Template (do GV cung cấp, KHÔNG sửa bản gốc):
  D:\\Edu\\BD\\BigData_Buoi06_DoAn2_Brief_Checkpoint_Template.docx

Output:
  docs/Checkpoint2_Brief_Filled.docx

Tự động điền:
  * bảng "Tên nhóm / commit / Environment / Source / Ingestion command / Raw location /
    Manifest-log / Rerun behavior / Blocker / Owner-deadline"  (bảng cuối của mẫu)
  * tick "Có" ở bảng "Evidence đầu buổi"
  * phần EXIT TICKET (4 câu) + trả lời
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
from docx.enum.text import WD_ALIGN_PARAGRAPH
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
TITLE = "Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành trên YouTube (YouTube Trending Analytics)"


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


def build() -> int:
    if not TEMPLATE.exists():
        raise SystemExit(f"Không tìm thấy template: {TEMPLATE}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE, OUT)
    doc = docx.Document(str(OUT))

    commit = git("rev-parse", "--short", "HEAD")
    tag = git("describe", "--tags", "--abbrev=0")
    tag_commit = git("rev-parse", "--short", f"{tag}^{{commit}}")

    # --- 1. Tick "Có" ở bảng evidence đầu buổi (bảng index 1) -------------
    for row in doc.tables[1].rows[1:]:
        cell = row.cells[2]
        for para in cell.paragraphs:
            for run in para.runs:
                if "□ Có" in run.text:
                    run.text = run.text.replace("□ Có", "☒ Có")

    # --- 2. Điền bảng thông tin cuối mẫu (bảng index 5) -------------------
    answers = [
        TEAM,
        TITLE,
        f"{commit} · tag {tag} ({tag_commit}) · nhánh main · repo: bigdata-project",
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
        "Log: logs/env_check.txt · logs/ingest.log · logs/transform.log\n"
        "(cả manifest + log đã commit vào git → GV clone repo là thấy bằng chứng)",
        "Mặc định --on-duplicate skip (idempotent theo SHA-256):\n"
        "  • lần 1   → tạo run_<UTC_TIMESTAMP>/ + copy + manifest\n"
        "  • lần 2,3 → hash trùng → SKIP, raw KHÔNG thay đổi (log: duplicate_skip)\n"
        "  • hash khác → run_id MỚI (append, không overwrite) | nguồn hỏng → fail-fast\n"
        "  • ép khác: --on-duplicate new-run | fail",
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

    # --- 3. EXIT TICKET + đối chiếu rubric --------------------------------
    doc.add_paragraph()
    head = doc.add_paragraph()
    run = head.add_run("EXIT TICKET – TRẢ LỜI CỦA NHÓM")
    run.bold = True
    run.font.size = Pt(13)

    ticket = [
        (
            "Câu 1 – Một lệnh duy nhất để kiểm tra environment của nhóm là gì?",
            "python src\\env_check.py\n"
            "→ in ra Spark version + phép tính Spark (Count 1.000.000) + RESULT: PASS, exit code 0.\n"
            "Output được append vào logs/env_check.txt (đã commit vào git).",
        ),
        (
            "Câu 2 – Nhóm xác định version/snapshot dữ liệu bằng cách nào?",
            "Ghi trong metadata/README.md + manifest.json của từng lần ingest:\n"
            "  dataset + URL nguồn + license (ODC-By) + ngày snapshot tải (2026-10-20)\n"
            "  + ingested_at_utc + SHA-256 của file + kích thước bytes + số record (đếm RFC4180).\n"
            "Nguồn tự cập nhật hằng ngày → mỗi lần ingest là một run_id riêng, không ghi đè.",
        ),
        (
            "Câu 3 – Nếu chạy ingestion 3 lần, raw storage thay đổi thế nào?",
            "Mặc định là skip-if-same-hash (idempotent):\n"
            "  lần 1  → tạo run_<UTC_TIMESTAMP>/ + copy file + ghi manifest.json\n"
            "  lần 2,3 → SHA-256 trùng → SKIP, KHÔNG tạo run mới, raw storage giữ nguyên\n"
            "            (log ghi rõ 'duplicate_skip → raw storage KHÔNG thay đổi')\n"
            "  file mới / version mới (hash khác) → tạo run_id mới (append, không overwrite)\n"
            "  nguồn hỏng (quality gate fail) → fail-fast, không tạo 'raw' giả\n"
            "Có thể ép hành vi khác: --on-duplicate new-run (luôn tạo run) | fail (thoát lỗi).",
        ),
        (
            "Câu 4 – Rủi ro lớn nhất trước Buổi 7 là gì?",
            "Rủi ro đã xảy ra & đã xử lý: schema nguồn Plan B khác đề cương (không có category_id,\n"
            "description nhiều dòng khiến Spark đếm sai 17 lần) → adapter SRC_MAP + split_csv.py.\n"
            "Rủi ro còn lại: file 8,59 GB mỗi snapshot + nguồn cập nhật hằng ngày → phải chạy\n"
            "ingest snapshot mới để so sánh growth giữa 2 kỳ, và phải giữ disk trống đủ.\n"
            "Owner: Phúc (transform) + Bảo (ingest) – deadline: trước Buổi 7.",
        ),
    ]
    for question, answer in ticket:
        q = doc.add_paragraph()
        r = q.add_run(question)
        r.bold = True
        r.font.size = Pt(11)
        a = doc.add_paragraph(answer)
        for run in a.runs:
            run.font.size = Pt(10)

    # --- 4. Bảng đối chiếu rubric -> evidence -----------------------------
    doc.add_paragraph()
    head = doc.add_paragraph()
    run = head.add_run("ĐỐI CHIẾU RUBRIC CHECKPOINT 2 → BẰNG CHỨNG TRONG REPO")
    run.bold = True
    run.font.size = Pt(13)

    rows = [
        ("Environment reproducible (2.0)", "src/env_check.py · logs/env_check.txt (RESULT: PASS)"),
        ("Source & provenance (1.5)", "metadata/README.md · manifest.json (URL, license, snapshot, SHA-256)"),
        ("Ingestion job (2.5)", "src/ingest_file.py · logs/ingest.log (chạy thật 8,59 GB + 3 lần rerun)"),
        ("Raw storage (2.0)", "data/raw/<dataset>/ingest_date=2026-10-20/run_20261020T143013Z/ + manifest.json"),
        ("Repo & report (1.0)", f"README.md · tag {tag} ({tag_commit}) · docs/Checkpoint2_Report_*.pptx"),
        ("Team understanding (1.0)", "Roles + trade-off ghi ở README §1-11 và docs/checkpoint2_slides_noidung.md"),
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
    print(f"   commit={commit} tag={tag} ({tag_commit})")
    return 0


if __name__ == "__main__":
    sys.exit(build())
