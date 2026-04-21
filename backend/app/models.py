# Modelos Pydantic para request/response de la API
from pydantic import BaseModel, Field
from typing import Optional


class TextBlock(BaseModel):
    """Bloque de texto extraído de una página del PDF."""
    page: int = Field(..., description="Número de página (1-indexed)")
    block_index: int = Field(..., description="Índice del bloque en la página")
    original_text: str = Field(..., description="Texto original extraído")
    corrected_text: Optional[str] = Field(None, description="Texto corregido por la IA")
    bbox: Optional[list[float]] = Field(None, description="Coordenadas del bloque [x0,y0,x1,y1]")
    font_size: Optional[float] = Field(None, description="Tamaño de fuente original en puntos")
    font_color: Optional[list[float]] = Field(None, description="Color de fuente RGB [r,g,b] en rango 0-1")
    font_name: Optional[str] = Field(None, description="Nombre de fuente original")
    bg_color: Optional[list[float]] = Field(None, description="Color de fondo RGB [r,g,b] en rango 0-1")
    skip_correction: bool = Field(False, description="Si es True, no se envía a la IA (iconos, símbolos, etc.)")
    word_data: Optional[list[dict]] = Field(None, exclude=True, description="Posiciones de palabras - no se serializa")


class CorrectionStats(BaseModel):
    """Estadísticas del proceso de corrección."""
    total_blocks: int
    corrected_blocks: int
    total_changes: int
    processing_time_seconds: float


class CorrectionResponse(BaseModel):
    """Respuesta completa del endpoint de corrección."""
    blocks: list[TextBlock]
    stats: CorrectionStats
    pdf_base64: str = Field(..., description="PDF corregido codificado en base64")


class AIBlockResponse(BaseModel):
    """Estructura que devuelve la IA para cada bloque."""
    block_index: int
    corrected_text: str
    changes_count: int