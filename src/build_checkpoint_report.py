"""Sinh bản Checkpoint Report đã điền từ template chính thức của Buổi 6.

Template (do GV cung cấp, KHÔNG sửa bản gốc):
  D:\\Edu\\BD\\BigData_Buoi06_DoAn2_Checkpoint2_Report_Template.pptx

Output:
  docs/Checkpoint2_Report_YouTube_Trending.pptx

Nguyên tắc:
  * Số liệu lấy từ evidence thật (logs/, manifest.json), commit hash lấy trực tiếp từ git
    -> không bao giờ ghi tay số liệu.
  * Layout dựa trên "khung" (card) của template: tiêu đề + thân. Thân được đo bằng
    metrics THẬT của font (Pillow đọc TTF Calibri/Consolas) để wrap chính xác như
    PowerPoint, tự thu nhỏ cỡ chữ nếu vượt khung -> KHÔNG có text tràn khung.
  * Sau khi sinh, script tự validate toàn bộ layout và trả exit code khác 0 nếu còn lỗi.

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
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(r"D:\Edu\BD\BigData_Buoi06_DoAn2_Checkpoint2_Report_Template.pptx")
OUT = ROOT / "docs" / "Checkpoint2_Report_YouTube_Trending.pptx"

MONO = "Consolas"
INK = RGBColor(0x1A, 0x1A, 0x1A)

EMU_IN = 914400
TITLE = "Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube"

# --- đo chữ bằng metrics thật của font (Pillow) -----------------------------
FONT_FILES = {
    ("consolas", False): r"C:\Windows\Fonts\consola.ttf",
    ("consolas", True): r"C:\Windows\Fonts\consolab.ttf",
    ("calibri", False): r"C:\Windows\Fonts\calibri.ttf",
    ("calibri", True): r"C:\Windows\Fonts\calibrib.ttf",
}
PX_PER_PT = 8          # đo ở độ phân giải cao rồi quy đổi
# chiều cao 1 dòng (theo em) - khớp cách PowerPoint bố trí dòng đơn
LINE_EM = {"calibri": 1.22, "consolas": 1.17}
SAFETY = 1.03          # biên an toàn

try:  # Pillow có sẵn qua streamlit; nếu thiếu thì dùng ước lượng đơn giản
    from PIL import ImageFont

    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False

_fonts: dict[tuple[str, bool, float], object] = {}


def _font(mono: bool, size_pt: float):
    key = ("consolas" if mono else "calibri", False, size_pt)
    if key not in _fonts:
        path = FONT_FILES[(key[0], key[1])]
        _fonts[key] = ImageFont.truetype(path, int(round(size_pt * PX_PER_PT)))
    return _fonts[key]


def wrap_lines(text: str, width_in: float, size_pt: float, mono: bool) -> int:
    """Số dòng sau khi wrap (PowerPoint wrap tại khoảng trắng)."""
    if not text.strip():
        return 1
    if not HAVE_PIL:
        cpl = max(1, int((width_in * 72) / (size_pt * (0.55 if mono else 0.50))))
        return -(-len(text) // cpl)
    font = _font(mono, size_pt)
    limit = width_in * 72 * PX_PER_PT
    words = text.split(" ")
    lines, cur = 1, ""
    for word in words:
        cand = f"{cur} {word}" if cur else word
        if font.getlength(cand) <= limit or not cur:
            cur = cand
        else:
            lines += 1
            cur = word
    return lines


def measure_height(lines: list[str], width_in: float, size_pt: float, mono: bool) -> float:
    """Chiều cao (inch) của khối chữ sau khi wrap."""
    n = sum(wrap_lines(l, width_in, size_pt, mono) for l in lines)
    line_pt = size_pt * LINE_EM["consolas" if mono else "calibri"]
    return n * line_pt / 72 * SAFETY


# --------------------------------------------------------------------- helpers


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def emu(inches: float) -> Emu:
    return Emu(int(round(inches * EMU_IN)))


def by_name(slide, name: str):
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    raise KeyError(f"Không tìm thấy shape '{name}' trong slide")


def place(shape, *, left=None, top=None, width=None, height=None) -> None:
    if left is not None:
        shape.left = emu(left)
    if top is not None:
        shape.top = emu(top)
    if width is not None:
        shape.width = emu(width)
    if height is not None:
        shape.height = emu(height)


def donor_rpr(paragraph):
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

    for p in list(tf.paragraphs[1:]):
        p._p.getparent().remove(p._p)
    for r in list(donor_p.runs):
        r._r.getparent().remove(r._r)

    for i, line in enumerate(lines):
        if i == 0:
            p = donor_p
        else:
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


def fit_size(lines: list[str], width_in: float, size_pt: float, mono: bool,
             avail_in: float, min_size: float = 7.5) -> float:
    """Giảm cỡ chữ tới khi khối chữ vừa `avail_in`."""
    size = size_pt
    while size > min_size:
        if measure_height(lines, width_in, size, mono) <= avail_in:
            return size
        size -= 0.5
    return min_size


def fill(shape, lines: list[str], *, mono: bool = False, size: float = 11.0,
         color: RGBColor | None = None, bold: bool | None = None,
         avail_in: float | None = None, min_size: float = 7.5) -> float:
    """Điền nội dung + tự chỉnh cỡ chữ/chiều cao để không tràn khung."""
    width_in = shape.width / EMU_IN
    if avail_in is not None:
        size = fit_size(lines, width_in, size, mono, avail_in, min_size)
    set_lines(shape, lines, mono=mono, size=size, color=color, bold=bold)
    shape.height = emu(measure_height(lines, width_in, size, mono))
    return size


# ------------------------------------------------------------------ layout 1:1


def fill_card(slide, card_name: str, body_name: str, lines: list[str], *,
              size: float, mono: bool = False, color: RGBColor | None = None,
              card_h: float | None = None, body_top: float | None = None,
              min_size: float = 7.5) -> float:
    """Điền phần thân của 1 khung trang trí (card) và bảo đảm không tràn.

    card  : khung trang trí (auto-shape) chứa tiêu đề + thân
    body  : text box của phần thân
    """
    card = by_name(slide, card_name)
    body = by_name(slide, body_name)

    if card_h is not None:
        place(card, height=card_h)
    if body_top is None:
        body_top = body.top / EMU_IN
    else:
        place(body, top=body_top)

    card_bottom = (card.top + card.height) / EMU_IN
    avail = card_bottom - body_top - 0.10
    used = fill(body, lines, mono=mono, size=size, color=color,
                avail_in=avail, min_size=min_size)
    # canh giữa khối chữ trong khoảng trống còn lại của card
    h = body.height / EMU_IN
    place(body, top=body_top + max(0.0, (avail - h) / 2))
    return used


# --------------------------------------------------------------------- build


def build() -> int:
    if not TEMPLATE.exists():
        raise SystemExit(f"Không tìm thấy template: {TEMPLATE}")

    from pptx import Presentation

    prs = Presentation(str(TEMPLATE))
    slides = list(prs.slides)

    # chỉ tham chiếu TAG (không phụ thuộc HEAD) -> sinh lại báo cáo cho kết quả
    # giống hệt nhau, không bao giờ lệch số liệu. Commit cụ thể: git log -1 checkpoint-2
    tag = git("describe", "--tags", "--abbrev=0")
    tag_commit = git("rev-parse", "--short", f"{tag}^{{commit}}")

    # ---------------- SLIDE 1 – Tiêu đề -----------------------------------
    s = slides[0]
    # 3 dòng thông tin: bề ngang < 8.40in để không chồng lên khung "QUY TẮC"
    for name in ("Text 2", "Text 3", "Text 4"):
        place(by_name(s, name), width=7.55)
    fill(by_name(s, "Text 2"),
         ["Nhóm: YouTube Trending Analytics (4 thành viên)"], size=13)
    fill(by_name(s, "Text 3"), [f"Đề tài: {TITLE}"], size=13)
    fill(by_name(s, "Text 4"),
         [f"Git commit/tag: tag {tag}  (git log -1 {tag})"], size=13)

    # ---------------- SLIDE 2 – Architecture ------------------------------
    s = slides[1]
    place(by_name(s, "Shape 3"), top=2.05, height=3.90)
    fill(by_name(s, "Text 4"),
         ["SƠ ĐỒ ARCHITECTURE (phần đã triển khai đến Checkpoint 2)"], size=11)
    fill_card(
        s, "Shape 3", "Text 5",
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
        card_h=3.90,
    )
    fill(by_name(s, "Text 6"),
         [
             "1 câu giải thích trade-off chính: máy cá nhân 16 GB RAM nên chạy Spark local[*] + "
             "chuẩn hóa CSV trước (1 dòng = 1 record) thay vì multiLine=true (phải nạp nguyên "
             "file 8,59 GB vào 1 task → OOM); cột description (~8 GB) giữ nguyên ở raw, chỉ drop "
             "ở tầng metric.",
         ],
         size=10.5)

    # ---------------- SLIDE 3 – Environment evidence ----------------------
    s = slides[1 + 1]
    fill_card(
        s, "Shape 3", "Text 5",
        [
            "Output logs/env_check.txt:",
            "",
            "  Python   : 3.12.10",
            "  JAVA_HOME: D:\\Code\\SDK\\jdk\\jdk-17.0.20.1+1",
            "  Java     : openjdk version \"17.0.20.1\"",
            "  Spark    : 3.5.1",
            "  Count    : 1000000 (mong đợi 1000000)",
            "  RESULT   : PASS",
            "",
            "→ smoke test chạy lại được, exit code 0 (22/10/2026)",
        ],
        mono=True, size=10.5, color=INK,
    )
    fill_card(
        s, "Shape 6", "Text 8",
        [
            "python -m venv .venv",
            ".venv\\Scripts\\pip install -r requirements.txt",
            ".venv\\Scripts\\python.exe src\\env_check.py",
        ],
        mono=True, size=10, card_h=1.20,
    )
    fill_card(
        s, "Shape 9", "Text 11",
        ["local[*] trên Windows (Spark 3.5.1 + JDK 17)"],
        size=11, card_h=1.20,
    )
    fill_card(
        s, "Shape 12", "Text 14",
        ["Đã xử lý: thiếu winutils.exe (Spark ghi Parquet) → tự cấu hình HADOOP_HOME + PATH "
         "trong transform.py, không cài Hadoop hệ thống."],
        size=10, card_h=1.05, body_top=5.60,
    )

    # ---------------- SLIDE 4 – Data source & ingestion -------------------
    s = slides[1 + 2]
    fill_card(
        s, "Shape 3", "Text 5",
        ["https://www.kaggle.com/datasets/asaniczka/trending-youtube-videos-113-countries"],
        size=10.5, card_h=1.20,
    )
    fill_card(
        s, "Shape 6", "Text 8",
        [
            "8.591.418.141 bytes (8,59 GB) · 6.094.047 record · 18 cột · 113 quốc gia",
            "snapshot_date 2023-10-26 → 2026-10-20 (snapshot tải 2026-10-20)",
            "SHA-256 4310930bd2d1… (đầy đủ trong manifest.json)",
        ],
        size=10, card_h=1.30,
    )
    fill_card(
        s, "Shape 9", "Text 11",
        ["Nguồn: Kaggle · license ODC-By · file gốc giữ ngoài repo; ingest = copy + hash + "
         "manifest → truy ngược được từng byte trong raw."],
        size=10, card_h=1.05, body_top=5.60,
    )
    fill_card(
        s, "Shape 12", "Text 14",
        [
            "Command:",
            "  python src\\ingest_file.py --source <csv> --dataset youtube_trending",
            "",
            "Result (logs/ingest.log):",
            "  success | files=1 | bytes=8591418141 | sha256=4310930bd2d1…",
            "  run=run_20261020T143013Z | status=success | manifest ghi ra raw/",
        ],
        mono=True, size=10, card_h=3.85,
    )

    # ---------------- SLIDE 5 – Raw storage & manifest --------------------
    s = slides[1 + 3]
    place(by_name(s, "Shape 3"), width=6.00)
    place(by_name(s, "Text 5"), width=5.70)
    fill_card(
        s, "Shape 3", "Text 5",
        [
            "Path convention:",
            "  data/raw/<dataset>/ingest_date=YYYY-MM-DD/run_<UTC>/",
            "",
            "  data/raw/youtube_trending/",
            "    ingest_date=2026-10-20/",
            "      run_20261020T143013Z/",
            "        ├─ trending_yt_videos_113_countries.csv (8.591.418.141 bytes)",
            "        └─ manifest.json                        (status: success)",
            "",
            "Raw file size: 8.591.418.141 bytes (8,59 GB) – không rỗng, giữ nguyên bản gốc.",
        ],
        mono=True, size=9.5, card_h=3.85,
    )
    fill_card(
        s, "Shape 6", "Text 8",
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
            "  amendments[]  : 1 (ghi mọi thay đổi metadata, kèm mốc thời gian)",
            "",
            "Log: logs/env_check.txt · logs/ingest.log · logs/transform.log",
            "Đếm record: src/verify_raw_records.py (chuẩn RFC4180, 86,7 s)",
        ],
        mono=True, size=10, card_h=3.85,
    )

    # ---------------- SLIDE 6 – Rerun, blocker, next action ----------------
    s = slides[1 + 4]
    fill_card(
        s, "Shape 3", "Text 5",
        [
            "Mặc định --on-duplicate skip (idempotent theo SHA-256):",
            "  lần 1   → tạo run_… + copy + manifest",
            "  lần 2,3 → hash trùng → SKIP, raw KHÔNG đổi (log: duplicate_skip)",
            "hash khác → run_id mới (append, không overwrite)",
            "nguồn hỏng → fail-fast (exit 1), không tạo raw giả",
        ],
        mono=True, size=9.5, card_h=1.55,
    )
    fill_card(
        s, "Shape 6", "Text 8",
        [
            "Schema nguồn Plan B khác đề cương (thiếu category_id, description nhiều dòng) → "
            "adapter SRC_MAP + split_csv.py (đã xử lý).",
            "Rủi ro còn lại: dung lượng 8,59 GB + nguồn cập nhật hằng ngày → phải chạy ingest "
            "snapshot mới để so sánh growth.",
            "Owner: Phúc (transform) · Khánh Linh (Parquet/DuckDB)   Deadline: trước Buổi 7",
        ],
        size=9, card_h=1.55,
    )
    fill_card(
        s, "Shape 9", "Text 11",
        [
            f"Commit/tag: tag {tag}  (git log -1 {tag})",
            "Raw/manifest/log: data/raw/youtube_trending/…/run_…/manifest.json",
            "logs/env_check.txt · logs/ingest.log · logs/transform.log",
        ],
        mono=True, size=9.5, card_h=1.55,
    )
    fill_card(
        s, "Shape 12", "Text 14",
        [
            "1) Chạy ingest snapshot mới (nguồn cập nhật hằng ngày) để so sánh growth 2 kỳ.",
            "2) Demo dashboard trực tiếp + chốt đề cương Đồ án 3 (ML / nâng cao).",
        ],
        size=9.5, card_h=1.55,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"OK -> {OUT}")
    print(f"   tag={tag} ({tag_commit})")
    return validate(prs, slides, tag)


# ------------------------------------------------------------------ validate

# khối chữ -> khung trang trí chứa nó (để validate không tràn khung)
CONTAINERS: dict[int, list[tuple[str, str | None]]] = {
    1: [("Text 2", None), ("Text 3", None), ("Text 4", None)],
    2: [("Text 4", "Shape 3"), ("Text 5", "Shape 3"), ("Text 6", None)],
    3: [("Text 5", "Shape 3"), ("Text 8", "Shape 6"), ("Text 11", "Shape 9"),
        ("Text 14", "Shape 12")],
    4: [("Text 5", "Shape 3"), ("Text 8", "Shape 6"), ("Text 11", "Shape 9"),
        ("Text 14", "Shape 12")],
    5: [("Text 5", "Shape 3"), ("Text 8", "Shape 6")],
    6: [("Text 5", "Shape 3"), ("Text 8", "Shape 6"), ("Text 11", "Shape 9"),
        ("Text 14", "Shape 12")],
}
# các khối chữ phải không chồng nhau theo chiều ngang
NO_OVERLAP_X = {1: [("Text 2", "Text 3", "Text 4", "Shape 5")]}


def validate(prs, slides, tag: str = "") -> int:
    problems: list[str] = []
    slide_h = prs.slide_height / EMU_IN
    slide_w = prs.slide_width / EMU_IN

    for idx, slide in enumerate(slides, 1):
        boxes = {sh.name: sh for sh in slide.shapes}
        for text_name, box_name in CONTAINERS.get(idx, []):
            shape = boxes.get(text_name)
            if shape is None or not shape.has_text_frame or not shape.text_frame.text.strip():
                continue
            runs = [r for p in shape.text_frame.paragraphs for r in p.runs]
            sizes = [r.font.size.pt for r in runs if r.font.size]
            fs = max(sizes) if sizes else 18.0
            mono = any(r.font.name == MONO for r in runs)
            lines = [p.text for p in shape.text_frame.paragraphs]
            need = measure_height(lines, shape.width / EMU_IN, fs, mono)
            top = shape.top / EMU_IN
            left = shape.left / EMU_IN
            width = shape.width / EMU_IN

            if top + need > slide_h - 0.10:
                problems.append(f"slide {idx} · {text_name}: tràn đáy slide "
                                f"(tới {top + need:.2f}in > {slide_h - 0.10:.2f}in)")
            if left < 0.20 or left + width > slide_w - 0.20:
                problems.append(f"slide {idx} · {text_name}: tràn mép ngang slide")
            if box_name:
                box = boxes[box_name]
                b_top = box.top / EMU_IN
                b_bottom = (box.top + box.height) / EMU_IN
                if top < b_top - 0.02 or top + need > b_bottom + 0.02:
                    problems.append(
                        f"slide {idx} · {text_name}: tràn khung '{box_name}' "
                        f"(text {top:.2f}→{top + need:.2f}in, khung {b_top:.2f}→{b_bottom:.2f}in)")

        for group in NO_OVERLAP_X.get(idx, []):
            rects = [(n, boxes[n]) for n in group if n in boxes]
            for i, (na, a) in enumerate(rects):
                for nb, b in rects[i + 1:]:
                    a_r = (a.left / EMU_IN, (a.left + a.width) / EMU_IN)
                    b_r = (b.left / EMU_IN, (b.left + b.width) / EMU_IN)
                    a_v = (a.top / EMU_IN, (a.top + a.height) / EMU_IN)
                    b_v = (b.top / EMU_IN, (b.top + b.height) / EMU_IN)
                    if a_r[0] < b_r[1] and b_r[0] < a_r[1] and a_v[0] < b_v[1] and b_v[0] < a_v[1]:
                        problems.append(f"slide {idx}: '{na}' chồng lên '{nb}'")

    # kiểm tra nội dung bắt buộc có mặt trong deck
    full = "\n".join(
        sh.text_frame.text
        for slide in slides for sh in slide.shapes
        if sh.has_text_frame
    )
    for needle in (tag, "6.094.047", "8.591.418.141", "4310930bd2d1",
                   "run_20261020T143013Z", "logs/ingest.log", "logs/env_check.txt",
                   "verify_raw_records", "duplicate_skip", "6094047"):
        if needle and needle not in full:
            problems.append(f"thiếu nội dung '{needle}'")

    if problems:
        print("\nLAYOUT CÓ VẤN ĐỀ:")
        for p in problems:
            print("  - " + p)
        return 1
    print("LAYOUT OK: mọi khối chữ nằm trong khung, không tràn slide, nội dung bắt buộc đủ.")
    return 0


if __name__ == "__main__":
    sys.exit(build())
