# PDFCorrector

Aplicación web fullstack que corrige errores ortográficos en documentos PDF usando inteligencia artificial, preservando el diseño y la estética original del documento.

## ¿Qué hace?

1. El usuario sube un PDF desde el navegador
2. El backend extrae el texto del PDF bloque a bloque, conservando posición, fuente y colores
3. La IA (Groq / Llama 3.3) corrige únicamente errores ortográficos puros (b/v, h, tildes, s/z...) sin tocar mayúsculas, URLs, emails, iconos ni nombres propios
4. El PDF se reconstruye con el texto corregido manteniendo el diseño original
5. El usuario descarga el PDF corregido y puede ver un diff con los cambios realizados

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| Frontend | Angular 20 + TypeScript |
| Backend | Python 3.13 + FastAPI |
| Extracción PDF | pdfplumber |
| Reconstrucción PDF | pypdf + reportlab |
| IA | Groq API (llama-3.3-70b-versatile) |
| i18n | ngx-translate (español / inglés) |

## Estructura del proyecto

```
pdfcorrector/
├── backend/
│   ├── app/
│   │   ├── main.py              # Punto de entrada FastAPI
│   │   ├── config.py            # Configuración y variables de entorno
│   │   ├── models.py            # Modelos Pydantic
│   │   ├── routes/
│   │   │   └── correction.py    # Endpoint POST /api/correct
│   │   └── services/
│   │       ├── pdf_extractor.py # Extrae bloques de texto del PDF
│   │       ├── ai_corrector.py  # Llama a la IA para corregir
│   │       └── pdf_rebuilder.py # Reconstruye el PDF corregido
│   ├── .env.example
│   └── requirements.txt
└── frontend/
    └── src/
        └── app/
            ├── core/            # Servicios y modelos
            ├── features/home/   # Upload, diff viewer, resultado
            └── shared/          # Navbar, spinner
```

## Requisitos previos

- Python 3.11 o superior
- Node.js 18 o superior
- Una API key gratuita de [Groq](https://console.groq.com)

## Instalación y arranque

### Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Edita .env y añade tu GROQ_API_KEY
```

Contenido del `.env`:
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
ALLOWED_ORIGINS=http://localhost:4200
```

Arrancar el servidor:
```bash
python run.py
```

El backend queda disponible en `http://localhost:8000`.  
Documentación interactiva: `http://localhost:8000/docs`

---

### Frontend

```bash
cd frontend

# Instalar dependencias
npm install

# Arrancar en modo desarrollo
npm start
```

La aplicación queda disponible en `http://localhost:4200`.

## Endpoint principal

```
POST /api/correct
Content-Type: multipart/form-data

Parámetros:
  file     → archivo PDF (máximo 20 MB)
  context  → descripción opcional del documento (mejora la corrección)

Respuesta:
  blocks       → lista de bloques con texto original y corregido
  stats        → estadísticas (bloques procesados, cambios, tiempo)
  pdf_base64   → PDF corregido codificado en base64
```

## Notas

- PDFs escaneados (solo imágenes) no son compatibles, se necesita texto seleccionable
- La IA no modifica mayúsculas, URLs, emails, nombres propios, tecnologías ni iconos
- El modelo Groq gratuito tiene un límite de ~14.400 peticiones/día
