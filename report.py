"""
report.py
---------
Report export utilities for InsightPilot v2.

Provides:
  - markdown_to_docx()  :  convert the agent's Markdown report + chart images
                           to a well-formed .docx byte stream
  - word_count()        :  count words in a Markdown string
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import config

# python-docx is an optional dependency; degrade gracefully if missing.
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.shared import Inches, Pt, RGBColor
    DOCX_AVAILABLE: bool = True
except ImportError:
    DOCX_AVAILABLE = False


# ---------------------------------------------------------------------------
# Word counter
# ---------------------------------------------------------------------------

def word_count(text: str) -> int:
    """
    Return the approximate word count of *text* (strips Markdown syntax).

    Parameters
    ----------
    text : str

    Returns
    -------
    int
    """
    # Remove fenced code blocks
    clean = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove inline code, headings markers, bold/italic, links
    clean = re.sub(r"[#*_`\[\]()]", " ", clean)
    # Remove URLs
    clean = re.sub(r"https?://\S+", "", clean)
    tokens = clean.split()
    return len(tokens)


# ---------------------------------------------------------------------------
# DOCX builder
# ---------------------------------------------------------------------------

def _set_heading_color(paragraph, rgb: tuple[int, int, int]) -> None:
    """Apply an RGB color to all runs in a heading paragraph."""
    r, g, b = rgb
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor(r, g, b)


def _add_horizontal_rule(doc: "Document") -> None:  # type: ignore[name-defined]
    """Insert a thin horizontal line (paragraph border) into *doc*."""
    p = doc.add_paragraph()
    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "E2E8F0")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def markdown_to_docx(
    report_md: str,
    chart_paths: list[str] | None = None,
) -> bytes:
    """
    Convert a Markdown report string to a .docx byte stream.

    Handles: headings (# / ## / ###), bullet lists (- or *), blank lines,
    bold/italic inline markers, and embeds chart PNG images.

    Parameters
    ----------
    report_md : str
        Markdown report produced by the agent.
    chart_paths : list[str] | None
        Absolute or relative paths to PNG chart files to embed.

    Returns
    -------
    bytes
        The .docx file content, ready for download.
        Returns b"" if python-docx is not installed.
    """
    if not DOCX_AVAILABLE:
        return b""

    doc = Document()

    # ---- Page margins ----
    section = doc.sections[0]
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.2)
    section.right_margin = Inches(1.2)

    # ---- Document title ----
    title_p = doc.add_heading("InsightPilot — Laporan Analisis Data", level=0)
    _set_heading_color(title_p, (10, 124, 101))  # #0A7C65

    # Subtitle / date line
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = subtitle.add_run("Dihasilkan oleh InsightPilot · IBM AI Builders Challenge")
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(100, 116, 139)  # #64748B

    _add_horizontal_rule(doc)

    # ---- Parse and render Markdown lines ----
    for line in report_md.splitlines():
        stripped = line.strip()

        if stripped.startswith("### "):
            p = doc.add_heading(_render_inline(stripped[4:]), level=3)
            _set_heading_color(p, (10, 124, 101))

        elif stripped.startswith("## "):
            p = doc.add_heading(_render_inline(stripped[3:]), level=2)
            _set_heading_color(p, (10, 124, 101))

        elif stripped.startswith("# "):
            p = doc.add_heading(_render_inline(stripped[2:]), level=1)
            _set_heading_color(p, (10, 124, 101))

        elif stripped.startswith("- ") or stripped.startswith("* "):
            p = doc.add_paragraph(style="List Bullet")
            _add_inline_runs(p, stripped[2:])

        elif stripped == "" or stripped == "---":
            doc.add_paragraph("")

        else:
            p = doc.add_paragraph()
            _add_inline_runs(p, stripped)

    # ---- Embed charts ----
    if chart_paths:
        _add_horizontal_rule(doc)
        charts_heading = doc.add_heading("Grafik Analisis", level=2)
        _set_heading_color(charts_heading, (10, 124, 101))

        for path_str in chart_paths:
            path = Path(path_str)
            if path.exists():
                try:
                    doc.add_paragraph(path.stem)
                    doc.add_picture(str(path), width=Inches(5.5))
                    doc.add_paragraph("")  # spacing
                except Exception:
                    doc.add_paragraph(f"[Grafik tidak dapat disematkan: {path.name}]")

    # ---- Footer note ----
    _add_horizontal_rule(doc)
    footer_p = doc.add_paragraph()
    footer_run = footer_p.add_run(
        "Laporan ini dihasilkan secara otomatis oleh InsightPilot menggunakan "
        "Anthropic Claude. Verifikasi angka-angka penting sebelum mengambil keputusan."
    )
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = RGBColor(100, 116, 139)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Inline Markdown renderer helpers (bold, italic, inline code)
# ---------------------------------------------------------------------------

def _render_inline(text: str) -> str:
    """Strip basic inline Markdown (bold, italic, code) for plain text."""
    # Remove **bold**, *italic*, `code`
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text


def _add_inline_runs(paragraph, text: str) -> None:
    """
    Add inline-formatted runs to *paragraph*.

    Supports **bold**, *italic*, and `inline code`.
    """
    # Tokenise: split on **bold**, *italic*, `code`
    pattern = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")
    parts = pattern.split(text)

    for part in parts:
        if not part:
            continue
        run = paragraph.add_run()
        if part.startswith("**") and part.endswith("**"):
            run.text = part[2:-2]
            run.bold = True
        elif part.startswith("*") and part.endswith("*"):
            run.text = part[1:-1]
            run.italic = True
        elif part.startswith("`") and part.endswith("`"):
            run.text = part[1:-1]
            run.font.name = "Consolas"
            run.font.size = Pt(9)
        else:
            run.text = part
