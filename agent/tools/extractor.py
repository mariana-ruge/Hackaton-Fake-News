"""[1] Extractor — obtiene el contenido de la noticia.

Si la entrada empieza por http/https, intenta extraerla con `scraper.py`
(Bright Data Scraping Browser). Para Bright Data MCP, ver
`main.py::_fetch_url_with_brightdata` que vive en el contexto FastAPI.
"""

from __future__ import annotations

import logging
from typing import TypedDict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class NoticiaExtraida(TypedDict, total=False):
    url: str | None
    titulo: str
    cuerpo: str
    autor: str | None
    fecha_publicacion: str | None
    dominio: str | None


def _looks_like_url(text: str) -> bool:
    return bool(text) and text.strip().startswith(("http://", "https://"))


async def extraer(entrada: str) -> NoticiaExtraida:
    """Extrae los metadatos y el cuerpo. Si no es URL, devuelve el texto tal cual."""
    text = (entrada or "").strip()
    if not text:
        return {"url": None, "titulo": "", "cuerpo": "", "autor": None,
                "fecha_publicacion": None, "dominio": None}

    if not _looks_like_url(text):
        return {
            "url": None,
            "titulo": text[:120],
            "cuerpo": text,
            "autor": None,
            "fecha_publicacion": None,
            "dominio": None,
        }

    # Es URL: intentamos extraer con scraper.py (best-effort).
    try:
        from scraper import extraer_texto_noticia  # type: ignore
        contenido = await extraer_texto_noticia(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[extractor] scraper.py falló: %s", exc)
        contenido = text  # degradación

    dominio = urlparse(text).hostname
    return {
        "url": text,
        "titulo": contenido.split("\n", 1)[0][:200] if contenido else "",
        "cuerpo": contenido,
        "autor": None,
        "fecha_publicacion": None,
        "dominio": dominio.lower().lstrip("www.") if dominio else None,
    }
