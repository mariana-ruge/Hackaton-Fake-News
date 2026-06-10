"""[7] Persistencia del veredicto consolidado en Elastic.

Firestore (en `main.py`) sigue guardando el log operativo de cada `/analizar`
y `/scrape`. Esta función indexa la versión semántica del caso — con embedding
del claim — para que futuros triages la encuentren por similitud.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agent.mcp.elastic_client import get_default_client
from agent.tools.embeddings import get_embedding

logger = logging.getLogger(__name__)


async def guardar_veredicto(
    *,
    claim_text: str,
    verdict_score: int,
    category: str,
    confidence: str,
    reasoning: str,
    evidence: list[dict[str, str]] | None = None,
    language: str = "es",
    source_domain: str | None = None,
    ttl_days: int = 30,
) -> str | None:
    """Indexa el veredicto en Elastic y devuelve el `_id` del documento.

    Devuelve `None` si Elastic no está disponible — el caller decide si
    continuar (no es bloqueante para responder al usuario).
    """
    try:
        embedding = await get_embedding(claim_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[persistence] embedding falló: %s — no indexo", exc)
        return None

    client = get_default_client()

    try:
        doc_id = await asyncio.to_thread(
            client.index_verification,
            claim_text=claim_text,
            claim_embedding=embedding,
            verdict_score=verdict_score,
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            evidence=evidence or [],
            language=language,
            source_domain=source_domain,
            ttl_days=ttl_days,
        )
        logger.info("[persistence] veredicto indexado en Elastic: %s", doc_id)
        return doc_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("[persistence] Elastic no disponible: %s", exc)
        return None


async def obtener_veredicto(claim_text: str) -> dict[str, Any] | None:
    """Devuelve el veredicto cacheado para un claim, o `None` si no existe."""
    client = get_default_client()
    try:
        return await asyncio.to_thread(client.get_by_hash, claim_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[persistence] get_by_hash falló: %s", exc)
        return None
