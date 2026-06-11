"""Cliente Gemini agnóstico al backend.

Soporta dos modos de autenticación (ambos válidos para Blacklight Expose):

  ┌────────────────────────────┬─────────────────────────────────────────────┐
  │ Modo A · Vertex AI (ADC)   │ Modo B · API key directa (AI Studio)        │
  │ recomendado para org +     │ pensado para jueces / devs que solo quieren │
  │ despliegue (Cloud Run,     │ probarlo rápido sin instalar gcloud.        │
  │ Agent Engine)              │                                             │
  ├────────────────────────────┼─────────────────────────────────────────────┤
  │ GOOGLE_GENAI_USE_VERTEXAI  │ GOOGLE_GENAI_USE_VERTEXAI=False             │
  │   =True                    │ GOOGLE_API_KEY=AIzaSy…                      │
  │ GOOGLE_CLOUD_PROJECT=…     │                                             │
  │ GOOGLE_CLOUD_LOCATION=…    │                                             │
  └────────────────────────────┴─────────────────────────────────────────────┘

La detección es automática: si `USE_VERTEXAI=True` se intenta ADC;
si está en False (o cualquier otro valor), exige `GOOGLE_API_KEY`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

from google import genai

logger = logging.getLogger(__name__)

AuthMode = Literal["vertex_adc", "api_key"]


@dataclass(frozen=True)
class GenAIConfig:
    mode: AuthMode
    model_name: str
    embedding_model: str
    project: str | None = None
    location: str | None = None


_client: genai.Client | None = None
_config: GenAIConfig | None = None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_config() -> GenAIConfig:
    """Devuelve el modo elegido y los nombres de modelo (lazy + cacheado)."""
    global _config
    if _config is not None:
        return _config

    use_vertex = _truthy(os.getenv("GOOGLE_GENAI_USE_VERTEXAI"))
    model_name = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-004")

    if use_vertex:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            raise RuntimeError(
                "GOOGLE_GENAI_USE_VERTEXAI=True pero falta GOOGLE_CLOUD_PROJECT. "
                "Define el ID del proyecto de Google Cloud en .env."
            )
        _config = GenAIConfig(
            mode="vertex_adc",
            model_name=model_name,
            embedding_model=embedding_model,
            project=project,
            location=location,
        )
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_GENAI_USE_VERTEXAI=False requiere GOOGLE_API_KEY. "
                "Pon tu API key de Google AI Studio en .env, o cambia a "
                "GOOGLE_GENAI_USE_VERTEXAI=True para usar ADC."
            )
        _config = GenAIConfig(
            mode="api_key",
            model_name=model_name,
            embedding_model=embedding_model,
        )
    return _config


def get_client() -> genai.Client:
    """Devuelve el `genai.Client` correctamente inicializado (lazy + cacheado)."""
    global _client
    if _client is not None:
        return _client

    cfg = get_config()
    if cfg.mode == "vertex_adc":
        _client = genai.Client(
            vertexai=True,
            project=cfg.project,
            location=cfg.location,
        )
        logger.info("Gemini auth: modo Vertex AI (ADC) · project=%s · location=%s",
                    cfg.project, cfg.location)
    else:
        _client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        logger.info("Gemini auth: modo API key directa (Google AI Studio).")
    return _client


def describe_auth() -> dict[str, str | None]:
    """Resumen de la auth actual para mostrar en `/health`."""
    try:
        cfg = get_config()
    except Exception as exc:  # noqa: BLE001
        return {"auth_mode": "unconfigured", "error": str(exc)}
    return {
        "auth_mode": cfg.mode,
        "model_name": cfg.model_name,
        "embedding_model": cfg.embedding_model,
        "project": cfg.project,
        "location": cfg.location,
    }
