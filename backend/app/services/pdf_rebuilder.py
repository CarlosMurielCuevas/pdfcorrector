import pypdf
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from io import BytesIO
import base64
import logging
from app.models import TextBlock

logger = logging.getLogger(__name__)


def _get_reportlab_font(font_name: str | None) -> str:
    """Mapea el nombre de fuente del PDF al equivalente estándar de reportlab."""
    if not font_name:
        return "Helvetica"
    name = font_name.lower()
    if "+" in name:
        name = name.split("+", 1)[1]

    is_bold = "bold" in name
    is_italic = "italic" in name or "oblique" in name

    if "times" in name or "roman" in name:
        if is_bold and is_italic:
            return "Times-BoldItalic"
        if is_bold:
            return "Times-Bold"
        if is_italic:
            return "Times-Italic"
        return "Times-Roman"
    if "courier" in name or "mono" in name:
        if is_bold:
            return "Courier-Bold"
        if is_italic:
            return "Courier-Oblique"
        return "Courier"
    if is_bold and is_italic:
        return "Helvetica-BoldOblique"
    if is_bold:
        return "Helvetica-Bold"
    if is_italic:
        return "Helvetica-Oblique"
    return "Helvetica"


def rebuild_pdf(original_bytes: bytes, corrected_blocks: list[TextBlock]) -> str:
    try:
        reader = PdfReader(BytesIO(original_bytes))
        writer = PdfWriter()

        blocks_by_page: dict[int, list[TextBlock]] = {}
        for block in corrected_blocks:
            if block.original_text != block.corrected_text and block.corrected_text:
                blocks_by_page.setdefault(block.page, []).append(block)

        for page_num, page in enumerate(reader.pages, start=1):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            page_blocks = blocks_by_page.get(page_num, [])
            if page_blocks:
                overlay = _create_word_overlay(page_blocks, page_width, page_height)
                overlay_reader = PdfReader(overlay)
                page.merge_page(overlay_reader.pages[0])

            writer.add_page(page)

        output = BytesIO()
        writer.write(output)
        output.seek(0)
        return base64.b64encode(output.read()).decode("utf-8")

    except Exception as e:
        logger.error(f"Error reconstruyendo PDF: {e}")
        raise ValueError(f"No se pudo reconstruir el PDF: {str(e)}")


def _create_word_overlay(
    blocks: list[TextBlock], page_width: float, page_height: float
) -> BytesIO:
    """
    Cubre y reescribe el bloque completo de cada línea que tiene cambios,
    manteniendo fuente, tamaño y color originales.
    """
    overlay_buffer = BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

    for block in blocks:
        if not block.corrected_text or not block.bbox:
            continue

        x0, y0_pdf, x1, y1_pdf = block.bbox
        block_width = x1 - x0
        block_height = y1_pdf - y0_pdf
        y_rl = page_height - y1_pdf

        rl_font = _get_reportlab_font(block.font_name)
        font_size = block.font_size or max(6, min(round(block_height * 0.85), 14))

        # Rectángulo de fondo del mismo color que el original
        bg = block.bg_color or [1.0, 1.0, 1.0]
        c.setFillColorRGB(*bg)
        padding = 1
        c.rect(
            x0 - padding,
            y_rl - padding,
            block_width + padding * 2,
            block_height + padding * 2,
            fill=1,
            stroke=0,
        )

        # Texto completo corregido con el color y fuente originales
        fg = block.font_color or [0.0, 0.0, 0.0]
        c.setFillColorRGB(*fg)
        c.setFont(rl_font, font_size)

        # Si el texto corregido es más ancho que el bloque original, lo comprimimos
        text_width = c.stringWidth(block.corrected_text, rl_font, font_size)
        if text_width > block_width and text_width > 0:
            c.setHorizScale((block_width / text_width) * 100)
        else:
            c.setHorizScale(100)

        c.drawString(x0, y_rl + 2, block.corrected_text)
        c.setHorizScale(100)

    c.save()
    overlay_buffer.seek(0)
    return overlay_buffer
