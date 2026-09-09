from io import BytesIO
from functools import lru_cache
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

TEMPLATE_PATH = Path(__file__).with_name("certificate_formate.png")
DEFAULT_RANK = "Participant"
PAGE_WIDTH = 920
PAGE_HEIGHT = 680
MAX_TEMPLATE_SIZE = (2300, 1700)


def _draw_centered_text(pdf: canvas.Canvas, text: str, x: float, y: float, font_size: int) -> None:
    font_name = "Helvetica-Bold"
    pdf.setFont(font_name, font_size)
    text_width = stringWidth(text, font_name, font_size)
    pdf.drawString(x - text_width / 2, y, text)


@lru_cache(maxsize=1)
def _optimized_template() -> bytes:
    template_buffer = BytesIO()
    with Image.open(TEMPLATE_PATH) as template_image:
        template_image.thumbnail(MAX_TEMPLATE_SIZE, Image.Resampling.LANCZOS)
        template_image.save(
            template_buffer,
            format="JPEG",
            quality=88,
            optimize=True,
        )
    return template_buffer.getvalue()


def create_certificate(name: str, rank: str | None = DEFAULT_RANK) -> BytesIO:
    template = ImageReader(BytesIO(_optimized_template()))
    page_width, page_height = PAGE_WIDTH, PAGE_HEIGHT

    overlay_buffer = BytesIO()
    overlay = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
    overlay.drawImage(template, 0, 0, width=page_width, height=page_height)

    overlay.setFillColorRGB(0.04, 0.07, 0.14)
    base_font_size = 20
    name_width = stringWidth(name, "Helvetica-Bold", base_font_size)
    name_font_size = min(base_font_size, max(18, 980 / max(name_width, 1) * base_font_size))
    name_width = stringWidth(name, "Helvetica-Bold", name_font_size)
    name_y = 300
    overlay.setFillColorRGB(1, 1, 1)
    overlay.rect(
        page_width / 2 - name_width / 2 - 8,
        name_y - 3,
        name_width + 16,
        25,
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
