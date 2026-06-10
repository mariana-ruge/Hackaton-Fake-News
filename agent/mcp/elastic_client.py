"""Cliente Elasticsearch reutilizable para VeritasAgent.

Encapsula:
- conexión (Cloud ID o URL + API key),
- búsqueda híbrida (kNN sobre `claim_embedding` + match sobre `claim_text`),
- indexado de veredictos.

El cliente es **sincrónico** porque `elasticsearch-py` ofrece API estable así
y nuestros endpoints lo invocan a través de `asyncio.to_thread` cuando hace
falta no bloquear el event loop.

Para uso desde el agente vía MCP, ver el `MCPToolset` de Elastic en `main.py`.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError
from elasticsearch.exceptions import NotFoundError

logger = logging.getLogger(__name__)

DEFAULT_INDEX = "verified_claims"
DEFAULT_TTL_DAYS = 30
DEFAULT_TOP_K = 5
EARLY_EXIT_THRESHOLD = float(os.getenv("TRIAGE_EARLY_EXIT_THRESHOLD", "0.92"))
EVIDENCE_THRESHOLD = float(os.getenv("TRIAGE_EVIDENCE_THRESHOLD", "0.75"))


def claim_hash(text: str) -> str:
    """Hash estable del claim para deduplicar (independiente del idioma de variantes triviales)."""
    normalized = " ".join(text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ElasticClient:
    """Wrapper estrecho alrededor de `elasticsearch.Elasticsearch`."""

    def __init__(self, *, url: str | None = None, cloud_id: str | None = None,
                 api_key: str | None = None, index: str | None = None) -> None:
        self.url = url or os.getenv("ELASTIC_URL")
        self.cloud_id = cloud_id or os.getenv("ELASTIC_CLOUD_ID")
        self.api_key = api_key or os.getenv("ELASTIC_API_KEY")
        self.index = index or os.getenv("ELASTIC_INDEX", DEFAULT_INDEX)
        self._es: Elasticsearch | None = None

    # ──────────────────────────────────────────────────────────────────────
    # Conexión
    # ──────────────────────────────────────────────────────────────────────
    def connect(self) -> Elasticsearch:
        if self._es is not None:
            return self._es
        if not self.api_key:
            raise RuntimeError("ELASTIC_API_KEY no está definida.")
        if not (self.url or self.cloud_id):
            raise RuntimeError("Define ELASTIC_URL o ELASTIC_CLOUD_ID.")

        kwargs: dict[str, Any] = {"api_key": self.api_key, "request_timeout": 30}
        if self.cloud_id:
            kwargs["cloud_id"] = self.cloud_id
        else:
            kwargs["hosts"] = [self.url]

        self._es = Elasticsearch(**kwargs)
        if not self._es.ping():
            raise ESConnectionError("ping a Elasticsearch falló")
        return self._es

    def healthy(self) -> bool:
        try:
            return self.connect().ping()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Elastic health check fallido: %s", exc)
            return False

    # ──────────────────────────────────────────────────────────────────────
    # Búsqueda para el triage
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_expired(source: dict[str, Any]) -> bool:
        """True si el doc superó su `ttl_days` desde `verified_at`."""
        verified_at = source.get("verified_at")
        if not verified_at:
            return False
        try:
            ts = datetime.fromisoformat(str(verified_at).replace("Z", "+00:00"))
        except ValueError:
            return False
        ttl = int(source.get("ttl_days") or DEFAULT_TTL_DAYS)
        return (datetime.now(timezone.utc) - ts).days > ttl

    def hybrid_search(
        self,
        claim_text: str,
        claim_embedding: list[float],
        *,
        top_k: int = DEFAULT_TOP_K,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recupera candidatos para el triage.

        ⚠️ Calibración de scores (ver ADR-0007):
        - La DECISIÓN (early-exit/evidence) usa SOLO el score kNN. Con
          `similarity: cosine`, Elasticsearch lo normaliza a [0, 1]
          (`(1 + cos) / 2`), compatible con los umbrales 0.92 / 0.75.
        - El match léxico BM25 NO participa en el umbral — su score no está
          acotado (5, 10, 20+) y dispararía early-exits falsos. Solo se usa
          para traer hits complementarios como evidencia, con `_score: 0.0`.
        - Los docs vencidos por `ttl_days` se descartan (cache con expiración).
        """
        es = self.connect()
        lang_filter = [{"term": {"language": language}}] if language else []

        knn: dict[str, Any] = {
            "field": "claim_embedding",
            "query_vector": claim_embedding,
            "k": top_k,
            "num_candidates": max(50, top_k * 10),
        }
        if lang_filter:
            knn["filter"] = lang_filter

        try:
            knn_resp = es.search(index=self.index, knn=knn, size=top_k)
        except NotFoundError:
            logger.warning("Índice '%s' no existe — ejecuta scripts/setup_elastic_index.py", self.index)
            return []

        hits: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        for h in knn_resp.get("hits", {}).get("hits", []):
            src = h["_source"]
            if self._is_expired(src):
                continue
            hits.append({"_score": h["_score"], **src})
            if src.get("claim_hash"):
                seen_hashes.add(src["claim_hash"])

        # BM25 complementario: solo aporta evidencia, nunca decide el umbral.
        bm25_query: dict[str, Any] = {"match": {"claim_text": claim_text}}
        if lang_filter:
            bm25_query = {"bool": {"must": [bm25_query], "filter": lang_filter}}
        try:
            bm25_resp = es.search(index=self.index, query=bm25_query, size=top_k)
            for h in bm25_resp.get("hits", {}).get("hits", []):
                src = h["_source"]
                if src.get("claim_hash") in seen_hashes or self._is_expired(src):
                    continue
                hits.append({"_score": 0.0, "_bm25_score": h["_score"], **src})
        except NotFoundError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("BM25 complementario falló (no bloqueante): %s", exc)

        return hits

    def triage(
        self,
        claim_text: str,
        claim_embedding: list[float],
        *,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Aplica los umbrales `0.92 / 0.75` y devuelve la acción a tomar.

        Acciones posibles:
            * `"early_exit"`  → usar `cached` (un veredicto previo verificado).
            * `"evidence"`    → usar `hits` como contexto, pero **no** salir.
            * `"fresh"`       → no hay match útil; flujo completo desde cero.
        """
        hits = self.hybrid_search(claim_text, claim_embedding, language=language)
        if not hits:
            return {"action": "fresh", "score": 0.0, "hits": []}

        best = hits[0]
        score = float(best.get("_score", 0.0))
        if score >= EARLY_EXIT_THRESHOLD:
            return {"action": "early_exit", "score": score, "cached": best, "hits": hits}
        if score >= EVIDENCE_THRESHOLD:
            return {"action": "evidence", "score": score, "hits": hits}
        return {"action": "fresh", "score": score, "hits": hits}

    # ──────────────────────────────────────────────────────────────────────
    # Persistencia de veredictos
    # ──────────────────────────────────────────────────────────────────────
    def index_verification(
        self,
        *,
        claim_text: str,
        claim_embedding: list[float],
        verdict_score: int,
        category: str,
        confidence: str,
        reasoning: str,
        evidence: list[dict[str, str]] | None = None,
        language: str = "es",
        source_domain: str | None = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> str:
        """Indexa un veredicto consolidado y devuelve el `_id` del doc."""
        es = self.connect()
        doc_id = claim_hash(claim_text)
        doc = {
            "claim_text": claim_text,
            "claim_embedding": claim_embedding,
            "claim_hash": doc_id,
            "language": language,
            "verdict_score": verdict_score,
            "category": category,
            "confidence": confidence,
            "reasoning": reasoning,
            "evidence": evidence or [],
            "source_domain": source_domain,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "ttl_days": ttl_days,
        }
        es.index(index=self.index, id=doc_id, document=doc, refresh="wait_for")
        return doc_id

    def get_by_hash(self, claim_text: str) -> dict[str, Any] | None:
        es = self.connect()
        try:
            doc = es.get(index=self.index, id=claim_hash(claim_text))
            return doc["_source"]
        except NotFoundError:
            return None


# Singleton accesible desde main.py / tools
_default_client: ElasticClient | None = None


def get_default_client() -> ElasticClient:
    global _default_client
    if _default_client is None:
        _default_client = ElasticClient()
    return _default_client
