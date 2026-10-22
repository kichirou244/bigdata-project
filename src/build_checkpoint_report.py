"""Sinh bản Checkpoint Report đã điền từ template chính thức của Buổi 6.

Template (do GV cung cấp, KHÔNG sửa bản gốc):
  D:\\Edu\\BD\\BigData_Buoi06_DoAn2_Checkpoint2_Report_Template.pptx

Output:
  docs/Checkpoint2_Report_YouTube_Trending.pptx

Nguyên tắc:
  * Số liệu lấy từ evidence thật (logs/, manifest.json); commit chỉ tham chiếu qua
    tag -> không bao giờ ghi tay số liệu, sinh lại bao nhiêu lần cũng ra 1 kết quả.
  * Font: template dùng Aptos nhưng máy này KHÔNG cài Aptos -> mọi run được set
    tường minh Calibri (body) / Consolas (số liệu), tránh PowerPoint tự thay font
    (font thay thế rộng hơn sẽ làm chữ tràn khung).
  * Khung (card) được tính theo chiều cao nội dung thật: đo bằng metrics của TTF
    (Pillow) + wrap theo từng từ -> chiều cao khung = tiêu đề + nội dung + padding,
    phần dư được chia đều thành khoảng cách => không còn khoảng trống chết.
  * validate() kiểm tra: chữ nằm trong khung, không tràn slide, không chồng nhau,
    không còn placeholder, đủ nội dung bắt buộc, không còn font Aptos.
    Exit code != 0 nếu còn lỗi.

Chạy:
  python src/build_checkpoint_report.py
"""
from __future__ import annotations

import copy
import re
import subprocess
import sys
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(r"D:\Edu\BD\BigData_Buoi06_DoAn2_Checkpoint2_Report_Template.pptx")
OUT = ROOT / "docs" / "Checkpoint2_Report_YouTube_Trending.pptx"

EMU_IN = 914400
BODY_FONT = "Calibri"
MONO_FONT = "Consolas"

NAVY = RGBColor(0x0B, 0x1F, 0x33)
BLUE = RGBColor(0x1D, 0x4E, 0xD8)
CYAN = RGBColor(0x06, 0xB6, 0xD4)
GRAY = RGBColor(0x5B, 0x6B, 0x7A)
MUTED = RGBColor(0x8A, 0x9A, 0xA8)
GREEN = RGBColor(0x0E, 0x7C, 0x4A)
RED = RGBColor(0xB4, 0x23, 0x18)
LIGHT = RGBColor(0xD5, 0xE3, 0xEE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RULE = RGBColor(0xDB, 0xE3, 0xEA)
CK_FILL = RGBColor(0xEF, 0xF6, 0xFF)   # nền xanh nhạt: phần thuộc checkpoint
P3_FILL = RGBColor(0xF4, 0xF6, 0xF8)   # nền xám nhạt: phần làm thêm (P3)
DARK_SLIDE = RGBColor(0x07, 0x1C, 0x2D)

TITLE = "Phân tích Xu hướng & Tốc độ Tăng trưởng Video Thịnh hành YouTube"

# --- bố cục chung ------------------------------------------------------------
X_LEFT, X_RIGHT = 0.85, 6.85
CARD_W = 5.55
FULL_X, FULL_W = 0.85, 11.63
TOP, BOTTOM = 2.00, 6.95

CARD_PAD_X = 0.28          # padding trái/phải trong card
CARD_TITLE_DY = 0.14       # tiêu đề card cách mép trên
CARD_TITLE_H = 0.34
CARD_BODY_DY = 0.58        # thân cách mép trên của card
CARD_PAD_B = 0.16
CARD_GAP = 0.20

# --- đo chữ bằng metrics thật của font ---------------------------------------
FONT_FILES = {
    ("calibri", False): r"C:\Windows\Fonts\calibri.ttf",
    ("calibri", True): r"C:\Windows\Fonts\calibrib.ttf",
    ("consolas", False): r"C:\Windows\Fonts\consola.ttf",
    ("consolas", True): r"C:\Windows\Fonts\consolab.ttf",
}
PX_PER_PT = 8
LINE_EM = {"calibri": 1.22, "consolas": 1.17}
SAFETY = 1.06              # biên an toàn: chừa 6% chiều cao cho sai số render

try:
    from PIL import ImageFont

    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False

_fonts: dict[tuple[str, bool, float], object] = {}


def _font(mono: bool, bold: bool, size_pt: float):
    key = (("consolas" if mono else "calibri"), bold, size_pt)
    if key not in _fonts:
        path = FONT_FILES[key[:2]]
        _fonts[key] = ImageFont.truetype(path, int(round(size_pt * PX_PER_PT)))
    return _fonts[key]


def wrap_lines(text: str, width_in: float, size_pt: float, mono: bool,
               bold: bool = False) -> int:
    """Số dòng sau khi wrap (PowerPoint wrap tại khoảng trắng)."""
    if not text.strip():
        return 1
    if not HAVE_PIL:
        cpl = max(1, int((width_in * 72) / (size_pt * (0.55 if mono else 0.50))))
        return -(-len(text) // cpl)
    font = _font(mono, bold, size_pt)
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


def measure_height(lines, width_in: float, size_pt: float, mono: bool) -> float:
    """Chiều cao (inch) của khối chữ sau khi wrap."""
    n = 0
    for line in lines:
        text, bold = line_spec(line)
        n += wrap_lines(text, width_in, size_pt, mono, bold)
    line_pt = size_pt * LINE_EM["consolas" if mono else "calibri"]
    return n * line_pt / 72 * SAFETY


def line_spec(line) -> tuple[str, bool]:
    """Chuẩn hóa 1 dòng: str | (text, color) | (text, color, bold) -> (text, bold)."""
    if isinstance(line, tuple):
        return line[0], (line[2] if len(line) > 2 else False)
    return line, False


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


def set_lines(shape, lines, *, mono: bool = False, size: float = 12.0,
              color: RGBColor = GRAY) -> None:
    """Ghi nội dung vào text box, giữ style khung của template (copy đoạn mẫu)."""
    tf = shape.text_frame
    donor_p = tf.paragraphs[0]
    rpr = donor_rpr(donor_p)
    donor_p_xml = copy.deepcopy(donor_p._p)

    for p in list(tf.paragraphs[1:]):
        p._p.getparent().remove(p._p)
    for r in list(donor_p.runs):
        r._r.getparent().remove(r._r)

    for i, spec in enumerate(lines):
        text, bold = line_spec(spec)
        col = spec[1] if isinstance(spec, tuple) else color
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
        run.text = text
        if rpr is not None:
            run._r.insert(0, copy.deepcopy(rpr))
        run.font.name = MONO_FONT if mono else BODY_FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = col


def fit_size(lines, width_in: float, size_pt: float, mono: bool, avail_in: float,
             min_size: float = 8.5) -> float:
    """Giảm cỡ chữ (bước 0.25) tới khi khối chữ vừa `avail_in`."""
    size = size_pt
    while size > min_size:
        if measure_height(lines, width_in, size, mono) <= avail_in:
            return size
        size -= 0.25
    return min_size


def content_height(lines, width_in: float, size_pt: float, mono: bool) -> float:
    return measure_height(lines, width_in, size_pt, mono)


def longest_word_width(lines, size_pt: float, mono: bool) -> float:
    """Bề rộng (inch) của từ dài nhất – từ không có khoảng trắng thì không wrap được."""
    widest = 0.0
    for line in lines:
        text, bold = line_spec(line)
        for word in text.split(" "):
            if not word:
                continue
            if HAVE_PIL:
                w = _font(mono, bold, size_pt).getlength(word) / (72 * PX_PER_PT)
            else:
                w = len(word) * size_pt * (0.55 if mono else 0.50) / 72
            widest = max(widest, w)
    return widest


def fill(shape, lines, *, mono: bool = False, size: float = 12.0,
         color: RGBColor = GRAY, avail_in: float | None = None,
         min_size: float = 8.5, align: str = "center") -> float:
    """Điền nội dung + tự chỉnh cỡ chữ/chiều cao để không tràn khung."""
    width_in = shape.width / EMU_IN
    if avail_in is not None:
        size = fit_size(lines, width_in, size, mono, avail_in, min_size)
    set_lines(shape, lines, mono=mono, size=size, color=color)
    h = content_height(lines, width_in, size, mono)
    shape.height = emu(h)
    tf = shape.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE if align == "center" else MSO_ANCHOR.TOP
    tf.word_wrap = True
    return size


# ------------------------------------------------------------- card + vùng chứa

REPORT: list[tuple[str, float, float, float]] = []   # card, size, used, area


def card(slide, card_name: str, title_name: str, body_name: str, lines, *,
         title_text: str, size: float = 12.0, mono: bool = False,
         x: float = X_LEFT, w: float = CARD_W,
         top: float = TOP, height: float = 1.2, min_size: float = 8.5,
         color: RGBColor = GRAY, title_size: float = 16.0,
         title_color: RGBColor = BLUE) -> float:
    """Đặt 1 card: khung, tiêu đề, thân (căn giữa theo chiều dọc), không tràn."""
    card_shape = by_name(slide, card_name)
    place(card_shape, left=x, top=top, width=w, height=height)

    title_shape = by_name(slide, title_name)
    place(title_shape, left=x + CARD_PAD_X, top=top + CARD_TITLE_DY,
          width=w - 2 * CARD_PAD_X, height=CARD_TITLE_H)
    set_lines(title_shape, [(title_text, title_color, True)], size=title_size)
    title_shape.text_frame.word_wrap = True
    title_shape.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE

    body = by_name(slide, body_name)
    body_w = w - 2 * CARD_PAD_X
    body_top = top + CARD_BODY_DY
    body_bottom = top + height - CARD_PAD_B
    avail = max(0.2, body_bottom - body_top)

    used = fit_size(lines, body_w, size, mono, avail, min_size)
    place(body, left=x + CARD_PAD_X, width=body_w)
    set_lines(body, lines, mono=mono, size=used, color=color)
    body.text_frame.word_wrap = True
    body.text_frame.vertical_anchor = MSO_ANCHOR.TOP

    h = content_height(lines, body_w, used, mono)
    body.height = emu(min(h, avail))
    place(body, top=body_top + max(0.0, (avail - h) / 2))
    REPORT.append((card_name, used, h, avail))
    return used


def stack(slide, cards: list[dict], *, x: float = X_LEFT, w: float = CARD_W,
          top: float = TOP, bottom: float = BOTTOM, gap: float = CARD_GAP) -> None:
    """Xếp n card theo chiều dọc, chia đều phần dư -> khung kín cả cột."""
    n = len(cards)
    avail = bottom - top - gap * (n - 1)
    # 1) chiều cao tự nhiên tại cỡ chữ ưa thích
    nat = []
    for c in cards:
        bw = w - 2 * CARD_PAD_X
        h = content_height(c["lines"], bw, c.get("size", 12.0), c.get("mono", False))
        nat.append(max(h + CARD_BODY_DY + CARD_PAD_B, 1.05))
    # 2) nếu tổng vượt chỗ trống -> giảm đều cỡ chữ
    shrink = 0.0
    while sum(nat) > avail and shrink < 4.0:
        shrink += 0.25
        nat = []
        for c in cards:
            bw = w - 2 * CARD_PAD_X
            size = max(8.5, c.get("size", 12.0) - shrink)
            h = content_height(c["lines"], bw, size, c.get("mono", False))
            nat.append(max(h + CARD_BODY_DY + CARD_PAD_B, 1.05))
    extra = max(0.0, (avail - sum(nat)) / n)

    y = top
    for c, h_nat in zip(cards, nat):
        card(slide, c["card"], c["title"], c["body"], c["lines"],
             title_text=c["title_text"],
             size=max(8.5, c.get("size", 12.0) - shrink),
             mono=c.get("mono", False), x=x, w=w, top=y, height=h_nat + extra,
             min_size=c.get("min_size", 8.5), color=c.get("color", GRAY),
             title_size=c.get("title_size", 16.0),
             title_color=c.get("title_color", BLUE))
        y += h_nat + extra + gap


def natural_height(c: dict, w: float, shrink: float = 0.0) -> float:
    bw = w - 2 * CARD_PAD_X
    size = max(8.5, c.get("size", 12.0) - shrink)
    h = content_height(c["lines"], bw, size, c.get("mono", False))
    return max(h + CARD_BODY_DY + CARD_PAD_B, 1.05)


def grid2x2(slide, cells: list[dict], *, top: float = TOP, bottom: float = BOTTOM,
            gap: float = CARD_GAP) -> None:
    """2 cột x 2 hàng: 2 card cùng hàng luôn cao bằng nhau (hàng thẳng)."""
    avail = bottom - top - gap
    shrink = 0.0
    while shrink < 4.0:
        nat = [natural_height(c, CARD_W, shrink) for c in cells]
        if max(nat[0], nat[1]) + max(nat[2], nat[3]) <= avail:
            break
        shrink += 0.25
    nat = [natural_height(c, CARD_W, shrink) for c in cells]
    row1 = max(nat[0], nat[1])
    row2 = max(nat[2], nat[3])
    extra = max(0.0, (avail - row1 - row2) / 2)
    row1 += extra
    row2 += extra
    slots = [(cells[0], row1, top, X_LEFT), (cells[1], row1, top, X_RIGHT),
             (cells[2], row2, top + row1 + gap, X_LEFT),
             (cells[3], row2, top + row1 + gap, X_RIGHT)]
    for c, h, y, x in slots:
        card(slide, c["card"], c["title"], c["body"], c["lines"],
             title_text=c["title_text"],
             size=max(8.5, c.get("size", 12.0) - shrink),
             mono=c.get("mono", False), x=x, w=CARD_W, top=y, height=h,
             min_size=c.get("min_size", 8.5), color=c.get("color", GRAY),
             title_size=c.get("title_size", 16.0),
             title_color=c.get("title_color", BLUE))


# ------------------------------------------------------- shape tự tạo (slide 2)


def add_shape(slide, kind, x, y, w, h, *, fill_color, line_color, line_w=1.0,
              radius: float | None = None):
    shape = slide.shapes.add_shape(kind, emu(x), emu(y), emu(w), emu(h))
    style = shape._element.find(qn("p:style"))
    if style is not None:                      # bỏ style theme (tránh shadow mặc định)
        shape._element.remove(style)
    shape.shadow.inherit = False
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(line_w)
    if radius is not None:
        shape.adjustments[0] = radius
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    return shape


def add_text(slide, x, y, w, h, lines, *, size=12.0, color=GRAY, mono=False,
             anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(emu(x), emu(y), emu(w), emu(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    set_lines(box, lines, mono=mono, size=size, color=color)
    # chiều cao khung = đúng chiều cao chữ (không để khung thiếu chỗ)
    box.height = emu(content_height(lines, w, size, mono))
    return box


# --------------------------------------------------------------------- build


def build() -> int:
    if not TEMPLATE.exists():
        raise SystemExit(f"Không tìm thấy template: {TEMPLATE}")

    from pptx import Presentation

    prs = Presentation(str(TEMPLATE))
    slides = list(prs.slides)

    # chỉ tham chiếu TAG (không phụ thuộc HEAD) -> sinh lại báo cáo cho kết quả
    # giống hệt nhau. Commit cụ thể: git log -1 checkpoint-2
    tag = git("describe", "--tags", "--abbrev=0")

    # ---------------- SLIDE 1 – Tiêu đề -----------------------------------
    s = slides[0]
    for name, text in (
        ("Text 2", "Nhóm: YouTube Trending Analytics  ·  4 thành viên"),
        ("Text 3", f"Đề tài: {TITLE}"),
        ("Text 4", f"Git commit/tag: tag {tag}   (git log -1 {tag})"),
    ):
        place(by_name(s, name), width=7.45, height=0.34)
        fill(by_name(s, name), [text], size=15.5, color=LIGHT)

    rule = add_shape(s, MSO_SHAPE.RECTANGLE, 0.75, 6.34, 11.83, 0.014,
                     fill_color=RGBColor(0x1E, 0x3A, 0x52), line_color=None)
    rule.name = "Rule 1"
    add_text(
        s, 0.75, 6.48, 11.83, 0.34,
        ["Buổi 6 · 20/10/2026   |   Phan Đình Bảo · Trương Đình Phúc · "
         "Trần Thị Khánh Linh · Đoàn Ngọc Trân Châu"],
        size=12, color=RGBColor(0x93, 0xAD, 0xC2),
    ).name = "Footer 1"

    # ---------------- SLIDE 2 – Architecture ------------------------------
    s = slides[1]
    card_h = 4.95
    place(by_name(s, "Shape 3"), left=FULL_X, top=TOP, width=FULL_W, height=card_h)
    # bỏ text hướng dẫn còn sót của template (nằm sau sơ đồ)
    leftover = by_name(s, "Text 5")
    leftover._element.getparent().remove(leftover._element)

    t = by_name(s, "Text 4")
    place(t, left=1.13, top=TOP + CARD_TITLE_DY, width=FULL_W - 0.56, height=0.34)
    set_lines(t, ["SƠ ĐỒ ARCHITECTURE — phần đã triển khai đến Checkpoint 2"],
              size=16, color=BLUE)

    stages = [
        ("01", "Kaggle CSV", ["8,59 GB · 113 nước", "6.094.047 record"], True),
        ("02", "ingest_file.py", ["quality gate + SHA-256", "copy nguyên bản"], True),
        ("03", "Raw storage", ["data/raw/…/run_…/", "+ manifest.json"], True),
        ("04", "split_csv.py", ["1 dòng = 1 record", "→ 33 chunk CSV"], False),
        ("05", "Spark 3.5.1", ["local[*] → Parquet", "341 MB, partition"], False),
        ("06", "DuckDB/Streamlit", ["dashboard tương tác", "(P3 – làm thêm)"], False),
    ]
    box_w, box_gap, box_h, box_y = 1.628, 0.26, 1.72, 2.72
    for i, (num, name, detail, in_ck) in enumerate(stages):
        bx = 1.13 + i * (box_w + box_gap)
        accent = BLUE if in_ck else MUTED
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, bx, box_y, box_w, box_h,
                  fill_color=CK_FILL if in_ck else P3_FILL, line_color=accent,
                  line_w=1.0, radius=0.08)
        badge = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, bx + 0.14, box_y + 0.20,
                          0.44, 0.36, fill_color=accent, line_color=None, radius=0.25)
        badge.name = f"Badge {num}"
        set_lines(badge, [(num, WHITE, True)], size=12.5)
        badge.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        for p in badge.text_frame.paragraphs:
            p.alignment = PP_ALIGN.CENTER

        add_text(s, bx + 0.14, box_y + 0.66, box_w - 0.26, 0.44,
                 [(name, NAVY, True)], size=10.5)
        add_text(s, bx + 0.14, box_y + 1.12, box_w - 0.26, 0.56,
                 [(d, MUTED) for d in detail], size=8.5)
        if i < len(stages) - 1:
            add_shape(s, MSO_SHAPE.RIGHT_ARROW, bx + box_w + 0.045,
                      box_y + box_h / 2 - 0.09, 0.17, 0.18,
                      fill_color=MUTED, line_color=None)

    # dòng technology + 2 dải boundary
    add_text(s, 1.13, 4.66, FULL_W - 0.56, 0.30,
             ["Technology:  Python 3.12 · JDK 17 · PySpark 3.5.1 · DuckDB · "
              "Streamlit · Parquet"], size=10.5, color=GRAY)

    for x0, w0, txt, in_ck in (
        (1.13, 5.42, "TRONG CHECKPOINT 2 — 01 → 02 → 03, có evidence chạy thật", True),
        (6.58, 5.34, "BUỔI 7–8 (P3) — 04 → 05 → 06, làm thêm ngoài yêu cầu", False),
    ):
        band = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x0, 5.06, w0, 0.46,
                         fill_color=CK_FILL if in_ck else P3_FILL,
                         line_color=BLUE if in_ck else MUTED, line_w=0.9, radius=0.14)
        band.name = "Band CK" if in_ck else "Band P3"
        set_lines(band, [txt], size=10.5, color=BLUE if in_ck else GRAY)
        band.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE

    add_shape(s, MSO_SHAPE.RECTANGLE, 1.13, 5.74, 10.79, 0.012,
              fill_color=RULE, line_color=None)

    trade = by_name(s, "Text 6")
    place(trade, left=1.13, top=5.88, width=FULL_W - 0.56)
    fill(trade,
         ["Trade-off chính: máy cá nhân 16 GB RAM nên nhóm chạy Spark local[*] và chuẩn hóa "
          "CSV trước (1 dòng = 1 record, 33 chunk) thay vì multiLine=true — nếu không, 1 task "
          "phải nạp nguyên file 8,59 GB vào RAM → OOM. Cột description (~8 GB) giữ nguyên ở "
          "raw, chỉ bỏ ở tầng metric."],
         size=11, color=GRAY, avail_in=0.95)

    # ---------------- SLIDE 3 – Environment evidence ----------------------
    s = slides[2]
    stack(s, [
        dict(card="Shape 3", title="Text 4", body="Text 5", size=12.0, mono=True,
             title_text="EVIDENCE",
             lines=[
                 "$ python src\\env_check.py",
                 "",
                 "=== env_check 2026-10-21T17:11:56+00:00 ===",
                 "Python   : 3.12.10  (E:\\bigdata-project)",
                 "JAVA_HOME: D:\\Code\\SDK\\jdk\\jdk-17.0.20.1+1",
                 'Java     : openjdk version "17.0.20.1"',
                 "Spark    : 3.5.1",
                 "Count    : 1000000 (mong đợi 1000000)",
                 ("RESULT   : PASS  (exit code 0)", GREEN, True),
                 "",
                 "Điều kiện đã kiểm:",
                 "  - .venv riêng, cài đủ từ requirements.txt",
                 "  - JAVA_HOME trỏ JDK 17, không cài Spark",
                 "    system-wide",
                 "  - SparkSession local[*] khởi động được",
                 "  - phép tính Spark trả đúng 1.000.000 dòng",
                 "",
                 "Kết luận: máy khác clone repo là chạy lại được.",
             ]),
    ], top=TOP, bottom=BOTTOM, x=X_LEFT, w=CARD_W)

    stack(s, [
        dict(card="Shape 6", title="Text 7", body="Text 8", size=10.5, mono=True,
             title_text="SETUP COMMAND",
             lines=["python -m venv .venv",
                    ".venv\\Scripts\\pip install -r requirements.txt",
                    ".venv\\Scripts\\python.exe src\\env_check.py"]),
        dict(card="Shape 9", title="Text 10", body="Text 11", size=11.5,
             title_text="EXECUTION MODE",
             lines=["local[*] trên Windows — Spark 3.5.1 + JDK 17",
                    "16 GB RAM · 16 logical CPU · không Docker/cluster"]),
        dict(card="Shape 12", title="Text 13", body="Text 14", size=11.0,
             title_text="BLOCKER (nếu có)",
             lines=["Thiếu winutils.exe khi Spark ghi Parquet trên Windows.",
                    "Đã xử lý: transform.py tự set HADOOP_HOME + PATH vào "
                    "hadoop/bin trong repo — không cài Hadoop hệ thống."]),
    ], top=TOP, bottom=BOTTOM, x=X_RIGHT, w=CARD_W)

    # ---------------- SLIDE 4 – Data source & ingestion -------------------
    s = slides[3]
    stack(s, [
        dict(card="Shape 3", title="Text 4", body="Text 5", size=10.5, mono=True,
             title_text="SOURCE",
             lines=["Dataset: Trending YouTube Videos (113 countries)",
                    "https://www.kaggle.com/datasets/asaniczka/",
                    "trending-youtube-videos-113-countries",
                    "tải về 2026-10-20 · giữ 1 file gốc, không sửa"]),
        dict(card="Shape 6", title="Text 7", body="Text 8", size=11.0,
             title_text="SCALE / VERSION",
             lines=["8.591.418.141 bytes (8,59 GB)",
                    "6.094.047 record · 18 cột · 113 quốc gia",
                    "snapshot 2023-10-26 → 2026-10-20"]),
        dict(card="Shape 9", title="Text 10", body="Text 11", size=11.0,
             title_text="PROVENANCE",
             lines=["Kaggle · license ODC-By · ghi rõ nguồn khi dùng lại.",
                    "ingest = copy + SHA-256 + manifest → truy ngược được "
                    "từng byte trong raw.",
                    "File 8,59 GB không commit; chỉ commit manifest + log."]),
    ], top=TOP, bottom=BOTTOM, x=X_LEFT, w=CARD_W)

    stack(s, [
        dict(card="Shape 12", title="Text 13", body="Text 14", size=11.0, mono=True,
             title_text="INGESTION EVIDENCE",
             lines=[
                 "$ python src\\ingest_file.py --source <csv> \\",
                 "      --dataset youtube_trending",
                 "",
                 "2026-10-20T14:30:40 | success | files=1",
                 "  bytes=8591418141",
                 "  sha256=4310930bd2d1…",
                 ("  run=run_20261020T143013Z", GRAY, True),
                 "2026-10-20T14:30:40 | manifest",
                 "  data\\raw\\youtube_trending\\",
                 "    ingest_date=2026-10-20\\run_20261020T143013Z\\",
                 "    manifest.json",
                 "",
                 "$ python src\\verify_raw_records.py",
                 "2026-10-21T17:20:17 | verify_records",
                 "  records=6,094,047",
                 "  physical_lines=134,442,959 (multi_line=True)",
                 "",
                 "Chạy lại 3 lần cùng file: duplicate_skip x3",
                 ("→ raw KHÔNG đổi, vẫn đúng 1 run", GREEN, True),
                 "",
                 "Exit code = 0 · raw chỉ được ghi 1 lần.",
             ]),
    ], top=TOP, bottom=BOTTOM, x=X_RIGHT, w=CARD_W)

    # ---------------- SLIDE 5 – Raw storage & manifest --------------------
    s = slides[4]
    place(by_name(s, "Shape 3"), width=5.80)
    stack(s, [
        dict(card="Shape 3", title="Text 4", body="Text 5", size=11.0, mono=True, w=5.80,
             title_text="RAW STORAGE",
             lines=[
                 "data/raw/",
                 "  youtube_trending/",
                 "    ingest_date=2026-10-20/",
                 "      run_20261020T143013Z/",
                 "        trending_yt_videos_113_countries.csv",
                 "          8.591.418.141 bytes (8,59 GB)",
                 "        manifest.json   (status: success)",
                 "",
                 "Path convention:",
                 "  data/raw/<dataset>/",
                 "    ingest_date=YYYY-MM-DD/run_<UTC>/",
                 "",
                 "Raw file: không rỗng, giữ nguyên 100% bản gốc",
                 "(không sửa 1 byte so với nguồn tải về).",
                 "Đã kiểm: size + SHA-256 khớp manifest.",
             ]),
    ], x=X_LEFT, w=5.80)

    stack(s, [
        dict(card="Shape 6", title="Text 7", body="Text 8", size=11.0, mono=True,
             title_text="MANIFEST / LOG",
             lines=[
                 "manifest.json (đặt cạnh raw file):",
                 "  dataset      : youtube_trending",
                 "  source       : trending_yt_videos_113_",
                 "                 countries.csv",
                 "  ingested_at  : 2026-10-20T14:30:13+00:00",
                 "  bytes        : 8591418141",
                 "  sha256       : 4310930bd2d1… (64 ký tự)",
                 "  destination  : data/raw/…/run_…/",
                 "  records      : 6094047  (RFC4180)",
                 "  status       : success",
                 "  amendments[] : 1 mục (mọi sửa metadata",
                 "                 đều ghi lại kèm thời điểm)",
                 "",
                 "Log evidence:",
                 "  logs/env_check.txt   → PASS",
                 "  logs/ingest.log      → success + skip",
                 "  logs/transform.log   → Spark 6.074.658 dòng",
             ]),
    ], x=X_RIGHT, w=CARD_W)

    # ---------------- SLIDE 6 – Rerun, blocker, next action ---------------
    s = slides[5]
    place(by_name(s, "Text 15"), left=0.85, top=6.62, width=11.63, height=0.44)
    fill(by_name(s, "Text 15"), ["DONE = evidence + commit + hiểu data flow"],
         size=17, color=BLUE)

    grid2x2(s, [
        dict(card="Shape 3", title="Text 4", body="Text 5", size=10.5, mono=True,
             title_text="NẾU CHẠY INGEST 3 LẦN",
             lines=[
                 "skip (mặc định): hash trùng → SKIP",
                 "  lần 2, 3 → duplicate_skip, raw không đổi",
                 "new-run: hash trùng vẫn tạo run_id mới",
                 "fail: hash trùng → exit 1",
                 "hash khác → luôn tạo run mới (append)",
             ]),
        dict(card="Shape 9", title="Text 10", body="Text 11", size=10.0, mono=True,
             title_text="EVIDENCE LINKS",
             lines=[
                 "Tag: checkpoint-2  (git log -1 checkpoint-2)",
                 "Manifest: data/raw/youtube_trending/",
                 "  …/run_20261020T143013Z/manifest.json",
                 "Logs: logs/env_check.txt",
                 "      logs/ingest.log",
                 "      logs/transform.log",
                 "Reports: docs/Checkpoint2_Report_*.pptx",
                 "         docs/Checkpoint2_Brief_Filled.docx",
             ]),
        dict(card="Shape 6", title="Text 7", body="Text 8", size=10.5,
             title_text="BLOCKER LỚN NHẤT",
             lines=[
                 "Schema nguồn khác đề cương: thiếu category_id,",
                 "description nhiều dòng → xử lý bằng SRC_MAP +",
                 "split_csv.py (1 dòng = 1 record).",
                 "Rủi ro còn lại: nguồn cập nhật hằng ngày.",
                 "Owner: Phúc (transform) · Linh (Parquet/DuckDB)",
                 "Deadline: trước Buổi 7",
             ]),
        dict(card="Shape 12", title="Text 13", body="Text 14", size=11.0,
             title_text="TRƯỚC BUỔI 7",
             lines=[
                 "1) Ingest snapshot mới (dữ liệu cập nhật hằng",
                 "   ngày) để so sánh growth giữa 2 kỳ.",
                 "2) Demo dashboard DuckDB + Streamlit trực tiếp.",
                 "3) Chốt đề cương Đồ án 3 (ML / nâng cao).",
             ]),
    ], top=TOP, bottom=6.48)

    # ---------------- font: thay Aptos (không có trên máy) bằng Calibri ----
    replaced = 0
    for part in [*prs.slides, prs.slide_master, *prs.slide_master.slide_layouts]:
        for el in part._element.iter():
            if el.get("typeface") == "Aptos":
                el.set("typeface", BODY_FONT)
                replaced += 1
    print(f"font: thay {replaced} chỗ Aptos -> {BODY_FONT}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"OK -> {OUT}")
    print(f"   tag={tag}")
    return validate(prs, slides, tag)


# ------------------------------------------------------------------ validate

# khối chữ -> khung trang trí chứa nó
CONTAINERS: dict[int, list[tuple[str, str | None]]] = {
    1: [("Text 2", None), ("Text 3", None), ("Text 4", None), ("Footer 1", None)],
    2: [("Text 4", "Shape 3"), ("Text 6", "Shape 3")],
    3: [("Text 5", "Shape 3"), ("Text 8", "Shape 6"), ("Text 11", "Shape 9"),
        ("Text 14", "Shape 12")],
    4: [("Text 5", "Shape 3"), ("Text 8", "Shape 6"), ("Text 11", "Shape 9"),
        ("Text 14", "Shape 12")],
    5: [("Text 5", "Shape 3"), ("Text 8", "Shape 6")],
    6: [("Text 5", "Shape 3"), ("Text 8", "Shape 6"), ("Text 11", "Shape 9"),
        ("Text 14", "Shape 12"), ("Text 15", None)],
}
NEEDLES = ("6.094.047", "8.591.418.141", "4310930bd2d1", "run_20261020T143013Z",
           "logs/ingest.log", "logs/env_check.txt", "verify_raw_records",
           "duplicate_skip", "6094047", "checkpoint-2")
PLACEHOLDERS = ("_____", "DÁN ", "Chèn ", "TODO", "Ghi rõ", "___________________")


def validate(prs, slides, tag: str = "") -> int:
    problems: list[str] = []
    slide_h = prs.slide_height / EMU_IN
    slide_w = prs.slide_width / EMU_IN

    for idx, slide in enumerate(slides, 1):
        boxes = {sh.name: sh for sh in slide.shapes}

        # --- audit toàn bộ shape có chữ: chữ phải nằm gọn trong chính khung của nó
        for shape in slide.shapes:
            if not shape.has_text_frame or not shape.text_frame.text.strip():
                continue
            runs = [r for p in shape.text_frame.paragraphs for r in p.runs]
            sizes = [r.font.size.pt for r in runs if r.font.size]
            fs = max(sizes) if sizes else 18.0
            mono = any(r.font.name == MONO_FONT for r in runs)
            lines = [p.text for p in shape.text_frame.paragraphs]
            sw = shape.width / EMU_IN
            sh_h = shape.height / EMU_IN
            need = measure_height(lines, sw, fs, mono)
            word_w = longest_word_width(lines, fs, mono)
            if need > sh_h + 0.03:
                problems.append(
                    f"slide {idx} · {shape.name}: chữ cần {need:.2f}in nhưng khung "
                    f"chỉ cao {sh_h:.2f}in (thiếu {need - sh_h:.2f}in)")
            if word_w > sw + 0.02:
                problems.append(
                    f"slide {idx} · {shape.name}: có từ dài {word_w:.2f}in > khung "
                    f"{sw:.2f}in (không wrap được)")

        for text_name, box_name in CONTAINERS.get(idx, []):
            shape = boxes.get(text_name)
            if shape is None or not shape.has_text_frame:
                problems.append(f"slide {idx}: thiếu shape '{text_name}'")
                continue
            raw = shape.text_frame.text
            if not raw.strip():
                problems.append(f"slide {idx} · {text_name}: khung chữ rỗng")
                continue
            for ph in PLACEHOLDERS:
                if ph in raw:
                    problems.append(f"slide {idx} · {text_name}: còn placeholder {ph!r}")

            runs = [r for p in shape.text_frame.paragraphs for r in p.runs]
            sizes = [r.font.size.pt for r in runs if r.font.size]
            fs = max(sizes) if sizes else 18.0
            mono = any(r.font.name == MONO_FONT for r in runs)
            lines = [p.text for p in shape.text_frame.paragraphs]
            need = measure_height(lines, shape.width / EMU_IN, fs, mono)
            top = shape.top / EMU_IN
            left = shape.left / EMU_IN
            width = shape.width / EMU_IN

            if top + need > slide_h - 0.12:
                problems.append(f"slide {idx} · {text_name}: tràn đáy slide "
                                f"({top + need:.2f}in > {slide_h - 0.12:.2f}in)")
            if left < 0.20 or left + width > slide_w - 0.20:
                problems.append(f"slide {idx} · {text_name}: tràn mép ngang slide")
            if box_name:
                box = boxes[box_name]
                b_top = box.top / EMU_IN
                b_bottom = (box.top + box.height) / EMU_IN
                b_left = box.left / EMU_IN
                b_right = (box.left + box.width) / EMU_IN
                if top < b_top - 0.02 or top + need > b_bottom - 0.04:
                    problems.append(
                        f"slide {idx} · {text_name}: tràn khung '{box_name}' "
                        f"(chữ {top:.2f}→{top + need:.2f}in, "
                        f"khung {b_top:.2f}→{b_bottom:.2f}in)")
                if left < b_left - 0.02 or left + width > b_right + 0.02:
                    problems.append(f"slide {idx} · {text_name}: tràn ngang khung "
                                    f"'{box_name}'")

        # các card cùng cột không được chồng lên nhau
        for names in (("Shape 3", "Shape 6", "Shape 9", "Shape 12"),):
            rects = [boxes[n] for n in names if n in boxes]
            for i, a in enumerate(rects):
                for b in rects[i + 1:]:
                    ax0, ax1 = a.left / EMU_IN, (a.left + a.width) / EMU_IN
                    bx0, bx1 = b.left / EMU_IN, (b.left + b.width) / EMU_IN
                    ay0, ay1 = a.top / EMU_IN, (a.top + a.height) / EMU_IN
                    by0, by1 = b.top / EMU_IN, (b.top + b.height) / EMU_IN
                    if ax0 < bx1 - 0.01 and bx0 < ax1 - 0.01 and \
                       ay0 < by1 - 0.01 and by0 < ay1 - 0.01:
                        problems.append(f"slide {idx}: '{a.name}' chồng '{b.name}'")

    # nội dung bắt buộc + font
    full = "\n".join(
        sh.text_frame.text for slide in slides for sh in slide.shapes
        if sh.has_text_frame
    )
    for needle in NEEDLES:
        if needle and needle not in full:
            problems.append(f"thiếu nội dung '{needle}'")
    for slide in slides:
        if "Aptos" in slide._element.xml:
            problems.append("còn font Aptos (máy không cài -> PowerPoint tự thay font)")

    # báo cáo độ lấp đầy của từng card
    print("\nĐộ lấp đầy khung (cao nội dung / cao vùng thân):")
    for name, size, used, area in REPORT:
        ratio = used / area if area else 0
        flag = "  <-- trống nhiều" if ratio < 0.55 else ""
        print(f"  {name:8} size={size:4.1f}  {used:4.2f}/{area:4.2f}in "
              f"= {ratio * 100:3.0f}%{flag}")

    if problems:
        print("\nLAYOUT CÓ VẤN ĐỀ:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nLAYOUT OK: mọi khối chữ nằm trong khung, không tràn slide, "
          "không chồng nhau, đủ nội dung bắt buộc.")
    return 0


if __name__ == "__main__":
    sys.exit(build())
