"""
Verdict: consolida claims, evidencias, evaluación de fuente y análisis
lingüístico en un veredicto final estructurado para el usuario.
"""

from typing import Literal, TypedDict


class Veredicto(TypedDict):
    etiqueta: Literal["verdadero", "engañoso", "falso", "no_verificable"]
    confianza: float
    resumen: str
    evidencias_clave: list[str]
    nota_neutralidad: str | None


def emitir_veredicto(claims, evidencias, fuente, linguistico) -> Veredicto:
    """Produce un veredicto consolidado."""
    raise NotImplementedError("Implementar generador de veredicto (usar prompt es)")
