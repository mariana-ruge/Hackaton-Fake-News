"""[0] Triage / Pre-análisis (Elastic) — early-exit semántico.

Para cada claim entrante:
1. Calcula su embedding (Vertex AI text-embedding-004).
2. Busca por similitud híbrida (kNN + BM25) en `verified_claims`.
3. Aplica los umbrales configurados:
     score >= 0.92 → EARLY EXIT   (devuelve el veredicto cacheado)
     0.75 <= s     → EVIDENCE     (usa los hits como contexto, sigue el flujo)
     score <  0.75 → FRESH        (flujo completo desde cero)

Regla de seguridad: el early-exit SOLO aplica contra claims que NOSOTROS ya
verificamos, nunca contra "noticias parecidas a una real" (PLAN.md §3).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, TypedDict

from agent.mcp.elastic_client import (
    EARLY_EXIT_THRESHOLD,
    EVIDENCE_THRESHOLD,
    get_default_client,
)
from agent.tools.embeddings import get_embedding

logger = logging.getLogger(__name__)

Accion = Literal["early_exit", "evidence", "fresh", "error"]


class TriageResult(TypedDict, total=False):
    accion: Accion
    score: float
    cached: dict[str, Any] | None
    hits: list[dict[str, Any]]
    motivo: str


async def triage(claim_text: str, language: str = "es") -> TriageResult:
    """Ejecuta el triage [0] sobre un claim.

    Args:
        claim_text: el texto del claim ya extraído (no la URL).
        language: idioma del claim (`"es"` o `"en"`).

    Returns:
        `TriageResult` con la acción a tomar.
    """
    if not claim_text or not claim_text.strip():
        return {"accion": "error", "score": 0.0, "motivo": "claim vacío", "hits": []}

    try:
        embedding = await get_embedding(claim_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[triage] No se pudo generar embedding: %s", exc)
        return {"accion": "fresh", "score": 0.0, "motivo": f"embedding falló: {exc}", "hits": []}

    client = get_default_client()

    try:
        result = await asyncio.to_thread(
            client.triage,
            claim_text=claim_text,
            claim_embedding=embedding,
            language=language,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[triage] Elastic no disponible: %s — sigo en modo fresh", exc)
        return {"accion": "fresh", "score": 0.0, "motivo": f"elastic falló: {exc}", "hits": []}

    accion: Accion = result["action"]  # type: ignore[assignment]
    score = float(result.get("score", 0.0))

    motivo = {
        "early_exit": f"match cacheado con score {score:.3f} >= {EARLY_EXIT_THRESHOLD}",
        "evidence":   f"hits útiles (score {score:.3f} ∈ [{EVIDENCE_THRESHOLD}, {EARLY_EXIT_THRESHOLD}))",
        "fresh":      f"sin matches relevantes (mejor score {score:.3f})",
    }.get(accion, "")

    return {
        "accion": accion,
        "score": score,
        "cached": result.get("cached"),
        "hits": result.get("hits", []),
        "motivo": motivo,
    }
