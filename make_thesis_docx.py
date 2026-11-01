# -*- coding: utf-8 -*-
"""Sinh BAO_CAO_KHOA_LUAN.docx từ BAO_CAO_KHOA_LUAN.md.

Định dạng chuẩn khóa luận: Times New Roman 13, giãn dòng 1.5, lề trái 3cm /
phải 2cm / trên-dưới 2.5cm, căn đều hai bên, thụt đầu dòng 1cm, số trang ở
footer. Markdown hỗ trợ: tiêu đề #/##/###, bảng pipe, code fence, bullet,
đánh số, in đậm **...**.
"""
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
MD = ROOT / "BAO_CAO_KHOA_LUAN.md"
OUT = ROOT / "BAO_CAO_KHOA_LUAN.docx"

TNR = "Times New Roman"
BLACK = RGBColor(0, 0, 0)

doc = Document()

# ---- Thiết lập trang + style nền -------------------------------------------
section = doc.sections[0]
section.page_width, section.page_height = Cm(21.0), Cm(29.7)  # A4
section.left_margin, section.right_margin = Cm(3.0), Cm(2.0)
section.top_margin, section.bottom_margin = Cm(2.5), Cm(2.5)

normal = doc.styles["Normal"]
normal.font.name = TNR
normal.font.size = Pt(13)
normal.font.color.rgb = BLACK
normal.paragraph_format.line_spacing = 1.5
normal.paragraph_format.space_after = Pt(6)
# Đảm bảo font tiếng Việt (rFonts east-asian/cs)
rpr = normal.element.get_or_add_rPr()
rfonts = rpr.find(qn("w:rFonts"))
if rfonts is None:
    rfonts = OxmlElement("w:rFonts")
    rpr.append(rfonts)
for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
    rfonts.set(qn(attr), TNR)


def add_page_number_footer():
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for el, attrs, text in (
        ("w:fldChar", {"w:fldCharType": "begin"}, None),
        ("w:instrText", {"xml:space": "preserve"}, " PAGE "),
        ("w:fldChar", {"w:fldCharType": "end"}, None),
    ):
        element = OxmlElement(el)
        for k, v in attrs.items():
            element.set(qn(k), v)
        if text:
            element.text = text
        run._r.append(element)
    run.font.name = TNR
    run.font.size = Pt(11)


add_page_number_footer()


def style_run(run, size=13, bold=False, italic=False, mono=False, color=BLACK):
    run.font.name = "Consolas" if mono else TNR
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = color
    if not mono:
        rpr = run._r.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(attr), TNR)
    return run


def add_paragraph(text, size=13, bold=False, italic=False, mono=False,
                  align=None, indent=True, line_spacing=1.5):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = line_spacing
    if align is not None:
        p.alignment = align
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if indent and not mono:
        p.paragraph_format.first_line_indent = Cm(1.0)
    # Tách **đậm** thành run
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            style_run(p.add_run(part[2:-2]), size=size, bold=True, mono=mono)
        elif part:
            style_run(p.add_run(part), size=size, bold=bold, italic=italic, mono=mono)
    return p


def add_heading_md(text, level):
    text = text.strip().lstrip("#").strip()
    sizes = {1: 16, 2: 14, 3: 13}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    if level == 1:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_run(p.add_run(text), size=sizes.get(level, 13), bold=True)
    return p


def add_table_md(header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, cell in enumerate(t.rows[0].cells):
        cell.text = ""
        style_run(cell.paragraphs[0].add_run(header[i].strip()), size=11, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i, cell in enumerate(row):
            if i >= len(cells):
                break
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            parts = re.split(r"(\*\*[^*]+\*\*)", cell.strip())
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    style_run(p.add_run(part[2:-2]), size=11, bold=True)
                elif part:
                    style_run(p.add_run(part), size=11)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_code_block(lines):
    for line in lines:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.space_after = Pt(0)
        style_run(p.add_run(line if line else " "), size=10, mono=True,
                  color=RGBColor(0x20, 0x20, 0x20))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# ---- Parse markdown ---------------------------------------------------------
lines = MD.read_text(encoding="utf-8").splitlines()
i = 0
in_cover = False
cover_done = False
while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    # Code fence
    if stripped.startswith("```"):
        block = []
        i += 1
        while i < len(lines) and not lines[i].strip().startswith("```"):
            block.append(lines[i])
            i += 1
        add_code_block(block)
        i += 1
        continue

    # Bảng markdown
    if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
        header = [c for c in stripped.strip("|").split("|")]
        i += 2
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append([c for c in lines[i].strip().strip("|").split("|")])
            i += 1
        add_table_md(header, rows)
        continue

    # Tiêu đề
    m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
    if m:
        level = len(m.group(1))
        text_h = m.group(2).strip()
        if level == 1:
            # Trang bìa: căn giữa, không thụt lề
            add_heading_md(text_h, 1)
        else:
            add_heading_md(text_h, min(level, 3))
        i += 1
        continue

    # Ngăn cách ngang "---" -> bỏ qua
    if re.match(r"^-{3,}$", stripped):
        i += 1
        continue

    # Bullet
    if re.match(r"^-\s+", stripped):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.line_spacing = 1.5
        parts = re.split(r"(\*\*[^*]+\*\*)", re.sub(r"^-\s+", "", stripped))
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                style_run(p.add_run(part[2:-2]), bold=True)
            elif part:
                style_run(p.add_run(part))
        i += 1
        continue

    # Danh sách đánh số "1. ..."
    m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
    if m and len(m.group(2)) > 2:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.left_indent = Cm(0.75)
        style_run(p.add_run(f"{m.group(1)}. "), bold=True)
        parts = re.split(r"(\*\*[^*]+\*\*)", m.group(2))
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                style_run(p.add_run(part[2:-2]), bold=True)
            elif part:
                style_run(p.add_run(part))
        i += 1
        continue

    # Dòng trống
    if not stripped:
        i += 1
        continue

    # Đoạn thường (căn giữa cho khối bìa: trước "## MỤC LỤC")
    if not cover_done and "MỤC LỤC" not in stripped.upper() and "MỤC LUC" not in stripped.upper():
        add_paragraph(stripped, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
        i += 1
        continue
    if not cover_done:
        cover_done = True
        add_paragraph(stripped, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
        i += 1
        continue
    add_paragraph(stripped)
    i += 1

doc.save(str(OUT))
print("Saved:", OUT)
