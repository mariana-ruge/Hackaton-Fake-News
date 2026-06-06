"""
Source Checker: evalúa la credibilidad de la fuente (dominio, historial,
reputación) consultando bases internas y servicios externos.
"""

from typing import TypedDict


class EvaluacionFuente(TypedDict):
    dominio: str
    credibilidad: float  # 0.0 - 1.0
    categoria: str       # ej: "medio reconocido", "blog", "red social"
    notas: list[str]


def evaluar_fuente(url: str) -> EvaluacionFuente:
    """Devuelve una evaluación de credibilidad para el dominio de la URL."""
    raise NotImplementedError("Implementar source checker")
