# Endpoint principal de la API: recibe el PDF y devuelve el corregido
import time
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.models import CorrectionResponse, CorrectionStats
from app.services.pdf_extractor import extract_text_blocks
from app.services.ai_corrector import correct_text_blocks
from app.services.pdf_rebuilder import rebuild_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["correction"])

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/correct", response_model=CorrectionResponse)
async def correct_pdf(
    file: UploadFile = File(..., description="Archivo PDF a corregir"),
    context: str = Form(default="", description="Contexto del documento"),
):
    """
    Endpoint principal. Recibe un PDF, extrae su texto, lo corrige con IA
    y devuelve el PDF reconstruido junto con el diff de cambios.
    """
    # Validación del tipo de archivo
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser un PDF válido (.pdf)"
        )

    # Leemos el contenido del archivo
    pdf_bytes = await file.read()

    # Validación del tamaño
    if len(pdf_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el límite de {MAX_FILE_SIZE_MB} MB"
        )

    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    start_time = time.time()
    logger.info(f"Procesando PDF: {file.filename} ({len(pdf_bytes)/1024:.1f} KB)")

    try:
        # Paso 1: Extraemos bloques de texto con posición
        logger.info("Paso 1/3: Extrayendo texto...")
        blocks = extract_text_blocks(pdf_bytes)

        if not blocks:
            raise HTTPException(
                status_code=422,
                detail="No se pudo extraer texto del PDF. El archivo puede ser un PDF escaneado (solo imágenes)."
            )

        # Paso 2: Corregimos con IA
        logger.info(f"Paso 2/3: Corrigiendo {len(blocks)} bloques con IA...")
        corrected_blocks = await correct_text_blocks(blocks, context)

        # Paso 3: Reconstruimos el PDF
        logger.info("Paso 3/3: Reconstruyendo PDF...")
        pdf_base64 = rebuild_pdf(pdf_bytes, corrected_blocks)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"Error inesperado procesando {file.filename}")
        raise HTTPException(
            status_code=500,
            detail="Error interno procesando el PDF. Por favor inténtalo de nuevo."
        )

    # Calculamos estadísticas
    elapsed = time.time() - start_time
    total_changes = sum(
        1 for b in corrected_blocks if b.original_text != b.corrected_text
    )

    stats = CorrectionStats(
        total_blocks=len(corrected_blocks),
        corrected_blocks=total_changes,
        total_changes=total_changes,
        processing_time_seconds=round(elapsed, 2),
    )

    logger.info(
        f"PDF procesado en {elapsed:.2f}s — "
        f"{total_changes}/{len(corrected_blocks)} bloques modificados"
    )

    return CorrectionResponse(
        blocks=corrected_blocks,
        stats=stats,
        pdf_base64=pdf_base64,
    )