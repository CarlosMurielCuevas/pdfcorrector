# Servicio que llama a Groq para corregir el texto extraído
import httpx
import json
import logging
import re
from app.models import TextBlock
from app.config import get_settings
import asyncio

# Detecta bloques que son puramente URLs, emails, dominios o rutas
_SKIP_PATTERN = re.compile(
    r'^('
    r'https?://\S+'                                                          # URL con protocolo
    r'|www\.\S+'                                                             # URL con www
    r'|[\w.+-]+@[\w-]+\.[\w.-]+'                                            # email
    r'|[\w][\w.-]*\.(?:com|net|org|io|app|dev|es|co|uk|fr|de|vercel)'      # dominio sin protocolo
      r'(?:\.[\w-]+)*(?:/\S*)?'                                              # subdominio y path opcionales
    r'|[A-Za-z]:\\[\w\\.\-]+'                                               # ruta Windows
    r'|/[\w/.\-]+'                                                           # ruta Unix
    r')$',
    re.IGNORECASE,
)

# Detecta tokens que no deben tocarse dentro de texto mixto
_PRESERVE_PATTERN = re.compile(
    r'https?://\S+'                                                          # URL con protocolo
    r'|www\.\S+'                                                             # URL con www
    r'|[\w.+-]+@[\w-]+\.[\w.-]+'                                            # email
    r'|[\w][\w.-]*\.(?:com|net|org|io|app|dev|es|co|uk|fr|de|vercel)'      # dominio sin protocolo
      r'(?:\.[\w-]+)*(?:/\S*)?',                                             # subdominio y path
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Límite de bloques por llamada para evitar exceder el contexto del modelo
BATCH_SIZE = 53


async def correct_text_blocks(
    blocks: list[TextBlock], context: str
) -> list[TextBlock]:
    """
    Envía los bloques de texto a la IA para su corrección.
    Procesa en lotes para manejar documentos largos.
    
    Args:
        blocks: Lista de bloques extraídos del PDF
        context: Descripción del documento dada por el usuario
        
    Returns:
        Lista de bloques con el campo corrected_text rellenado
    """
    settings = get_settings()
    corrected_blocks = list(blocks)  # copia para no mutar la original

    # Pre-filtro: iconos/símbolos y bloques pura URL/email se omiten directamente
    skip_indices: set[int] = set()
    for i, block in enumerate(blocks):
        if block.skip_correction or _SKIP_PATTERN.match(block.original_text.strip()):
            corrected_blocks[i].corrected_text = block.original_text
            skip_indices.add(i)

    # Procesamos en lotes
    for batch_start in range(0, len(blocks), BATCH_SIZE):
        batch = blocks[batch_start : batch_start + BATCH_SIZE]

        # Excluimos del lote los bloques ya resueltos (URLs/emails)
        active_batch = [
            b for i, b in enumerate(batch)
            if (batch_start + i) not in skip_indices
        ]
        active_indices = [
            i for i in range(len(batch))
            if (batch_start + i) not in skip_indices
        ]

        if not active_batch:
            continue

        logger.info(
            f"Procesando lote {batch_start//BATCH_SIZE + 1}, "
            f"{len(active_batch)} bloques activos de {len(batch)}"
        )

        corrections = await _call_groq(active_batch, context, settings)

        # Remapeamos block_index del lote activo al índice global
        index_map = {ai_i: active_indices[ai_i] for ai_i in range(len(active_batch))}

        # Aplicamos las correcciones al listado completo usando el remapeo
        for correction in corrections:
            ai_idx = correction.get("block_index", -1)
            local_idx = index_map.get(ai_idx, -1)
            global_idx = batch_start + local_idx
            if 0 <= global_idx < len(corrected_blocks):
                corrected_text = correction.get("corrected_text", "")
                original = corrected_blocks[global_idx].original_text
                # Post-proceso: restaura URLs/emails que la IA pudo haber alterado
                corrected_text = _restore_preserved_tokens(original, corrected_text)
                corrected_blocks[global_idx].corrected_text = corrected_text or original

    # Los bloques sin corrección conservan el texto original
    for block in corrected_blocks:
        if block.corrected_text is None:
            block.corrected_text = block.original_text

    return corrected_blocks


async def _call_groq(
    batch: list[TextBlock], context: str, settings
) -> list[dict]:
    """
    Realiza la llamada HTTP a la API de Groq con el lote de bloques.

    Returns:
        Lista de dicts con block_index y corrected_text
    """
    # Preparamos el payload con los bloques numerados
    blocks_payload = [
        {"block_index": i, "text": b.original_text}
        for i, b in enumerate(batch)
    ]

    context_info = f"Tipo de documento: {context}" if context.strip() else ""

    prompt = f"""Eres un corrector ortográfico especializado en español. Tu ÚNICA tarea es corregir errores fonéticos puros en palabras españolas.

SOLO debes corregir estos tipos de errores y NADA MÁS:
- Confusión b/v (ej: "havlar" → "hablar")
- H omitida o sobrante (ej: "acer" → "hacer", "hera" → "era")
- Confusión s/z/c (ej: "serbicio" → "servicio")
- Tildes faltantes en palabras españolas (ej: "tambien" → "también")
- Confusión ll/y en palabras españolas

PROHIBIDO absolutamente:
- NUNCA cambies mayúsculas a minúsculas ni minúsculas a mayúsculas — si está en MAYÚSCULAS es diseño intencional
- NUNCA cambies la capitalización de ninguna palabra
- NUNCA toques palabras en inglés — cópialas exactamente igual
- NUNCA toques URLs, dominios ni enlaces (con o sin protocolo)
- NUNCA toques emails ni números de teléfono
- NUNCA toques nombres propios (personas, empresas, lugares, productos)
- NUNCA toques siglas ni abreviaturas
- NUNCA toques nombres de tecnologías (Angular, Python, TypeScript, SQL, Git, etc.)
- NUNCA elimines ni cambies caracteres especiales o iconos
- NUNCA cambies el orden de palabras ni reescribas frases
- Si no hay error fonético claro, devuelve el texto EXACTAMENTE igual

{context_info}

Devuelve ÚNICAMENTE un JSON válido sin markdown ni explicaciones:
[
  {{"block_index": 0, "corrected_text": "texto aquí", "changes_count": 0}},
  ...
]

Bloques a revisar:
{json.dumps(blocks_payload, ensure_ascii=False)}"""

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,  # Baja temperatura para correcciones más consistentes
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        for intento in range(3):  # máximo 3 intentos
            try:
                response = await client.post(
                    GROQ_URL, headers=headers, json=payload
                )

                if response.status_code == 429:
                    espera = 30 * (intento + 1)  # 30s, 60s, 90s
                    logger.warning(f"Rate limit alcanzado, esperando {espera}s (intento {intento+1}/3)")
                    await asyncio.sleep(espera)
                    continue

                response.raise_for_status()
                break  # éxito, salimos del bucle

            except httpx.HTTPStatusError as e:
                if intento == 2:  # último intento
                    logger.error(f"Error HTTP de Groq: {e.response.status_code} - {e.response.text}")
                    raise ValueError(f"Error al llamar a la IA: {e.response.status_code}")
            except httpx.TimeoutException:
                raise ValueError("La solicitud a la IA excedió el tiempo límite.")

    data = response.json()
    raw_text = data["choices"][0]["message"]["content"]

    # Parseamos el JSON devuelto por la IA
    try:
        # Limpiamos posibles marcadores de código markdown
        clean = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except json.JSONDecodeError as e:
        logger.error(f"La IA no devolvió JSON válido: {raw_text[:200]}")
        # Fallback: devolvemos los textos originales sin corrección
        return [
            {"block_index": i, "corrected_text": b.original_text, "changes_count": 0}
            for i, b in enumerate(batch)
        ]


def _restore_preserved_tokens(original: str, corrected: str) -> str:
    """
    Si la IA modificó alguna URL o email que existía en el original,
    los restaura al valor exacto original.
    """
    if not corrected:
        return original

    orig_tokens = _PRESERVE_PATTERN.findall(original)
    corr_tokens = _PRESERVE_PATTERN.findall(corrected)

    result = corrected
    for orig_tok, corr_tok in zip(orig_tokens, corr_tokens):
        if orig_tok != corr_tok:
            result = result.replace(corr_tok, orig_tok, 1)

    return result