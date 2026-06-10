"""[4] Cross Reference — busca evidencias para cada claim.

Dos fuentes de evidencia, en orden:
1. **Hits del triage [0]**: veredictos previos relacionados que ya viven en
   Elastic (score en rango `evidence`). Gratis, sin red.
2. **Búsqueda web vía Bright Data MCP** (`search_engine`): contrasta el claim
   contra la web abierta. Los resultados entran como evidencia `contexto` —
   determinar si confirman o refutan es trabajo del verdict [6], que recibe
   título y dominio de cada resultado.

El pipeline limita cuántos claims disparan búsqueda web (latencia y cuota);
ver `CROSS_REFERENCE_MAX_SEARCHES`.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from agent.mcp import brightdata_client

logger = logging.getLogger(__name__)


class Evidencia(TypedDict, total=False):
    claim_id: str
    fuente: str
    url: str
    fragmento: str
    soporte: str  # "confirma" | "refuta" | "contexto"


async def contrastar(
    claim_id: str,
    claim_texto: str,
    *,
    triage_hits: list[dict[str, Any]] | None = None,
    buscar_web: bool = True,
    max_resultados_web: int = 5,
) -> list[Evidencia]:
    """Devuelve evidencias para el claim (memoria Elastic + web abierta)."""
    evidencias: list[Evidencia] = []

    # 1) Recicla la evidencia de veredictos previos (hits del triage)
    for hit in (triage_hits or [])[:5]:
        for ev in hit.get("evidence", []) or []:
            evidencias.append({
                "claim_id": claim_id,
                "fuente": ev.get("source", "desconocida"),
                "url": ev.get("url", ""),
                "fragmento": hit.get("reasoning", "")[:240],
                "soporte": ev.get("stance", "contexto"),
            })

    # 2) Búsqueda web real (Bright Data MCP)
    if buscar_web and brightdata_client.is_configured():
        try:
            resultados = await brightdata_client.search_web(claim_texto)
            for r in resultados[:max_resultados_web]:
                evidencias.append({
                    "claim_id": claim_id,
                    "fuente": r["dominio"],
                    "url": r["url"],
                    "fragmento": r["titulo"][:240],
                    "soporte": "contexto",
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[cross_reference] búsqueda web falló para claim %s: %s", claim_id, exc
            )
    elif buscar_web:
        logger.info(
            "[cross_reference] sin BRIGHTDATA_API_TOKEN — claim %s solo con memoria local.",
            claim_id,
        )

    if not evidencias:
        logger.info("[cross_reference] sin evidencias para claim %s.", claim_id)
    return evidencias
