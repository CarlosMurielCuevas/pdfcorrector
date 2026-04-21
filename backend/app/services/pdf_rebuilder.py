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
    Crea una capa que solo cubre y reescribe las palabras concretas que cambiaron,
    manteniendo la fuente, tamaño y color del original.
    """
    overlay_buffer = BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

    for block in blocks:
        if not block.corrected_text or not block.word_data:
            continue

        orig_words = block.original_text.split()
        corr_words = block.corrected_text.split()
        word_positions = block.word_data

        rl_font = _get_reportlab_font(block.font_name)
        font_size = block.font_size or 10

        for i, (orig_w, corr_w) in enumerate(zip(orig_words, corr_words)):
            if orig_w == corr_w:
                continue
            if i >= len(word_positions):
                continue

            wp = word_positions[i]
            x0_w = wp["x0"]
            y0_w = wp["top"]
            x1_w = wp["x1"]
            y1_w = wp["bottom"]

            word_width = x1_w - x0_w
            word_height = y1_w - y0_w
            y_rl = page_height - y1_w

            # Fondo del mismo color que el original
            bg = block.bg_color or [1.0, 1.0, 1.0]
            c.setFillColorRGB(*bg)
            padding = 1
            c.rect(
                x0_w - padding,
                y_rl - padding,
                word_width + padding * 2,
                word_height + padding * 2,
                fill=1,
                stroke=0,
            )

            # Texto corregido con el color y fuente originales
            fg = block.font_color or [0.0, 0.0, 0.0]
            c.setFillColorRGB(*fg)
            c.setFont(rl_font, font_size)
            c.drawString(x0_w, y_rl + 2, corr_w)

    c.save()
    overlay_buffer.seek(0)
    return overlay_buffer
