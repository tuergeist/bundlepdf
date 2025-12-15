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
    """Convert HTML from TipTap editor to ReportLab flowables."""
    flowables = []

    if not html_content or not html_content.strip():
        return flowables

    # Simple HTML tag patterns
    block_pattern = re.compile(r'<(h[1-3]|p|ul|ol|li)[^>]*>(.*?)</\1>', re.DOTALL | re.IGNORECASE)

    # Process block elements
    content = html_content

    # Handle headings and paragraphs
    def process_inline(text: str) -> str:
        """Convert inline HTML tags to ReportLab markup."""
        # Remove nested tags but keep text
        text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'<b>\1</b>', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<em[^>]*>(.*?)</em>', r'<i>\1</i>', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<u[^>]*>(.*?)</u>', r'<u>\1</u>', text, flags=re.IGNORECASE | re.DOTALL)
        # Remove any other HTML tags
        text = re.sub(r'<(?!/?[biu]>)[^>]+>', '', text)
        return text.strip()

    def get_alignment(tag_content: str) -> int:
        if 'text-align: center' in tag_content or 'text-align:center' in tag_content:
            return TA_CENTER
        elif 'text-align: right' in tag_content or 'text-align:right' in tag_content:
            return TA_RIGHT
        return TA_LEFT

    # Find all block elements
    pos = 0
    while pos < len(content):
        # Try to match block elements
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content[pos:], re.DOTALL | re.IGNORECASE)
        h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', content[pos:], re.DOTALL | re.IGNORECASE)
        h3_match = re.search(r'<h3[^>]*>(.*?)</h3>', content[pos:], re.DOTALL | re.IGNORECASE)
        p_match = re.search(r'<p[^>]*>(.*?)</p>', content[pos:], re.DOTALL | re.IGNORECASE)
        ul_match = re.search(r'<ul[^>]*>(.*?)</ul>', content[pos:], re.DOTALL | re.IGNORECASE)
        ol_match = re.search(r'<ol[^>]*>(.*?)</ol>', content[pos:], re.DOTALL | re.IGNORECASE)

        matches = []
        if h1_match: matches.append(('h1', h1_match))
        if h2_match: matches.append(('h2', h2_match))
        if h3_match: matches.append(('h3', h3_match))
        if p_match: matches.append(('p', p_match))
        if ul_match: matches.append(('ul', ul_match))
        if ol_match: matches.append(('ol', ol_match))

        if not matches:
            break

        # Find the earliest match
        earliest = min(matches, key=lambda x: x[1].start())
        tag_type, match = earliest

        full_match = match.group(0)
        inner_content = match.group(1)
        alignment = get_alignment(full_match)

        if tag_type == 'h1':
            style = ParagraphStyle('h1', parent=styles['Heading1'], alignment=alignment)
            flowables.append(Paragraph(process_inline(inner_content), style))
            flowables.append(Spacer(1, 6*mm))
        elif tag_type == 'h2':
            style = ParagraphStyle('h2', parent=styles['Heading2'], alignment=alignment)
            flowables.append(Paragraph(process_inline(inner_content), style))
            flowables.append(Spacer(1, 4*mm))
        elif tag_type == 'h3':
            style = ParagraphStyle('h3', parent=styles['Heading3'], alignment=alignment)
            flowables.append(Paragraph(process_inline(inner_content), style))
            flowables.append(Spacer(1, 3*mm))
        elif tag_type == 'p':
            text = process_inline(inner_content)
            if text:
                style = ParagraphStyle('p', parent=styles['Normal'], alignment=alignment)
                flowables.append(Paragraph(text, style))
                flowables.append(Spacer(1, 2*mm))
        elif tag_type in ('ul', 'ol'):
            # Extract list items
            li_pattern = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL | re.IGNORECASE)
            items = li_pattern.findall(inner_content)
            if items:
                bullet_type = 'bullet' if tag_type == 'ul' else '1'
                list_items = [ListItem(Paragraph(process_inline(item), styles['Normal'])) for item in items if process_inline(item)]
                if list_items:
                    flowables.append(ListFlowable(list_items, bulletType=bullet_type, leftIndent=10*mm))
                    flowables.append(Spacer(1, 2*mm))

        pos += match.end()

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
