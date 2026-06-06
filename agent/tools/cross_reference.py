"""
Cross Reference: contrasta cada claim contra múltiples fuentes (medios,
fact-checkers indexados en Elastic, etc.) y devuelve evidencias.
"""

from typing import TypedDict


class Evidencia(TypedDict):
    claim_id: str
    fuente: str
    url: str
    fragmento: str
    soporte: str  # "confirma" | "refuta" | "contexto"


async def contrastar(claim_id: str, claim_texto: str) -> list[Evidencia]:
    """Busca evidencias en múltiples fuentes para un claim concreto."""
    raise NotImplementedError("Implementar cross reference")
