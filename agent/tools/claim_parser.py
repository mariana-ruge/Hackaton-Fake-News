"""[2] Claim Parser — descompone un texto en claims atómicos verificables.

Usa el prompt `agent/prompts/claim_parser.<lang>.txt` con Gemini estructurado
(`response_mime_type=application/json`).
"""

from __future__ import annotations

import logging
from typing import TypedDict

from agent.llm_client import generate_json

logger = logging.getLogger(__name__)


class Claim(TypedDict, total=False):
    id: str
    texto: str
    entidades: list[str]
    fecha_referida: str | None


async def parsear_claims(texto: str, language: str = "es") -> list[Claim]:
    """Devuelve la lista de claims atómicos extraídos de `texto`.

    Si Gemini falla o devuelve algo no parseable, devuelve `[]` y logea.
    """
    if not texto or not texto.strip():
        return []

    try:
        data = await generate_json(
            "claim_parser",
            language=language,
            variables={"texto": texto},
            temperature=0.1,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[claim_parser] fallo Gemini/JSON: %s", exc)
        return []

    if not isinstance(data, list):
        logger.warning("[claim_parser] respuesta no es lista: %r", type(data).__name__)
        return []

    # Garantizamos los campos mínimos.
    claims: list[Claim] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        claims.append({
            "id": str(item.get("id") or f"c{i+1}"),
            "texto": str(item.get("texto", "")).strip(),
            "entidades": list(item.get("entidades") or []),
            "fecha_referida": item.get("fecha_referida"),
        })
    return [c for c in claims if c["texto"]]
