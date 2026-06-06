"""Helper para llamadas a Gemini con prompts plantilla.

Centraliza la llamada al modelo (Vertex AI) y el parseo JSON tolerante.
Lo usan las tools `claim_parser`, `linguistic` y `verdict`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from vertexai.generative_models import GenerationConfig, GenerativeModel

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_model: GenerativeModel | None = None


def _get_model() -> GenerativeModel:
    """Lazy-init del modelo. `vertexai.init()` ya se ejecuta en main.py."""
    global _model
    if _model is None:
        _model = GenerativeModel(MODEL_NAME)
    return _model


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
        # Busca el primer { … } o [ … ] balanceado de forma simple.
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
    """Renderiza un prompt, lo manda a Gemini y devuelve el JSON parseado.

    Args:
        prompt_name: nombre del prompt sin extensión (ej. `"verdict"`).
        language:    `"es"` o `"en"`.
        variables:   dict con las variables a sustituir con `str.format`.
        temperature: bajo (0.1-0.3) para tareas estructuradas.
    """
    template = load_prompt(prompt_name, language)
    if variables:
        # Las llaves `{`/`}` que NO son placeholders ya se preservan porque
        # los prompts solo usan `{texto}`, `{claims}`, etc.
        rendered = template.format(**variables)
    else:
        rendered = template

    model = _get_model()
    config = GenerationConfig(
        temperature=temperature,
        response_mime_type="application/json",
    )

    def _call() -> str:
        resp = model.generate_content(rendered, generation_config=config)
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
    model = _get_model()
    config = GenerationConfig(temperature=temperature)

    def _call() -> str:
        resp = model.generate_content(prompt, generation_config=config)
        return resp.text or ""

    return await asyncio.to_thread(_call)
