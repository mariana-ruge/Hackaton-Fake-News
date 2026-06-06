"""Async embedding helper using Google Generative AI (text-embedding-004)."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import OrderedDict

import numpy as np
import google.generativeai as genai
from google.api_core import exceptions as gcp_exceptions


_MODEL = "models/text-embedding-004"
_DIMENSION = 768
_MAX_CACHE = 100
_MAX_RETRIES = 3

_cache: "OrderedDict[str, list[float]]" = OrderedDict()
_configured = False
_lock = asyncio.Lock()


def _configure() -> None:
    """Configure the genai SDK with the API key from the environment."""
    global _configured
    if _configured:
        return
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY no está definida en el entorno.")
    genai.configure(api_key=api_key)
    _configured = True


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

    _configure()

    key = _hash_text(text)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            # google-generativeai's embed_content es síncrono; lo movemos
            # a un thread para no bloquear el event loop.
            response = await asyncio.to_thread(
                genai.embed_content,
                model=_MODEL,
                content=text,
                output_dimensionality=_DIMENSION,
            )
            raw = response["embedding"] if isinstance(response, dict) else response.embedding
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
