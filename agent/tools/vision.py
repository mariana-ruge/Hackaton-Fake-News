"""[V] Visión — extrae el claim de una captura de pantalla.

Las fake news financieras circulan como pantallazos (cadenas de WhatsApp,
posts de Instagram de pseudo-traders, "capturas de ganancias"). Gemini es
multimodal: no hace falta OCR — el modelo transcribe el texto Y describe
señales visuales sospechosas (logos imitados, urgencia, ganancias fabricadas).

Funciona en ambos modos de auth (ADR-0006): `google-genai` acepta imágenes
tanto en Vertex/ADC como con API key.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TypedDict

from google.genai import types as genai_types

from agent.genai_client import get_client, get_config
from agent.llm_client import _parse_json_tolerant

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}

_PROMPT = """Analiza esta imagen. Probablemente es una captura de pantalla de una
noticia, un mensaje viral o una promesa de inversión (WhatsApp, Instagram,
Telegram, X). Devuelve SOLO un JSON con esta forma exacta:

{
  "texto_extraido": "<transcripción fiel del texto principal visible>",
  "claim_principal": "<la afirmación o promesa central, en una sola frase>",
  "senales_visuales": ["<señal sospechosa VISIBLE: logo imitado, captura de ganancias, cuenta sin verificar, urgencia gráfica, etc.>"]
}

Reglas:
- Transcribe en el idioma original de la imagen.
- "senales_visuales" solo incluye lo que se VE (no infieras del contenido textual).
- Si no hay texto legible ni claim, devuelve cadenas vacías y lista vacía."""


class VisionResult(TypedDict, total=False):
    texto_extraido: str
    claim_principal: str
    senales_visuales: list[str]


async def extraer_de_imagen(imagen: bytes, mime_type: str) -> VisionResult:
    """Extrae texto, claim y señales visuales de una captura.

    Raises:
        ValueError: mime no soportado o imagen demasiado grande
                    (el endpoint los traduce a HTTP 400).
    """
    mime_type = (mime_type or "").lower().strip()
    if mime_type not in ALLOWED_MIME:
        raise ValueError(
            f"Tipo de imagen no soportado: {mime_type or '(vacío)'}. Usa PNG, JPEG o WebP."
        )
    if not imagen:
        raise ValueError("Imagen vacía.")
    if len(imagen) > MAX_IMAGE_BYTES:
        raise ValueError("Imagen demasiado grande (máximo 4 MB).")

    cfg = get_config()
    client = get_client()
    config = genai_types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
    )

    def _call() -> str:
        resp = client.models.generate_content(
            model=cfg.model_name,
            contents=[
                genai_types.Part.from_bytes(data=imagen, mime_type=mime_type),
                _PROMPT,
            ],
            config=config,
        )
        return resp.text or ""

    raw = await asyncio.to_thread(_call)
    if not raw:
        raise RuntimeError("Gemini Vision devolvió respuesta vacía.")

    data = _parse_json_tolerant(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"Respuesta de visión no es un objeto JSON: {type(data).__name__}")

    return {
        "texto_extraido": str(data.get("texto_extraido", "")).strip(),
        "claim_principal": str(data.get("claim_principal", "")).strip(),
        "senales_visuales": [str(s) for s in (data.get("senales_visuales") or [])][:10],
    }
