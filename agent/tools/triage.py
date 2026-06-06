"""
Triage: clasifica la entrada del usuario (URL, texto, captura) y decide la ruta
de procesamiento (extracción web, parseo directo, OCR, etc.).
"""

from typing import Literal, TypedDict


class TriageResult(TypedDict):
    tipo: Literal["url", "texto", "imagen", "desconocido"]
    confianza: float
    siguiente_paso: str


def triage(entrada: str) -> TriageResult:
    """Determina el tipo de entrada y el siguiente paso del pipeline."""
    raise NotImplementedError("Implementar lógica de triage")
