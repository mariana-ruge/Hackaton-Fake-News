"""
Triage: clasifica la entrada del usuario (URL, texto, captura) y decide la ruta
de procesamiento (extracción web, parseo directo, OCR, etc.).

Además expone `triage_semantico`, la capa [0] del pipeline VeritasAgent:
consulta la memoria de verificaciones en Elastic y decide si podemos resolver
la noticia con un veredicto ya emitido (early-exit) sin volver a invocar al
agente completo.
"""

from __future__ import annotations

import hashlib
import os
import unicodedata
from typing import Any, Literal, TypedDict


class TriageResult(TypedDict):
    tipo: Literal["url", "texto", "imagen", "desconocido"]
    confianza: float
    siguiente_paso: str


def triage(entrada: str) -> TriageResult:
    """Determina el tipo de entrada y el siguiente paso del pipeline."""
    raise NotImplementedError("Implementar lógica de triage")


# ==========================================================================
# Triage semántico (memoria Elastic + early-exit)
# ==========================================================================
EARLY_EXIT_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD_EXIT", "0.92"))
EVIDENCE_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD_EVIDENCE", "0.75"))


class TriageDecision(TypedDict):
    early_exit: bool
    source: Literal["cache_exact", "cache_semantic", "none", "disabled", "error"]
    score: float
    claim_hash: str
    cached_doc: dict[str, Any] | None
    evidencias: list[dict[str, Any]]


def normalizar_claim(texto: str) -> str:
    """Normaliza el texto para hashing estable (minúsculas, sin acentos/espacios extra)."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


def claim_hash(texto: str) -> str:
    return hashlib.sha256(normalizar_claim(texto).encode("utf-8")).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    import numpy as np

    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


async def triage_semantico(texto_noticia: str) -> TriageDecision:
    """Decide si la noticia ya fue verificada (early-exit) usando memoria Elastic.

    Seguridad: el índice solo contiene NUESTRAS verificaciones, así que un acierto
    siempre corresponde a un claim que ya analizamos. Nunca se hace early-exit por
    parecerse a una noticia real no verificada.

    Devuelve siempre una decisión; ante cualquier fallo de Elastic/embeddings hace
    fallback (`early_exit=False`) para que el flujo del agente continúe normal.
    """
    h = claim_hash(texto_noticia)
    decision: TriageDecision = {
        "early_exit": False,
        "source": "none",
        "score": 0.0,
        "claim_hash": h,
        "cached_doc": None,
        "evidencias": [],
    }

    try:
        from agent.mcp.elastic_client import get_elastic_client

        elastic = get_elastic_client()
        if not elastic.is_configured():
            decision["source"] = "disabled"
            return decision

        # 1) Coincidencia exacta por hash (claim idéntico ya verificado).
        exact = await elastic.get_by_hash(h)
        if exact is not None:
            decision.update(
                early_exit=True, source="cache_exact", score=1.0, cached_doc=exact
            )
            return decision

        # 2) Búsqueda semántica/híbrida sobre verificaciones previas.
        from agent.tools.embeddings import get_embedding

        embedding = await get_embedding(texto_noticia)
        hits = await elastic.hybrid_search(embedding, texto_noticia, top_k=5)
        if not hits:
            return decision

        # Similitud coseno pura para decidir el early-exit (independiente de BM25).
        top = hits[0]
        cached_vec = top.get("claim_embedding")
        if cached_vec:
            score = _cosine(embedding, list(cached_vec))
        else:
            # Conversión aproximada del score kNN coseno de Elastic.
            score = max(0.0, min(1.0, 2 * float(top.get("_score", 0.0)) - 1))

        decision["score"] = score
        decision["evidencias"] = [
            h2 for h2 in hits if h2.get("claim_embedding") is None or True
        ][:5]

        if score >= EARLY_EXIT_THRESHOLD:
            decision.update(early_exit=True, source="cache_semantic", cached_doc=top)

        return decision

    except Exception as exc:  # noqa: BLE001 - fallback seguro
        print(f"[WARN] triage_semantico falló, se continúa sin Elastic: {exc}")
        decision["source"] = "error"
        return decision
