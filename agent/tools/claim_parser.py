"""
Claim Parser: descompone una noticia o texto en afirmaciones verificables
(claims) atómicas e independientes.
"""

from typing import TypedDict


class Claim(TypedDict):
    id: str
    texto: str
    entidades: list[str]
    fecha_referida: str | None


def parsear_claims(texto: str) -> list[Claim]:
    """Devuelve la lista de afirmaciones verificables encontradas en `texto`."""
    raise NotImplementedError("Implementar claim parser (usar prompt es)")
