# Servicio para extraer texto de PDFs manteniendo estructura por bloques
import pdfplumber
from io import BytesIO
from app.models import TextBlock
import logging

logger = logging.getLogger(__name__)

# Palabras clave en nombres de fuentes que indican que son fuentes de iconos/símbolos
_SYMBOL_FONT_KEYWORDS = frozenset([
    "symbol", "wingdings", "wingding", "webdings", "marlett",
    "fontawesome", "fontaweso", "awesome", "font awesome",
    "material", "materialicons", "materialdesign",
    "iconic", "icomoon", "ionicons", "feather", "remixicon",
    "glyphicons", "linearicons", "dingbat", "zapfdingbat",
    "brandicon", "socialicon",
])


def _is_symbol_font(fontname: str) -> bool:
    """Devuelve True si el nombre de fuente corresponde a una fuente de iconos/símbolos."""
    if not fontname:
        return False
    lower = fontname.lower().replace("-", "").replace("_", "").replace(" ", "")
    return any(kw.replace(" ", "") in lower for kw in _SYMBOL_FONT_KEYWORDS)


def _has_private_use_chars(text: str) -> bool:
    """Detecta caracteres Unicode de uso privado (iconos) o caracteres de control."""
    for ch in text:
        cp = ord(ch)
        # Unicode Private Use Area: E000-F8FF y F0000-FFFFF
        if (0xE000 <= cp <= 0xF8FF) or (0xF0000 <= cp <= 0xFFFFF):
            return True
        # Caracteres de control excepto tab, newline, retorno
        if cp < 0x0020 and cp not in (0x09, 0x0A, 0x0D):
            return True
    return False


def extract_text_blocks(pdf_bytes: bytes) -> list[TextBlock]:
    """
    Extrae bloques de texto del PDF preservando posición, tamaño de fuente,
    color de fuente, color de fondo y si el bloque contiene iconos/símbolos.
    """
    blocks: list[TextBlock] = []
    block_counter = 0

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                logger.info(f"Procesando página {page_num}/{len(pdf.pages)}")

                words = page.extract_words(
                    x_tolerance=3,
                    y_tolerance=3,
                    keep_blank_chars=False,
                    use_text_flow=True,
                )

                if not words:
                    continue

                page_chars = page.chars or []
                page_rects = [r for r in (page.rects or []) if r.get("fill")]
                # Líneas de subrayado: líneas horizontales delgadas
                page_lines = [
                    l for l in (page.lines or [])
                    if abs(l.get("y0", 0) - l.get("y1", 0)) < 2
                ]

                current_block_words = []
                current_y = None
                LINE_THRESHOLD = 8

                for word in words:
                    word_y = word["top"]

                    if current_y is None or abs(word_y - current_y) <= LINE_THRESHOLD:
                        current_block_words.append(word)
                        current_y = word_y
                    else:
                        if current_block_words:
                            block = _words_to_block(
                                current_block_words, page_num, block_counter,
                                page_chars, page_rects, page_lines
                            )
                            blocks.append(block)
                            block_counter += 1
                        current_block_words = [word]
                        current_y = word_y

                if current_block_words:
                    block = _words_to_block(
                        current_block_words, page_num, block_counter,
                        page_chars, page_rects, page_lines
                    )
                    blocks.append(block)
                    block_counter += 1

    except Exception as e:
        logger.error(f"Error extrayendo texto del PDF: {e}")
        raise ValueError(f"No se pudo procesar el PDF: {str(e)}")

    logger.info(f"Extracción completada: {len(blocks)} bloques en {page_num} páginas")
    return blocks


def _normalize_color(color) -> list[float] | None:
    """
    Convierte el color del formato de pdfplumber (grayscale, RGB, CMYK)
    a una lista RGB [r, g, b] con valores entre 0 y 1.
    Devuelve None si el color no está definido.
    """
    if color is None:
        return None
    if isinstance(color, (int, float)):
        v = float(color)
        return [v, v, v]
    if isinstance(color, (tuple, list)):
        if len(color) == 1:
            v = float(color[0])
            return [v, v, v]
        elif len(color) == 3:
            return [float(c) for c in color]
        elif len(color) == 4:
            # CMYK → RGB
            c, m, y, k = [float(x) for x in color]
            return [
                (1 - c) * (1 - k),
                (1 - m) * (1 - k),
                (1 - y) * (1 - k),
            ]
    return None


def _words_to_block(
    words: list[dict],
    page: int,
    index: int,
    page_chars: list[dict],
    page_rects: list[dict],
    page_lines: list[dict] = [],
) -> TextBlock:
    """Convierte una lista de palabras en un TextBlock con bbox, fuente, color y flags."""
    text = " ".join(w["text"] for w in words)
    x0 = min(w["x0"] for w in words)
    y0 = min(w["top"] for w in words)
    x1 = max(w["x1"] for w in words)
    y1 = max(w["bottom"] for w in words)

    font_size = None
    font_color = None
    bg_color = None
    skip_correction = False

    # Detectamos iconos por caracteres Unicode de uso privado
    if _has_private_use_chars(text):
        skip_correction = True

    # Buscamos los chars que caen dentro del bbox del bloque
    block_chars = [
        c for c in page_chars
        if c.get("x0", 0) >= x0 - 3
        and c.get("x1", 0) <= x1 + 3
        and c.get("top", 0) >= y0 - 3
        and c.get("bottom", 0) <= y1 + 3
        and c.get("text", "").strip()
    ]

    font_name = None
    if block_chars:
        # Detectamos fuentes de iconos/símbolos
        fontnames = [c.get("fontname", "") for c in block_chars]
        if any(_is_symbol_font(fn) for fn in fontnames):
            skip_correction = True

        # Nombre de fuente más frecuente
        valid_fontnames = [fn for fn in fontnames if fn]
        if valid_fontnames:
            font_name = max(set(valid_fontnames), key=valid_fontnames.count)

        # Tamaño de fuente más frecuente
        sizes = [c["size"] for c in block_chars if c.get("size")]
        if sizes:
            font_size = round(max(set(sizes), key=sizes.count), 2)

        # Color de fuente: tomamos el más frecuente entre los chars con color definido
        raw_colors = [c.get("non_stroking_color") for c in block_chars]
        raw_colors = [c for c in raw_colors if c is not None]
        if raw_colors:
            font_color = _normalize_color(raw_colors[0])

    # Buscamos el rectángulo de fondo MÁS PEQUEÑO (más interior/específico) que contenga el bloque
    # Esto evita coger el fondo global de la página en vez del fondo local del elemento
    best_bg = None
    best_area = float("inf")
    for rect in page_rects:
        rx0 = rect.get("x0", 0)
        ry0 = rect.get("top", 0)
        rx1 = rect.get("x1", 0)
        ry1 = rect.get("bottom", 0)
        if rx0 <= x0 + 2 and ry0 <= y0 + 2 and rx1 >= x1 - 2 and ry1 >= y1 - 2:
            area = (rx1 - rx0) * (ry1 - ry0)
            if area < best_area:
                color = rect.get("non_stroking_color")
                normalized = _normalize_color(color)
                # Ignoramos blanco puro (es el fondo por defecto, no aporta info)
                if normalized and normalized != [1.0, 1.0, 1.0]:
                    best_area = area
                    best_bg = normalized

    bg_color = best_bg

    word_data = [
        {"text": w["text"], "x0": w["x0"], "top": w["top"], "x1": w["x1"], "bottom": w["bottom"]}
        for w in words
    ]

    # Detectamos subrayados: líneas horizontales que caen justo debajo del bloque
    underlines = [
        {"x0": l["x0"], "y": l["y0"], "x1": l["x1"], "width": l.get("linewidth", 1),
         "color": _normalize_color(l.get("non_stroking_color") or l.get("stroking_color"))}
        for l in page_lines
        if l.get("x0", 0) >= x0 - 5 and l.get("x1", 0) <= x1 + 5
        and y0 - 5 <= l.get("y0", 0) <= y1 + 8
    ]

    return TextBlock(
        page=page,
        block_index=index,
        original_text=text,
        bbox=[x0, y0, x1, y1],
        font_size=font_size,
        font_name=font_name,
        font_color=font_color,
        bg_color=bg_color,
        skip_correction=skip_correction,
        word_data=word_data,
        underlines=underlines if underlines else None,
    )
