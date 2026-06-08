"""
Cliente de Elastic para VeritasAgent.

Implementa la capa [0] Triage (búsqueda semántica/híbrida) y la capa [7]
Persist/Index (memoria de verificaciones) descritas en PLAN.md.

- Búsqueda híbrida: kNN (dense_vector cosine) + BM25 (texto).
- Memoria: cada verificación se reindexa para alimentar triages futuros.
- TTL: las verificaciones caducan según `ttl_days` (default 30).

Si Elastic no está configurado (sin ELASTIC_URL/ELASTIC_CLOUD_ID o sin
ELASTIC_API_KEY) el cliente queda inactivo y `is_configured()` devuelve False,
de modo que el flujo principal del agente sigue funcionando sin Elastic.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

try:
    from elasticsearch import AsyncElasticsearch
    from elasticsearch import exceptions as es_exceptions
    _ELASTIC_AVAILABLE = True
except ImportError:  # pragma: no cover - se maneja en runtime
    AsyncElasticsearch = None  # type: ignore[assignment]
    es_exceptions = None  # type: ignore[assignment]
    _ELASTIC_AVAILABLE = False


DEFAULT_INDEX = os.getenv("ELASTIC_INDEX", "verified_claims")
EMBEDDING_DIMS = int(os.getenv("EMBEDDING_DIMS", "768"))


def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


class ElasticClient:
    """Cliente async sobre Elasticsearch para triage + memoria de claims."""

    def __init__(self) -> None:
        self.index = _env_value("ELASTIC_INDEX", DEFAULT_INDEX) or DEFAULT_INDEX
        self._cloud_id = _env_value("ELASTIC_CLOUD_ID")
        self._url = _env_value("ELASTIC_URL")
        self._api_key = _env_value("ELASTIC_API_KEY")
        self._client: "AsyncElasticsearch | None" = None

    # ------------------------------------------------------------------
    # Configuración / conexión
    # ------------------------------------------------------------------
    def is_configured(self) -> bool:
        """True si hay credenciales suficientes y la librería está instalada."""
        if not _ELASTIC_AVAILABLE:
            return False
        if not self._api_key:
            return False
        return bool(self._cloud_id or self._url)

    def _build_client(self) -> "AsyncElasticsearch":
        kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._cloud_id:
            kwargs["cloud_id"] = self._cloud_id
        else:
            kwargs["hosts"] = [self._url]
        return AsyncElasticsearch(**kwargs)  # type: ignore[misc]

    async def connect(self) -> None:
        if self._client is None and self.is_configured():
            self._client = self._build_client()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def ping(self) -> bool:
        if not self.is_configured():
            return False
        await self.connect()
        try:
            return bool(await self._client.ping())  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # Índice
    # ------------------------------------------------------------------
    def index_mapping(self) -> dict[str, Any]:
        return {
            "mappings": {
                "properties": {
                    "claim_hash": {"type": "keyword"},
                    "claim_text": {"type": "text"},
                    "claim_embedding": {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIMS,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "veredicto": {"type": "keyword"},
                    "analisis": {"type": "text"},
                    "confianza": {"type": "float"},
                    "fuente": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "idioma": {"type": "keyword"},
                    "ttl_days": {"type": "integer"},
                    "verified_at": {"type": "date"},
                }
            }
        }

    async def ensure_index(self) -> bool:
        """Crea el índice si no existe. Devuelve True si está disponible."""
        if not self.is_configured():
            return False
        await self.connect()
        try:
            exists = await self._client.indices.exists(index=self.index)  # type: ignore[union-attr]
            if not exists:
                await self._client.indices.create(  # type: ignore[union-attr]
                    index=self.index, body=self.index_mapping()
                )
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Elastic ensure_index falló: {exc}")
            return False

    # ------------------------------------------------------------------
    # Búsqueda híbrida (triage)
    # ------------------------------------------------------------------
    @staticmethod
    def _is_fresh(doc: dict[str, Any]) -> bool:
        ttl = int(doc.get("ttl_days", 30) or 30)
        verified_at = doc.get("verified_at")
        if not verified_at:
            return True
        try:
            ts = datetime.fromisoformat(str(verified_at).replace("Z", "+00:00"))
        except ValueError:
            return True
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).days <= ttl

    async def hybrid_search(
        self,
        claim_embedding: list[float],
        query_text: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Búsqueda híbrida kNN + BM25. Devuelve docs frescos con `_score`."""
        if not self.is_configured():
            return []
        await self.connect()

        knn = {
            "field": "claim_embedding",
            "query_vector": claim_embedding,
            "k": top_k,
            "num_candidates": max(50, top_k * 10),
        }
        query = {"match": {"claim_text": {"query": query_text}}}

        try:
            response = await self._client.search(  # type: ignore[union-attr]
                index=self.index,
                knn=knn,
                query=query,
                size=top_k,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Elastic hybrid_search falló: {exc}")
            return []

        results: list[dict[str, Any]] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            if not self._is_fresh(source):
                continue
            results.append({**source, "_score": hit.get("_score", 0.0)})
        return results

    async def get_by_hash(self, claim_hash: str) -> dict[str, Any] | None:
        """Recupera una verificación cacheada por hash exacto (si está fresca)."""
        if not self.is_configured():
            return None
        await self.connect()
        try:
            doc = await self._client.get(  # type: ignore[union-attr]
                index=self.index, id=claim_hash
            )
        except Exception:  # noqa: BLE001 - incluye NotFoundError
            return None

        source = doc.get("_source", {})
        if source and self._is_fresh(source):
            return source
        return None

    # ------------------------------------------------------------------
    # Persistencia / memoria (write-back context layer)
    # ------------------------------------------------------------------
    async def index_verification(self, doc: dict[str, Any]) -> bool:
        """Indexa (o reemplaza) una verificación usando `claim_hash` como id."""
        if not self.is_configured():
            return False
        await self.connect()

        payload = dict(doc)
        payload.setdefault("ttl_days", int(os.getenv("CACHE_TTL_DAYS", "30")))
        payload["verified_at"] = datetime.now(timezone.utc).isoformat()
        claim_hash = payload.get("claim_hash")

        try:
            await self._client.index(  # type: ignore[union-attr]
                index=self.index,
                id=claim_hash,
                document=payload,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Elastic index_verification falló: {exc}")
            return False


# Singleton perezoso para reutilizar la conexión en la app.
_elastic_singleton: ElasticClient | None = None


def get_elastic_client() -> ElasticClient:
    global _elastic_singleton
    if _elastic_singleton is None:
        _elastic_singleton = ElasticClient()
    return _elastic_singleton
