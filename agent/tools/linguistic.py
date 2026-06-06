"""
Análisis lingüístico: detecta sesgos, lenguaje emocional, alarmismo,
clickbait y banderas rojas típicas de estafas (FOMO, urgencia, etc.).
"""

from typing import TypedDict


class AnalisisLinguistico(TypedDict):
    alarmismo: float          # 0.0 - 1.0
    sesgo: float              # 0.0 - 1.0
    clickbait: float          # 0.0 - 1.0
    banderas_rojas: list[str]


def analizar(texto: str) -> AnalisisLinguistico:
    """Analiza el tono y los marcadores lingüísticos sospechosos."""
    raise NotImplementedError("Implementar análisis lingüístico (usar prompt es)")
