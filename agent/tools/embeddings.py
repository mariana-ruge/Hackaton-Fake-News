"""Async embedding helper usando Vertex AI (text-embedding-004).

La organización bloquea las API keys → autenticamos vía ADC + Vertex AI.
Para correr localmente asegúrate de haber ejecutado:
    gcloud auth application-default login
    gcloud auth application-default set-quota-project <project-id>

Cache LRU en memoria + retry exponencial ante throttling.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from collections import OrderedDict

import numpy as np
from google.api_core import exceptions as gcp_exceptions
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

logger = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
_DIMENSION = 768
_MAX_CACHE = 100
_MAX_RETRIES = 3
_TASK_TYPE = "SEMANTIC_SIMILARITY"

_cache: "OrderedDict[str, list[float]]" = OrderedDict()
_model: TextEmbeddingModel | None = None
_lock = asyncio.Lock()


def _get_model() -> TextEmbeddingModel:
    """Lazy-init del modelo de embeddings de Vertex.

    Vertex AI ya debe estar inicializado (lo hace `main.py` con
    `vertexai.init(project=..., location=...)`).
    """
    global _model
    if _model is None:
        _model = TextEmbeddingModel.from_pretrained(_MODEL_NAME)
    return _model


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
    """Devuelve un embedding de 768 dimensiones L2-normalizado para `text`.

    - Modelo: text-embedding-004 (Vertex AI)
    - Cache LRU en memoria (últimos 100 textos por hash SHA-256)
    - Retry exponencial (2^n s) ante errores de cuota / disponibilidad.
    """
    if not text or not text.strip():
        raise ValueError("`text` no puede estar vacío.")

    key = _hash_text(text)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    model = _get_model()
    inputs = [TextEmbeddingInput(text=text, task_type=_TASK_TYPE)]

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            # `get_embeddings` es síncrono → lo movemos a un thread para
            # no bloquear el event loop.
            response = await asyncio.to_thread(
                model.get_embeddings,
                inputs,
                output_dimensionality=_DIMENSION,
            )
            raw = response[0].values
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
