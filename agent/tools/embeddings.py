"""Embeddings agnósticos al backend (Vertex ADC o API key).

Usa el cliente unificado de `agent.genai_client` para que el mismo código
funcione tanto con `GOOGLE_GENAI_USE_VERTEXAI=True` (ADC) como con
`GOOGLE_API_KEY` (API directa de Google AI Studio).

Cache LRU en memoria + retry exponencial ante throttling.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import OrderedDict

import numpy as np
from google.api_core import exceptions as gcp_exceptions
from google.genai import types as genai_types

from agent.genai_client import get_client, get_config

logger = logging.getLogger(__name__)

_DIMENSION = 768
_MAX_CACHE = 100
_MAX_RETRIES = 3
_TASK_TYPE = "SEMANTIC_SIMILARITY"

_cache: "OrderedDict[str, list[float]]" = OrderedDict()
_lock = asyncio.Lock()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> list[float] | None:
    vec = _cache.get(key)
    if vec is not None:
        _cache.move_to_end(key)
    return vec


def _cache_put(key: str, vec: list[float]) -> None:
    _cache[key] = vec
    _cache.move_to_end(key)
    while len(_cache) > _MAX_CACHE:
        _cache.popitem(last=False)


def _normalize(vec: list[float]) -> list[float]:
    arr = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr.tolist()
    return (arr / norm).tolist()


def _resolve_model(name: str) -> str:
    """Vertex AI espera el nombre tal cual; AI Studio acepta con/sin `models/`."""
    if name.startswith("models/"):
        return name
    return name  # google-genai normaliza internamente


async def get_embedding(text: str) -> list[float]:
    """Devuelve un embedding de 768 dimensiones L2-normalizado para `text`.

    - Modelo configurable vía `EMBEDDING_MODEL` (por defecto `text-embedding-004`).
    - Cache LRU en memoria (últimos 100 textos por hash SHA-256).
    - Retry exponencial (2^n s) ante errores de cuota / disponibilidad.
    """
    if not text or not text.strip():
        raise ValueError("`text` no puede estar vacío.")

    key = _hash_text(text)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    cfg = get_config()
    client = get_client()
    model_name = _resolve_model(cfg.embedding_model)

    # `task_type` solo aplica a la API pública; en Vertex se ignora con buen comportamiento.
    embed_config = genai_types.EmbedContentConfig(
        output_dimensionality=_DIMENSION,
        task_type=_TASK_TYPE,
    )

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            def _call():
                return client.models.embed_content(
                    model=model_name,
                    contents=text,
                    config=embed_config,
                )

            response = await asyncio.to_thread(_call)
            # `response.embeddings` es lista[ContentEmbedding] con `.values`
            embeddings = getattr(response, "embeddings", None) or []
            if not embeddings:
                raise RuntimeError("respuesta sin embeddings")
            raw = list(embeddings[0].values)
            vector = _normalize(raw)

            async with _lock:
                _cache_put(key, vector)
            return vector

        except (
            gcp_exceptions.ResourceExhausted,
            gcp_exceptions.TooManyRequests,
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.DeadlineExceeded,
        ) as exc:
            last_exc = exc
            if attempt == _MAX_RETRIES - 1:
                break
            await asyncio.sleep(2 ** attempt)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            break

    raise RuntimeError(
        f"No se pudo obtener embedding tras {_MAX_RETRIES} intentos: {last_exc}"
    ) from last_exc
