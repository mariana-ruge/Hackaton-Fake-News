"""[4] Cross Reference — busca evidencias para cada claim.

Estrategia conservadora (lista para la entrega):
1. Aprovecha los hits del triage [0] si el score era `evidence` (0.75–0.92):
   esos son veredictos previos relacionados que ya tenemos en Elastic.
2. Si no hay nada, devuelve lista vacía y el `verdict` lo marcará como
   `no_verificable`.

Futuro: en producción este paso usaría Bright Data MCP (`search_engine` y
`scrape_as_markdown`) para traer evidencia fresca de medios financieros y
fact-checkers. Lo dejamos como TODO porque requiere pasar el toolset MCP
abierto desde el orquestador.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

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
) -> list[Evidencia]:
    """Devuelve evidencias para el claim, reciclando lo que el triage trajo."""
    evidencias: list[Evidencia] = []

    for hit in (triage_hits or [])[:5]:
        for ev in hit.get("evidence", []) or []:
            evidencias.append({
                "claim_id": claim_id,
                "fuente": ev.get("source", "desconocida"),
                "url": ev.get("url", ""),
                "fragmento": hit.get("reasoning", "")[:240],
                "soporte": ev.get("stance", "contexto"),
            })

    if not evidencias:
        logger.info(
            "[cross_reference] sin evidencias para claim %s (sin hits relevantes en Elastic).",
            claim_id,
        )
    return evidencias
