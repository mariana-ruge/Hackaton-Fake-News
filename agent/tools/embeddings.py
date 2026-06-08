"""Async embedding helper usando Vertex AI (text-embedding-004) vía google-genai.

El proyecto se autentica con Application Default Credentials (ADC) sobre Vertex
AI, así que NO usamos API key. Mantiene la API pública `get_embedding`.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import OrderedDict

import numpy as np
from google.api_core import exceptions as gcp_exceptions


_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
_DIMENSION = int(os.getenv("EMBEDDING_DIMS", "768"))
_MAX_CACHE = 100
_MAX_RETRIES = 3

_cache: "OrderedDict[str, list[float]]" = OrderedDict()
_client = None
_lock = asyncio.Lock()


def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


def _get_client():
    """Crea (una vez) el cliente google-genai apuntando a Vertex AI con ADC."""
    global _client
    if _client is not None:
        return _client

    from google import genai

    project = _env_value("PROJECT_ID") or _env_value("GOOGLE_CLOUD_PROJECT")
    location = _env_value("VERTEX_LOCATION") or _env_value(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )

    _client = genai.Client(vertexai=True, project=project, location=location)
    return _client


def _embed_sync(text: str) -> list[float]:
    """Llamada síncrona a Vertex AI embeddings (se ejecuta en un thread)."""
    from google.genai import types as genai_types

    client = _get_client()
    response = client.models.embed_content(
        model=_MODEL,
        contents=text,
        config=genai_types.EmbedContentConfig(output_dimensionality=_DIMENSION),
    )
    return list(response.embeddings[0].values)


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


async def get_embedding(text: str) -> list[float]:
    """Return a 768-dim L2-normalized embedding for `text`.

    - Modelo: text-embedding-004
    - Cache LRU en memoria (últimos 100 textos por hash SHA-256)
    - Retry exponencial (2^n s) en errores de cuota/recursos
    """
    if not text or not text.strip():
        raise ValueError("`text` no puede estar vacío.")

    key = _hash_text(text)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            # embed_content es síncrono; lo movemos a un thread para no
            # bloquear el event loop.
            raw = await asyncio.to_thread(_embed_sync, text)
            vector = _normalize(list(raw))

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

    raise RuntimeError(
        f"No se pudo obtener embedding tras {_MAX_RETRIES} intentos: {last_exc}"
    ) from last_exc
