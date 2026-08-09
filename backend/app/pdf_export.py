from __future__ import annotations

import html
from io import BytesIO
from pathlib import Path
from typing import Any

from .config import settings
from .utils import format_elapsed, image_data_url_to_media, list_to_lines, timestamp
from .vmd_core import criteria_evaluation_map, criteria_for_zone, record_zone

try:
    from reportlab.lib import colors as pdf_colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image as ReportLabImage
    from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except Exception:  # pragma: no cover - PDF export reports a dependency error when unavailable.
    REPORTLAB_AVAILABLE = False


PDF_FONT_REGULAR = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"


def setup_pdf_fonts() -> None:
    global PDF_FONT_REGULAR, PDF_FONT_BOLD
    if not REPORTLAB_AVAILABLE:
        return
    regular_path = Path("C:/Windows/Fonts/malgun.ttf")
    bold_path = Path("C:/Windows/Fonts/malgunbd.ttf")
    if not regular_path.exists() or not bold_path.exists():
        return
    if "VmdMalgun" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("VmdMalgun", str(regular_path)))
    if "VmdMalgunBold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("VmdMalgunBold", str(bold_path)))
    PDF_FONT_REGULAR = "VmdMalgun"
    PDF_FONT_BOLD = "VmdMalgunBold"


def pdf_markup(value: Any, fallback: str = "-") -> str:
    text = list_to_lines(value).strip() if value is not None else ""
    return html.escape(text or fallback).replace("\n", "<br/>")


def pdf_image_for_record(record: dict[str, Any], max_width: float = 220, max_height: float = 150) -> Any:
    media = image_data_url_to_media(record.get("image_data_url", ""))
    if media is None:
        return Paragraph(
            "대표 이미지가 없습니다.",
            ParagraphStyle("missing-image", fontName=PDF_FONT_REGULAR, fontSize=9, textColor=pdf_colors.HexColor("#6F6A61")),
        )
    stream = BytesIO(media["data"])
    width, height = ImageReader(stream).getSize()
    scale = min(max_width / max(1, width), max_height / max(1, height), 1)
    image = ReportLabImage(stream, width=max(1, width * scale), height=max(1, height * scale))
    image.hAlign = "CENTER"
    return image


def draw_pdf_footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFillColor(pdf_colors.HexColor("#F7F5F0"))
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(pdf_colors.HexColor("#B79B61"))
    canvas.rect(doc.leftMargin, A4[1] - 11 * mm, A4[0] - doc.leftMargin - doc.rightMargin, 1.2, fill=1, stroke=0)
    canvas.setStrokeColor(pdf_colors.HexColor("#DED8CE"))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 18 * mm, A4[0] - doc.rightMargin, 18 * mm)
    canvas.setFont(PDF_FONT_REGULAR, 7.5)
    canvas.setFillColor(pdf_colors.HexColor("#6F6A61"))
    canvas.drawString(doc.leftMargin, 11 * mm, "AX R&D VMD - 분석 결과 보고서")
    canvas.drawRightString(A4[0] - doc.rightMargin, 11 * mm, f"{doc.page}")
    canvas.restoreState()


def save_pdf(records: list[dict[str, Any]], prefix: str = "vmd_results") -> str:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF 저장을 위해 reportlab 패키지가 필요합니다. requirements.txt를 설치한 뒤 다시 시도해 주세요.")
    settings.ensure_dirs()
    setup_pdf_fonts()
    path = settings.pdf_dir / f"{prefix}_{timestamp()}.pdf"
    styles = getSampleStyleSheet()

    eyebrow_style = ParagraphStyle("pdf-eyebrow", parent=styles["Normal"], fontName=PDF_FONT_BOLD, fontSize=7.5, leading=10, textColor=pdf_colors.HexColor("#B79B61"), spaceAfter=5)
    title_style = ParagraphStyle("pdf-title", parent=styles["Title"], fontName=PDF_FONT_BOLD, fontSize=20, leading=26, textColor=pdf_colors.HexColor("#111111"), alignment=TA_LEFT, spaceAfter=6)
    subtitle_style = ParagraphStyle("pdf-subtitle", parent=styles["Normal"], fontName=PDF_FONT_REGULAR, fontSize=9, leading=13, textColor=pdf_colors.HexColor("#6F6A61"), spaceAfter=12)
    section_style = ParagraphStyle("pdf-section", parent=styles["Heading2"], fontName=PDF_FONT_BOLD, fontSize=12, leading=16, textColor=pdf_colors.HexColor("#111111"), spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle("pdf-body", parent=styles["BodyText"], fontName=PDF_FONT_REGULAR, fontSize=8.8, leading=13, textColor=pdf_colors.HexColor("#3D3932"))
    small_style = ParagraphStyle("pdf-small", parent=body_style, fontSize=7.6, leading=10.5)
    label_style = ParagraphStyle("pdf-label", parent=body_style, fontName=PDF_FONT_BOLD, fontSize=7.8, leading=10, textColor=pdf_colors.HexColor("#6F6A61"))
    issue_header_dark_style = ParagraphStyle("pdf-issue-header-dark", parent=section_style, textColor=pdf_colors.white, spaceBefore=0, spaceAfter=0)
    issue_header_gold_style = ParagraphStyle("pdf-issue-header-gold", parent=section_style, textColor=pdf_colors.HexColor("#111111"), spaceBefore=0, spaceAfter=0)
    table_header_style = ParagraphStyle("pdf-table-header", parent=body_style, fontName=PDF_FONT_BOLD, fontSize=7.5, leading=9.5, textColor=pdf_colors.white, alignment=TA_CENTER)
    table_cell_style = ParagraphStyle("pdf-table-cell", parent=body_style, fontSize=7.3, leading=9.5)
    score_style = ParagraphStyle("pdf-score", parent=table_cell_style, fontName=PDF_FONT_BOLD, fontSize=12, leading=14, textColor=pdf_colors.HexColor("#111111"), alignment=TA_CENTER)

    story: list[Any] = []
    for record_index, record in enumerate(records):
        result = record.get("result", {})
        zone = record_zone(record)
        photo = result.get("photo_quality", {})
        mannequin = result.get("mannequin", {})
        title = f"VMD 이미지 분석 리포트 - {zone}"
        image_names = record.get("image_names", "분석 이미지")
        detected_zone = result.get("ai_detected_zone", "UNKNOWN")
        confidence = round(float(result.get("zone_confidence", 0) or 0) * 100)

        story.append(Paragraph("AX R&D VISUAL MERCHANDISING", eyebrow_style))
        story.append(Paragraph(html.escape(title), title_style))
        story.append(Paragraph(f"분석 이미지: {html.escape(str(image_names))}<br/>분석 시간: {html.escape(format_elapsed(record.get('elapsed_seconds')))}", subtitle_style))

        meta_data = [
            [Paragraph("사용자 지정 구역", label_style), Paragraph(pdf_markup(result.get("user_selected_zone", zone)), body_style), Paragraph("AI 감지 구역", label_style), Paragraph(pdf_markup(detected_zone), body_style)],
            [Paragraph("구역 신뢰도", label_style), Paragraph(f"{confidence}%", body_style), Paragraph("총점 / 등급", label_style), Paragraph(f"{pdf_markup(result.get('total_score'))} / {pdf_markup(result.get('grade'))}", body_style)],
            [Paragraph("사진 품질", label_style), Paragraph(f"{pdf_markup(photo.get('score'))}점 - {pdf_markup(photo.get('comment'))}", small_style), Paragraph("마네킹", label_style), Paragraph(f"{('있음' if mannequin.get('exists') else '없음')} - {pdf_markup(mannequin.get('type'))}", small_style)],
        ]
        meta_table = Table(meta_data, colWidths=[80, 170, 70, 185], hAlign="LEFT")
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), pdf_colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.6, pdf_colors.HexColor("#DED8CE")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, pdf_colors.HexColor("#DED8CE")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 10))

        summary_data = [
            [
                [Paragraph("영역별 종합 평가", section_style), Paragraph(pdf_markup(result.get("zone_evaluation_summary", result.get("final_summary"))), body_style)],
                [Paragraph("우선 개선 방향", section_style), Paragraph(pdf_markup(result.get("priority_action_summary", result.get("final_summary"))), body_style)],
            ],
            [pdf_image_for_record(record), Paragraph(f"<b>최종 요약</b><br/>{pdf_markup(result.get('overall_improvement_summary', result.get('final_summary')))}", body_style)],
        ]
        summary_table = Table(summary_data, colWidths=[252, 253], hAlign="LEFT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.6, pdf_colors.HexColor("#DED8CE")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, pdf_colors.HexColor("#DED8CE")),
                    ("BACKGROUND", (0, 0), (-1, 0), pdf_colors.HexColor("#EADFCA")),
                    ("BACKGROUND", (0, 1), (-1, 1), pdf_colors.white),
                    ("LINEABOVE", (0, 0), (-1, 0), 1.2, pdf_colors.HexColor("#B79B61")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(summary_table)
        story.append(Paragraph("항목별 평가", section_style))

        by_criterion = criteria_evaluation_map(result)
        criteria_rows = [
            [
                Paragraph("평가항목", table_header_style),
                Paragraph("점수", table_header_style),
                Paragraph("근거", table_header_style),
                Paragraph("문제점", table_header_style),
                Paragraph("개선안", table_header_style),
            ]
        ]
        for criterion in criteria_for_zone(zone):
            item = by_criterion.get(criterion, {})
            criteria_rows.append(
                [
                    Paragraph(pdf_markup(criterion), table_cell_style),
                    Paragraph(pdf_markup(item.get("score")), score_style),
                    Paragraph(pdf_markup(item.get("evidence")), table_cell_style),
                    Paragraph(pdf_markup(item.get("issue")), table_cell_style),
                    Paragraph(pdf_markup(item.get("suggestion")), table_cell_style),
                ]
            )
        criteria_table = LongTable(criteria_rows, colWidths=[105, 38, 120, 120, 120], repeatRows=1, hAlign="LEFT")
        criteria_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), pdf_colors.HexColor("#050505")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [pdf_colors.white, pdf_colors.HexColor("#F7F5F0")]),
                    ("LINEBELOW", (0, 0), (-1, 0), 1.2, pdf_colors.HexColor("#B79B61")),
                    ("BOX", (0, 0), (-1, -1), 0.6, pdf_colors.HexColor("#DED8CE")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, pdf_colors.HexColor("#DED8CE")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(criteria_table)
        story.append(Spacer(1, 8))

        issue_data = [
            [Paragraph("감지된 문제점", issue_header_dark_style), Paragraph("개선 방향", issue_header_gold_style)],
            [
                Paragraph(pdf_markup(result.get("detected_issues", result.get("critical_issues", []))), body_style),
                Paragraph(pdf_markup(result.get("improvement_actions", result.get("improvement_suggestions", []))), body_style),
            ],
        ]
        issue_table = Table(issue_data, colWidths=[252, 253], hAlign="LEFT")
        issue_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), pdf_colors.HexColor("#050505")),
                    ("BACKGROUND", (1, 0), (1, 0), pdf_colors.HexColor("#EADFCA")),
                    ("LINEABOVE", (0, 0), (-1, 0), 1.2, pdf_colors.HexColor("#B79B61")),
                    ("BOX", (0, 0), (-1, -1), 0.6, pdf_colors.HexColor("#DED8CE")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, pdf_colors.HexColor("#DED8CE")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(issue_table)
        if record_index < len(records) - 1:
            story.append(PageBreak())

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=25 * mm,
        title="VMD 이미지 분석 결과",
        author="AX R&D VMD",
    )
    document.build(story, onFirstPage=draw_pdf_footer, onLaterPages=draw_pdf_footer)
    return str(path.relative_to(settings.project_root))
