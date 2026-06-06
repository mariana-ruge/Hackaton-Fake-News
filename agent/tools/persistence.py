"""
Persistencia: guarda análisis, claims y veredictos para auditoría y para
alimentar el índice de fact-checkers (Elasticsearch).
"""

from typing import Any


async def guardar_analisis(payload: dict[str, Any]) -> str:
    """Persiste un análisis completo y devuelve su identificador."""
    raise NotImplementedError("Implementar persistencia (Elastic / BD)")


async def obtener_analisis(analisis_id: str) -> dict[str, Any] | None:
    """Recupera un análisis previo por id."""
    raise NotImplementedError("Implementar lectura de análisis")
