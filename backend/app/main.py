# Punto de entrada de la aplicación FastAPI
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.correction import router as correction_router

# Configuramos logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

settings = get_settings()

app = FastAPI(
    title="PDFCorrector API",
    description="API para corrección ortográfica y de estilo de documentos PDF usando IA",
    version="1.0.0",
)

# Middleware CORS — permitimos las peticiones desde el frontend Angular
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registramos las rutas
app.include_router(correction_router)


@app.get("/health")
async def health_check():
    """Endpoint de salud para verificar que el servidor está activo."""
    return {"status": "ok", "model": settings.groq_model}