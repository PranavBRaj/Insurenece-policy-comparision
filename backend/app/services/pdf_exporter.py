"""
pdf_exporter.py
===============
Generates a formatted, multi-section PDF comparison report from a stored
comparison_result dict using ReportLab only.

Returns raw PDF bytes suitable for a FastAPI streaming/binary response.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_NAVY       = colors.HexColor("#1e3a5f")
_BLUE       = colors.HexColor("#2d6a9f")
_ROW_ALT    = colors.HexColor("#f0f4f8")
_ROW_WHITE  = colors.white
_LIGHT_BLUE = colors.HexColor("#dce8f5")
_BORDER     = colors.HexColor("#aac4de")

# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _na(value: Any) -> str:
    """Return the string representation of *value*, or 'N/A' for falsy values."""
    if value is None or value == "" or value == []:
        return "N/A"
    return str(value)


def _wrap(text: Any, max_chars: int = 60) -> str:
    """Truncate *text* for table cells and replace None with 'N/A'."""
    s = _na(text)
    if len(s) > max_chars:
        return s[:max_chars - 1] + "…"
    return s


def _para(text: Any, style: ParagraphStyle) -> Paragraph:
    """Create a Paragraph, safely HTML-escaping ampersands and angle brackets."""
    safe = _na(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


# ---------------------------------------------------------------------------
# Style registry
# ---------------------------------------------------------------------------

def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    styles: dict[str, ParagraphStyle] = {}

    styles["report_title"] = ParagraphStyle(
        "report_title",
        parent=base["Title"],
        fontSize=20,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    styles["report_sub"] = ParagraphStyle(
        "report_sub",
        parent=base["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#cce0f5"),
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    styles["section_heading"] = ParagraphStyle(
        "section_heading",
        parent=base["Heading2"],
        fontSize=13,
        textColor=_BLUE,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=4,
        borderPad=2,
    )
    styles["sub_heading"] = ParagraphStyle(
        "sub_heading",
        parent=base["Heading3"],
        fontSize=10,
        textColor=_NAVY,
        fontName="Helvetica-Bold",
        spaceBefore=6,
        spaceAfter=3,
    )
    styles["body"] = ParagraphStyle(
        "body",
        parent=base["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#1a1a2e"),
        leading=13,
    )
    styles["bullet"] = ParagraphStyle(
        "bullet",
        parent=styles["body"],
        leftIndent=12,
        bulletIndent=2,
        spaceAfter=2,
    )
    styles["cell"] = ParagraphStyle(
        "cell",
        parent=styles["body"],
        fontSize=8,
        leading=11,
    )
    styles["cell_hdr"] = ParagraphStyle(
        "cell_hdr",
        parent=styles["cell"],
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    styles["cell_label"] = ParagraphStyle(
        "cell_label",
        parent=styles["cell"],
        fontName="Helvetica-Bold",
    )
    styles["stat_value"] = ParagraphStyle(
        "stat_value",
        parent=base["Normal"],
        fontSize=18,
        fontName="Helvetica-Bold",
        textColor=_NAVY,
        alignment=TA_CENTER,
        spaceAfter=1,
    )
    styles["stat_label"] = ParagraphStyle(
        "stat_label",
        parent=base["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#5a7a9a"),
        alignment=TA_CENTER,
    )
    styles["footer"] = ParagraphStyle(
        "footer",
        parent=base["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#8899aa"),
        alignment=TA_CENTER,
    )
    styles["policy_label"] = ParagraphStyle(
        "policy_label",
        parent=base["Normal"],
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=_NAVY,
        alignment=TA_CENTER,
    )

    return styles


# ---------------------------------------------------------------------------
# Table style helpers
# ---------------------------------------------------------------------------

_BASE_TABLE_STYLE = TableStyle([
    ("BACKGROUND",  (0, 0), (-1, 0), _NAVY),
    ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
    ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",    (0, 0), (-1, 0), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_ROW_WHITE, _ROW_ALT]),
    ("FONTSIZE",    (0, 1), (-1, -1), 8),
    ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING",  (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING",   (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ("GRID",        (0, 0), (-1, -1), 0.4, _BORDER),
    ("WORDWRAP",    (0, 0), (-1, -1), "LTR"),
])


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header_block(
    story: list,
    styles: dict,
    p1name: str,
    p2name: str,
    comparison_id: int,
    created_at: datetime,
) -> None:
    """Append the report header with title, meta, and policy names."""
    usable_w = PAGE_W - 2 * MARGIN

    header_table = Table(
        [[
            Paragraph("Insurance Policy Comparison Report", styles["report_title"]),
        ]],
        colWidths=[usable_w],
        rowHeights=[None],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), _NAVY),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",(0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(header_table)

    meta_table = Table(
        [[
            Paragraph(f"Comparison ID: #{comparison_id}", styles["report_sub"]),
            Paragraph(
                f"Generated: {created_at.strftime('%B %d, %Y at %H:%M UTC')}",
                styles["report_sub"],
            ),
        ]],
        colWidths=[usable_w / 2, usable_w / 2],
    )
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, -1), _NAVY),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",     (0, 0), (-1, -1), 0),
        ("LEFTPADDING",    (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))

    policy_table = Table(
        [[
            _para(p1name, styles["policy_label"]),
            _para("VS", styles["policy_label"]),
            _para(p2name, styles["policy_label"]),
        ]],
        colWidths=[usable_w * 0.45, usable_w * 0.10, usable_w * 0.45],
    )
    policy_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, 0), _LIGHT_BLUE),
        ("BACKGROUND",  (1, 0), (1, 0), _NAVY),
        ("BACKGROUND",  (2, 0), (2, 0), _LIGHT_BLUE),
        ("TEXTCOLOR",   (1, 0), (1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica-Bold"),
        ("GRID",        (0, 0), (-1, -1), 0.4, _BORDER),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 6),
    ]))
    story.append(policy_table)
    story.append(Spacer(1, 6 * mm))


def _summary_section(
    story: list,
    styles: dict,
    summary: dict,
    p1name: str,
    p2name: str,
) -> None:
    """Append the Summary Statistics section."""
    story.append(Paragraph("Summary Statistics", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE, spaceAfter=4))

    usable_w = PAGE_W - 2 * MARGIN
    col_w = usable_w / 3

    stat_rows = [
        [
            _stat_cell(summary.get("total_coverage_items_policy1"),
                       f"{p1name}\nCoverage Items", styles),
            _stat_cell(summary.get("total_coverage_items_policy2"),
                       f"{p2name}\nCoverage Items", styles),
            _stat_cell(summary.get("shared_coverage_items"),
                       "Shared\nCoverage Items", styles),
        ],
        [
            _stat_cell(summary.get("total_exclusion_items_policy1"),
                       f"{p1name}\nExclusion Items", styles),
            _stat_cell(summary.get("total_exclusion_items_policy2"),
                       f"{p2name}\nExclusion Items", styles),
            _stat_cell(summary.get("shared_exclusion_items"),
                       "Shared\nExclusion Items", styles),
        ],
    ]

    for row in stat_rows:
        t = Table([row], colWidths=[col_w] * 3)
        t.setStyle(TableStyle([
            ("BOX",         (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID",   (0, 0), (-1, -1), 0.5, _BORDER),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0,0), (-1, -1), 6),
            ("BACKGROUND",  (0, 0), (-1, -1), _ROW_ALT),
        ]))
        story.append(t)
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 4 * mm))


def _stat_cell(value: Any, label: str, styles: dict) -> Table:
    """Return a small stat card (value + label) as a Table."""
    inner = Table(
        [
            [Paragraph(_na(value), styles["stat_value"])],
            [Paragraph(label, styles["stat_label"])],
        ],
        colWidths=[(PAGE_W - 2 * MARGIN) / 3 - 6],
    )
    inner.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return inner


def _advantages_section(
    story: list,
    styles: dict,
    summary: dict,
    p1name: str,
    p2name: str,
) -> None:
    """Append the Advantages section with two side-by-side bullet lists."""
    story.append(Paragraph("Key Advantages", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE, spaceAfter=6))

    adv1: list = summary.get("policy1_advantages") or []
    adv2: list = summary.get("policy2_advantages") or []

    usable_w = PAGE_W - 2 * MARGIN
    col_w = (usable_w - 6) / 2

    def _bullet_list(items: list, name: str) -> list:
        rows = [[Paragraph(name, styles["sub_heading"])]]
        if not items:
            rows.append([_para("No specific advantages noted.", styles["body"])])
        else:
            for item in items:
                rows.append([
                    _para(f"• {item}", styles["bullet"])
                ])
        return rows

    left_rows  = _bullet_list(adv1, f"{p1name} Advantages")
    right_rows = _bullet_list(adv2, f"{p2name} Advantages")

    max_rows = max(len(left_rows), len(right_rows))
    combined_rows = []
    empty_para = _para("", styles["body"])
    for i in range(max_rows):
        l_cell = left_rows[i][0]  if i < len(left_rows)  else empty_para
        r_cell = right_rows[i][0] if i < len(right_rows) else empty_para
        combined_rows.append([l_cell, r_cell])

    t = Table(combined_rows, colWidths=[col_w, col_w])
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0,0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",(0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_ROW_WHITE, _ROW_ALT]),
        ("BOX",         (0, 0), (-1, -1), 0.4, _BORDER),
        ("LINEAFTER",   (0, 0), (0, -1), 0.4, _BORDER),
        ("SPAN",        (0, 0), (0, 0)),
        ("SPAN",        (1, 0), (1, 0)),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))


def _premium_section(
    story: list,
    styles: dict,
    premiums: dict,
    p1name: str,
    p2name: str,
) -> None:
    """Append the Premium Comparison table."""
    story.append(Paragraph("Premium Comparison", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE, spaceAfter=4))

    p1 = premiums.get("policy1") or {}
    p2 = premiums.get("policy2") or {}

    fields = [
        ("Annual Premium",       "annual_premium"),
        ("Monthly Premium",      "monthly_premium"),
        ("Deductible",           "deductible"),
        ("Copay",                "copay"),
        ("Coinsurance",          "coinsurance"),
        ("Out-of-Pocket Maximum","out_of_pocket_max"),
    ]

    usable_w = PAGE_W - 2 * MARGIN
    col_widths = [usable_w * 0.30, usable_w * 0.35, usable_w * 0.35]

    header = [
        _para("Field",    styles["cell_hdr"]),
        _para(p1name,     styles["cell_hdr"]),
        _para(p2name,     styles["cell_hdr"]),
    ]
    data_rows = [header]
    for label, key in fields:
        data_rows.append([
            _para(label,          styles["cell_label"]),
            _para(p1.get(key),    styles["cell"]),
            _para(p2.get(key),    styles["cell"]),
        ])

    diffs: list = premiums.get("differences") or []
    if diffs:
        data_rows.append([
            _para("Key Differences", styles["cell_label"]),
            _para("; ".join(diffs),  styles["cell"]),
            _para("",                styles["cell"]),
        ])

    t = Table(data_rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(_BASE_TABLE_STYLE)
    if diffs:
        last = len(data_rows) - 1
        t.setStyle(TableStyle([
            ("SPAN",       (1, last), (2, last)),
            ("BACKGROUND", (0, last), (-1, last), colors.HexColor("#fff8e6")),
        ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))


def _section_table(
    story: list,
    styles: dict,
    heading: str,
    common_items: list,
    only_p1: list,
    only_p2: list,
    p1name: str,
    p2name: str,
) -> None:
    """Append a coverage-or-exclusions section with shared table + unique lists."""
    story.append(Paragraph(heading, styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE, spaceAfter=4))

    usable_w = PAGE_W - 2 * MARGIN

    if common_items:
        story.append(Paragraph(f"Shared {heading}", styles["sub_heading"]))
        col_widths = [
            usable_w * 0.22,
            usable_w * 0.28,
            usable_w * 0.28,
            usable_w * 0.11,
            usable_w * 0.11,
        ]
        header = [
            _para("Topic",          styles["cell_hdr"]),
            _para(f"{p1name} Details", styles["cell_hdr"]),
            _para(f"{p2name} Details", styles["cell_hdr"]),
            _para("P1 Limit",      styles["cell_hdr"]),
            _para("P2 Limit",      styles["cell_hdr"]),
        ]
        rows = [header]
        for item in common_items:
            rows.append([
                _para(item.get("item"),               styles["cell"]),
                _para(item.get("policy1_details"),     styles["cell"]),
                _para(item.get("policy2_details"),     styles["cell"]),
                _para(item.get("policy1_amount"),      styles["cell"]),
                _para(item.get("policy2_amount"),      styles["cell"]),
            ])
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(_BASE_TABLE_STYLE)
        story.append(t)
        story.append(Spacer(1, 3 * mm))

    if only_p1:
        story.append(Paragraph(f"{heading} Only in {p1name}", styles["sub_heading"]))
        for item in only_p1:
            text = item.get("text", "")
            amount = item.get("amount") or item.get("limit")
            line = f"• {text}"
            if amount:
                line += f"  [{amount}]"
            story.append(_para(line, styles["bullet"]))
        story.append(Spacer(1, 3 * mm))

    if only_p2:
        story.append(Paragraph(f"{heading} Only in {p2name}", styles["sub_heading"]))
        for item in only_p2:
            text = item.get("text", "")
            amount = item.get("amount") or item.get("limit")
            line = f"• {text}"
            if amount:
                line += f"  [{amount}]"
            story.append(_para(line, styles["bullet"]))
        story.append(Spacer(1, 3 * mm))

    if not common_items and not only_p1 and not only_p2:
        story.append(_para("No items found for this section.", styles["body"]))
        story.append(Spacer(1, 3 * mm))


# ---------------------------------------------------------------------------
# Footer / header callback
# ---------------------------------------------------------------------------

def _make_footer_cb(styles: dict):
    """Return a page-template onPage callback that draws the footer."""
    def _draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#8899aa"))
        canvas.drawCentredString(
            PAGE_W / 2,
            12 * mm,
            f"Page {doc.page}  •  Generated by Insurance Policy Comparator",
        )
        canvas.restoreState()
    return _draw_footer


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_comparison_pdf(
    comparison_result: dict,
    comparison_id: int,
    created_at: datetime,
) -> bytes:
    """Generate a formatted PDF comparison report and return it as raw bytes.

    Builds a multi-section ReportLab document covering: header metadata,
    summary statistics, advantages, premiums, coverage, and exclusions.
    Each page carries a footer with the page number.

    Raises ValueError if an unexpected error prevents PDF generation.
    """
    logger.info("Starting PDF generation for comparison #%d", comparison_id)

    try:
        styles = _build_styles()

        p1name: str = comparison_result.get("policy1_filename") or "Policy 1"
        p2name: str = comparison_result.get("policy2_filename") or "Policy 2"
        coverage   = comparison_result.get("coverage")   or {}
        exclusions = comparison_result.get("exclusions") or {}
        premiums   = comparison_result.get("premiums")   or {}
        summary    = comparison_result.get("summary")    or {}

        buf = io.BytesIO()
        footer_cb = _make_footer_cb(styles)

        doc = BaseDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=20 * mm,
            title=f"Policy Comparison Report #{comparison_id}",
            author="Insurance Policy Comparator",
        )

        frame = Frame(
            MARGIN, 20 * mm,
            PAGE_W - 2 * MARGIN, PAGE_H - MARGIN - 20 * mm,
            id="main",
        )
        template = PageTemplate(id="main", frames=[frame], onPage=footer_cb)
        doc.addPageTemplates([template])

        story: list = []

        _header_block(story, styles, p1name, p2name, comparison_id, created_at)
        _summary_section(story, styles, summary, p1name, p2name)
        _advantages_section(story, styles, summary, p1name, p2name)
        story.append(PageBreak())

        _premium_section(story, styles, premiums, p1name, p2name)
        story.append(PageBreak())

        _section_table(
            story, styles,
            "Coverage",
            coverage.get("common", []),
            coverage.get("only_in_policy1", []),
            coverage.get("only_in_policy2", []),
            p1name, p2name,
        )
        story.append(PageBreak())

        _section_table(
            story, styles,
            "Exclusions",
            exclusions.get("common", []),
            exclusions.get("only_in_policy1", []),
            exclusions.get("only_in_policy2", []),
            p1name, p2name,
        )

        doc.build(story)

        pdf_bytes = buf.getvalue()
        logger.info(
            "PDF generation complete for comparison #%d — %d bytes",
            comparison_id, len(pdf_bytes),
        )
        return pdf_bytes

    except Exception as exc:
        raise ValueError(
            f"Failed to generate PDF for comparison #{comparison_id}: {exc}"
        ) from exc
