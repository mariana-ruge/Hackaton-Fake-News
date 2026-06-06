"""
Extractor: obtiene el contenido limpio de una noticia a partir de una URL.
Delega el scraping a `agent.mcp.brightdata_client`.
"""

from typing import TypedDict


class NoticiaExtraida(TypedDict):
    url: str
    titulo: str
    cuerpo: str
    autor: str | None
    fecha_publicacion: str | None


async def extraer(url: str) -> NoticiaExtraida:
    """Extrae los metadatos y el cuerpo de la noticia indicada."""
    raise NotImplementedError("Implementar extractor")
