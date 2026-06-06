"""Helper para llamadas a Gemini con prompts plantilla.

Centraliza la llamada al modelo y el parseo JSON tolerante.
Lo usan las tools `claim_parser`, `linguistic` y `verdict`.

El cliente se obtiene de `agent.genai_client.get_client()` y respeta el modo
seleccionado en `GOOGLE_GENAI_USE_VERTEXAI` (Vertex/ADC o API key).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from google.genai import types as genai_types

from agent.genai_client import get_client, get_config

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str, language: str = "es") -> str:
    """Carga un prompt de `agent/prompts/<name>.<language>.txt`."""
    path = PROMPTS_DIR / f"{name}.{language}.txt"
    if not path.exists():
        # Fallback al español si no hay traducción.
        path = PROMPTS_DIR / f"{name}.es.txt"
    return path.read_text(encoding="utf-8")


def _strip_code_fences(text: str) -> str:
    """Quita ```json ... ``` si el modelo los devuelve."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_tolerant(text: str) -> Any:
    """Intenta parsear JSON aunque el modelo añada texto antes/después."""
    cleaned = _strip_code_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for opener, closer in (("{", "}"), ("[", "]")):
            start = cleaned.find(opener)
            end = cleaned.rfind(closer)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    continue
        raise


async def generate_json(
    prompt_name: str,
    *,
    language: str = "es",
    variables: dict[str, Any] | None = None,
    temperature: float = 0.2,
) -> Any:
    """Renderiza un prompt, lo manda a Gemini y devuelve el JSON parseado."""
    template = load_prompt(prompt_name, language)
    rendered = template.format(**variables) if variables else template

    cfg = get_config()
    client = get_client()
    config = genai_types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
    )

    def _call() -> str:
        resp = client.models.generate_content(
            model=cfg.model_name,
            contents=rendered,
            config=config,
        )
        return resp.text or ""

    raw = await asyncio.to_thread(_call)
    if not raw:
        raise RuntimeError(f"Gemini devolvió respuesta vacía para prompt '{prompt_name}'")
    return _parse_json_tolerant(raw)


async def generate_text(
    prompt: str,
    *,
    temperature: float = 0.3,
) -> str:
    """Llamada simple de texto libre — para pasos sin JSON estructurado."""
    cfg = get_config()
    client = get_client()
    config = genai_types.GenerateContentConfig(temperature=temperature)

    def _call() -> str:
        resp = client.models.generate_content(
            model=cfg.model_name,
            contents=prompt,
            config=config,
        )
        return resp.text or ""

    return await asyncio.to_thread(_call)
