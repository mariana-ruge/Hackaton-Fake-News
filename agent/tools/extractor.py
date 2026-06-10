"""[1] Extractor — obtiene el contenido de la noticia.

Cadena de extracción para URLs (de mejor a peor):
  1. Bright Data MCP (`scrape_as_markdown`) — sortea anti-bot, sin navegador local.
  2. `scraper.py` (Scraping Browser por WebSocket) — respaldo legado, requiere
     BRIGHT_DATA_WS_URL que ya no está en .env.example.
  3. Degradación: se analiza la URL como texto plano (el verdict lo reflejará).

Si la entrada no es URL, se trata como texto directo.
"""

from __future__ import annotations

import logging
from typing import TypedDict
from urllib.parse import urlparse

from agent.mcp import brightdata_client

logger = logging.getLogger(__name__)


class NoticiaExtraida(TypedDict, total=False):
    url: str | None
    titulo: str
    cuerpo: str
    autor: str | None
    fecha_publicacion: str | None
    dominio: str | None
    extractor_usado: str


def _looks_like_url(text: str) -> bool:
    return bool(text) and text.strip().startswith(("http://", "https://"))


async def extraer(entrada: str) -> NoticiaExtraida:
    """Extrae los metadatos y el cuerpo. Si no es URL, devuelve el texto tal cual."""
    text = (entrada or "").strip()
    if not text:
        return {"url": None, "titulo": "", "cuerpo": "", "autor": None,
                "fecha_publicacion": None, "dominio": None, "extractor_usado": "none"}

    if not _looks_like_url(text):
        return {
            "url": None,
            "titulo": text[:120],
            "cuerpo": text,
            "autor": None,
            "fecha_publicacion": None,
            "dominio": None,
            "extractor_usado": "texto_directo",
        }

    contenido: str | None = None
    extractor_usado = "fallback_url_cruda"

    # 1) Bright Data MCP
    if brightdata_client.is_configured():
        try:
            contenido = await brightdata_client.scrape_url_markdown(text)
            extractor_usado = "brightdata_mcp"
        except Exception as exc:  # noqa: BLE001
            logger.warning("[extractor] Bright Data MCP falló: %s", exc)

    # 2) Respaldo legado: Scraping Browser por WebSocket
    if not contenido:
        try:
            from scraper import extraer_texto_noticia  # type: ignore
            contenido = await extraer_texto_noticia(text)
            extractor_usado = "scraping_browser_legacy"
        except Exception as exc:  # noqa: BLE001
            logger.warning("[extractor] scraper.py falló: %s", exc)

    # 3) Degradación final
    if not contenido:
        contenido = text

    dominio = urlparse(text).hostname
    return {
        "url": text,
        "titulo": contenido.split("\n", 1)[0][:200] if contenido else "",
        "cuerpo": contenido,
        "autor": None,
        "fecha_publicacion": None,
        "dominio": dominio.lower().removeprefix("www.") if dominio else None,
        "extractor_usado": extractor_usado,
    }
