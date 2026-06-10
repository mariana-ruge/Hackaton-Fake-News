"""[5] Análisis lingüístico — detecta sensacionalismo, sesgo, clickbait y banderas rojas.

Usa el prompt `agent/prompts/linguistic.<lang>.txt`.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from agent.llm_client import generate_json

logger = logging.getLogger(__name__)


class AnalisisLinguistico(TypedDict, total=False):
    alarmismo: float
    sesgo: float
    clickbait: float
    banderas_rojas: list[str]


_VACIO: AnalisisLinguistico = {
    "alarmismo": 0.0,
    "sesgo": 0.0,
    "clickbait": 0.0,
    "banderas_rojas": [],
}


def _clip01(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


async def analizar(texto: str, language: str = "es") -> AnalisisLinguistico:
    if not texto or not texto.strip():
        return dict(_VACIO)  # type: ignore[return-value]

    try:
        data = await generate_json(
            "linguistic",
            language=language,
            variables={"texto": texto},
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[linguistic] fallo Gemini/JSON: %s", exc)
        return dict(_VACIO)  # type: ignore[return-value]

    if not isinstance(data, dict):
        logger.warning("[linguistic] respuesta no es dict: %r", type(data).__name__)
        return dict(_VACIO)  # type: ignore[return-value]

    return {
        "alarmismo": _clip01(data.get("alarmismo", 0.0)),
        "sesgo": _clip01(data.get("sesgo", 0.0)),
        "clickbait": _clip01(data.get("clickbait", 0.0)),
        "banderas_rojas": [str(b) for b in (data.get("banderas_rojas") or [])][:20],
    }
