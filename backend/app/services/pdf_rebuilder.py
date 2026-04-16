# Servicio para reconstruir el PDF manteniendo el diseño original
# con el texto corregido superpuesto sobre el original
import pypdf
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from io import BytesIO
import base64
import logging
from app.models import TextBlock

logger = logging.getLogger(__name__)


def rebuild_pdf(original_bytes: bytes, corrected_blocks: list[TextBlock]) -> str:
    """
    Reconstruye el PDF reemplazando el texto original con el corregido.

    Estrategia: Para cada página, creamos una capa de texto con reportlab
    que se fusiona sobre el PDF original. Esto preserva imágenes,
    formatos y elementos visuales.
    """
    try:
        reader = PdfReader(BytesIO(original_bytes))
        writer = PdfWriter()

        blocks_by_page: dict[int, list[TextBlock]] = {}
        for block in corrected_blocks:
            if block.page not in blocks_by_page:
                blocks_by_page[block.page] = []
            blocks_by_page[block.page].append(block)

        for page_num, page in enumerate(reader.pages, start=1):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            page_blocks = blocks_by_page.get(page_num, [])

            if page_blocks:
                overlay = _create_text_overlay(page_blocks, page_width, page_height)
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


def _create_text_overlay(
    blocks: list[TextBlock], page_width: float, page_height: float
) -> BytesIO:
    """
    Crea una capa PDF transparente con el texto corregido posicionado
    exactamente donde estaba el texto original, respetando el color
    y tamaño de fuente originales.
    """
    overlay_buffer = BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

    # Fondo completamente transparente
    c.setFillAlpha(0)
    c.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    c.setFillAlpha(1)

    for block in blocks:
        if block.original_text == block.corrected_text:
            continue
        if not block.bbox or not block.corrected_text:
            continue

        x0, y0_pdf, x1, y1_pdf = block.bbox

        # Conversión de coordenadas pdfplumber (top-left) → reportlab (bottom-left)
        y_reportlab = page_height - y1_pdf
        block_width = x1 - x0
        block_height = y1_pdf - y0_pdf

        # Tamaño de fuente: usamos el extraído o lo estimamos por la altura del bloque
        font_size = block.font_size or max(6, min(round(block_height * 0.85), 14))

        # Color de fondo: usamos el extraído del PDF o blanco por defecto
        if block.bg_color:
            c.setFillColorRGB(*block.bg_color)
        else:
            c.setFillColorRGB(1, 1, 1)

        padding = 1
        c.rect(
            x0 - padding,
            y_reportlab - padding,
            block_width + padding * 2,
            block_height + padding * 2,
            fill=1,
            stroke=0,
        )

        # Color de texto: usamos el extraído del PDF o negro por defecto
        if block.font_color:
            c.setFillColorRGB(*block.font_color)
        else:
            c.setFillColorRGB(0, 0, 0)

        c.setFont("Helvetica", font_size)
        text_object = c.beginText(x0, y_reportlab + 2)
        text_object.setFont("Helvetica", font_size)
        text_object.setLeading(font_size * 1.2)
        text_object.textLine(block.corrected_text)
        c.drawText(text_object)

    c.save()
    overlay_buffer.seek(0)
    return overlay_buffer
