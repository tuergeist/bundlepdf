from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime
import pytz
import re
import html as html_module
from typing import Optional
import json
import os
from bs4 import BeautifulSoup, NavigableString

# Register DejaVu fonts for Unicode support (including German umlauts)
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
DEFAULT_FONT = 'Helvetica'

def register_fonts():
    global DEFAULT_FONT
    try:
        if os.path.exists(f'{FONT_DIR}/DejaVuSans.ttf'):
            pdfmetrics.registerFont(TTFont('DejaVu', f'{FONT_DIR}/DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', f'{FONT_DIR}/DejaVuSans-Bold.ttf'))
            # Use regular as fallback for italic (core package doesn't have oblique)
            pdfmetrics.registerFont(TTFont('DejaVu-Italic', f'{FONT_DIR}/DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVu-BoldItalic', f'{FONT_DIR}/DejaVuSans-Bold.ttf'))
            DEFAULT_FONT = 'DejaVu'
            print(f"Registered DejaVu fonts from {FONT_DIR}")
    except Exception as e:
        print(f"Could not register DejaVu fonts: {e}, using Helvetica")
        DEFAULT_FONT = 'Helvetica'

register_fonts()

app = FastAPI(title="PDF Merger API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_cet_timestamp() -> str:
    cet = pytz.timezone("Europe/Berlin")
    now = datetime.now(cet)
    return now.strftime("%d.%m.%Y %H:%M CET")


def html_to_flowables(html_content: str, styles: dict) -> list:
    """Convert HTML from TipTap editor to ReportLab flowables using BeautifulSoup."""
    flowables = []

    if not html_content or not html_content.strip():
        return flowables

    soup = BeautifulSoup(html_content, 'html.parser')

    def get_alignment(element) -> int:
        """Extract text alignment from element style."""
        style = element.get('style', '')
        if 'text-align: center' in style or 'text-align:center' in style:
            return TA_CENTER
        elif 'text-align: right' in style or 'text-align:right' in style:
            return TA_RIGHT
        return TA_LEFT

    def process_inline(element) -> str:
        """Convert inline elements to ReportLab markup, preserving text."""
        if isinstance(element, NavigableString):
            return str(element)

        result = []
        for child in element.children:
            if isinstance(child, NavigableString):
                result.append(str(child))
            elif child.name == 'strong' or child.name == 'b':
                result.append(f'<b>{process_inline(child)}</b>')
            elif child.name == 'em' or child.name == 'i':
                result.append(f'<i>{process_inline(child)}</i>')
            elif child.name == 'u':
                result.append(f'<u>{process_inline(child)}</u>')
            else:
                # For other tags, just get their text content
                result.append(process_inline(child))

        return ''.join(result).strip()

    def render_list(list_element, level: int = 0) -> list:
        """Recursively render list items with proper indentation."""
        result = []
        is_ordered = list_element.name == 'ol'
        bullet_char = '\u2022'
        item_num = 0

        for li in list_element.find_all('li', recursive=False):
            item_num += 1

            # Get direct text content (before any nested list)
            text_parts = []
            for child in li.children:
                if isinstance(child, NavigableString):
                    text_parts.append(str(child))
                elif child.name in ('ul', 'ol'):
                    break  # Stop at nested list
                else:
                    text_parts.append(process_inline(child))

            text = ''.join(text_parts).strip()

            if text:
                indent = 10 + (level * 10)
                if is_ordered:
                    prefix = f"{item_num}.  "
                else:
                    prefix = bullet_char + '  '

                style = ParagraphStyle(
                    f'list_{level}_{item_num}',
                    parent=styles['Normal'],
                    leftIndent=indent*mm,
                    firstLineIndent=-5*mm,
                )
                result.append(Paragraph(prefix + text, style))
                result.append(Spacer(1, 1*mm))

            # Process nested lists
            for nested_list in li.find_all(['ul', 'ol'], recursive=False):
                result.extend(render_list(nested_list, level + 1))

        return result

    # Process top-level elements
    for element in soup.children:
        if isinstance(element, NavigableString):
            continue

        tag = element.name
        if not tag:
            continue

        if tag == 'h1':
            alignment = get_alignment(element)
            style = ParagraphStyle('h1', parent=styles['Heading1'], alignment=alignment)
            flowables.append(Paragraph(process_inline(element), style))
            flowables.append(Spacer(1, 6*mm))

        elif tag == 'h2':
            alignment = get_alignment(element)
            style = ParagraphStyle('h2', parent=styles['Heading2'], alignment=alignment)
            flowables.append(Paragraph(process_inline(element), style))
            flowables.append(Spacer(1, 4*mm))

        elif tag == 'h3':
            alignment = get_alignment(element)
            style = ParagraphStyle('h3', parent=styles['Heading3'], alignment=alignment)
            flowables.append(Paragraph(process_inline(element), style))
            flowables.append(Spacer(1, 3*mm))

        elif tag == 'p':
            text = process_inline(element)
            if text:
                alignment = get_alignment(element)
                style = ParagraphStyle('p', parent=styles['Normal'], alignment=alignment)
                flowables.append(Paragraph(text, style))
                flowables.append(Spacer(1, 2*mm))

        elif tag in ('ul', 'ol'):
            list_flowables = render_list(element)
            flowables.extend(list_flowables)
            flowables.append(Spacer(1, 2*mm))

    return flowables


def create_front_page(html_content: str, pdf_names: list[str]) -> bytes:
    """Create the front page PDF with user content and document list."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=30*mm,
    )

    styles = getSampleStyleSheet()

    # Override styles with Unicode font
    for style_name in styles.byName:
        styles[style_name].fontName = DEFAULT_FONT

    # Create custom styles with proper fonts
    styles.add(ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=DEFAULT_FONT,
    ))
    styles.add(ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontName=f'{DEFAULT_FONT}-Bold' if DEFAULT_FONT == 'DejaVu' else 'Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontName=f'{DEFAULT_FONT}-Bold' if DEFAULT_FONT == 'DejaVu' else 'Helvetica-Bold',
    ))

    flowables = []

    # Add user content
    flowables.extend(html_to_flowables(html_content, styles))

    # Add attached documents section if there are PDFs
    if pdf_names:
        flowables.append(Spacer(1, 10*mm))
        flowables.append(Paragraph("Attached Documents:", styles['Heading2']))
        flowables.append(Spacer(1, 3*mm))

        for i, name in enumerate(pdf_names, 1):
            flowables.append(Paragraph(f"{i}. {html_module.escape(name)}", styles['Normal']))
            flowables.append(Spacer(1, 1*mm))

    # Add footer with timestamp
    timestamp = get_cet_timestamp()

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColorRGB(0.5, 0.5, 0.5)
        canvas.drawCentredString(A4[0]/2, 15*mm, f"Generated on: {timestamp}")
        canvas.restoreState()

    doc.build(flowables, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer.getvalue()


@app.post("/api/merge")
async def merge_pdfs(
    content: str = Form(default=""),
    file_order: str = Form(default="[]"),
    files: list[UploadFile] = File(default=[]),
):
    """Merge PDFs with a custom front page."""
    try:
        # Parse file order
        order = json.loads(file_order) if file_order else []

        # Create a map of filename to file data
        file_map = {}
        for f in files:
            data = await f.read()
            file_map[f.filename] = data

        # Order files according to user preference
        if order:
            ordered_names = order
        else:
            ordered_names = list(file_map.keys())

        # Create front page
        front_page_bytes = create_front_page(content, ordered_names)

        # Merge all PDFs
        writer = PdfWriter()

        # Add front page
        front_reader = PdfReader(BytesIO(front_page_bytes))
        for page in front_reader.pages:
            writer.add_page(page)

        # Add uploaded PDFs in order
        failed_files = []
        for name in ordered_names:
            if name not in file_map:
                continue
            try:
                reader = PdfReader(BytesIO(file_map[name]))
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as e:
                print(f"Failed to process {name}: {e}")
                failed_files.append(name)

        # Write merged PDF to buffer
        output = BytesIO()
        writer.write(output)
        output.seek(0)

        # Set filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"merged-document-{timestamp}.pdf"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
        }

        if failed_files:
            headers["X-Failed-Files"] = json.dumps(failed_files)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers=headers,
        )

    except Exception as e:
        print(f"Error merging PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    return {"status": "ok"}
