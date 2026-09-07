from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

TEMPLATE_PATH = Path(__file__).with_name("certificate_formate.png")
DEFAULT_RANK = "Participant"


def _draw_centered_text(pdf: canvas.Canvas, text: str, x: float, y: float, font_size: int) -> None:
    font_name = "Helvetica-Bold"
    pdf.setFont(font_name, font_size)
    text_width = stringWidth(text, font_name, font_size)
    pdf.drawString(x - text_width / 2, y, text)


def create_certificate(name: str, rank: str | None = DEFAULT_RANK) -> BytesIO:
    template = ImageReader(str(TEMPLATE_PATH))
    page_width, page_height = template.getSize()

    overlay_buffer = BytesIO()
    overlay = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
    overlay.drawImage(template, 0, 0, width=page_width, height=page_height)

    overlay.setFillColorRGB(0.04, 0.07, 0.14)
    name_width = stringWidth(name, "Helvetica-Bold", 34)
    name_font_size = min(34, max(18, 980 / max(name_width, 1) * 34))
    name_y = 590
    overlay.setFillColorRGB(1, 1, 1)
    overlay.rect(
        page_width / 2 - name_width / 2 - 14,
        name_y - 5,
        name_width + 28,
        42,
        fill=1,
        stroke=0,
    )
    overlay.setFillColorRGB(0.04, 0.07, 0.14)
    _draw_centered_text(overlay, name, page_width / 2, name_y, int(name_font_size))

    overlay.save()

    overlay_buffer.seek(0)
    overlay_page = PdfReader(overlay_buffer).pages[0]

    output = BytesIO()
    writer = PdfWriter()
    writer.add_page(overlay_page)
    writer.add_metadata({"/Title": f"Certificate - {name}"})
    writer.write(output)
    output.seek(0)
    return output
