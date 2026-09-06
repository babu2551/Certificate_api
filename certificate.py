from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

TEMPLATE_PATH = Path(__file__).with_name("certificate_formate.png")


def _draw_centered_text(pdf: canvas.Canvas, text: str, x: float, y: float, font_size: int) -> None:
    font_name = "Helvetica-Bold"
    pdf.setFont(font_name, font_size)
    text_width = stringWidth(text, font_name, font_size)
    pdf.drawString(x - text_width / 2, y, text)


def _draw_checkmark(pdf: canvas.Canvas, x: float, y: float) -> None:
    pdf.setStrokeColorRGB(0.04, 0.07, 0.14)
    pdf.setLineWidth(3)
    pdf.line(x - 9, y, x - 2, y - 8)
    pdf.line(x - 2, y - 8, x + 11, y + 10)


def create_certificate(name: str, rank: str | None = None) -> BytesIO:
    template = ImageReader(str(TEMPLATE_PATH))
    page_width, page_height = template.getSize()

    overlay_buffer = BytesIO()
    overlay = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
    overlay.drawImage(template, 0, 0, width=page_width, height=page_height)

    overlay.setFillColorRGB(0.04, 0.07, 0.14)
    name_width = stringWidth(name, "Helvetica-Bold", 34)
    name_font_size = min(34, max(18, 980 / max(name_width, 1) * 34))
    _draw_centered_text(overlay, name, page_width / 2, 432, int(name_font_size))

    rank_centers = {"first": 594, "second": 879, "third": 1134}
    if rank in rank_centers:
        _draw_checkmark(overlay, rank_centers[rank], 349)

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
