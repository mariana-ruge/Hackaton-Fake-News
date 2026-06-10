"""[3] Source Checker — evalúa la credibilidad de la fuente.

Estrategia:
1. Si la entrada es URL, extrae el dominio.
2. Busca el dominio en la **lista curada** de `agent/data/factcheckers.json`
   (generada por `scripts/seed_factcheckers.py`).
3. Aplica heurísticas adicionales para reportar señales útiles.

No requiere LLM — es determinista y barato.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "factcheckers.json"


class EvaluacionFuente(TypedDict, total=False):
    dominio: str
    credibilidad: float       # 0.0 – 1.0
    categoria: str            # "fact_checker" | "medio_referencia" | "desconocido" | "no_aplica"
    notas: list[str]
    encontrado: bool


_cache: list[dict] | None = None


def _load_curated() -> list[dict]:
    global _cache
    if _cache is not None:
        return _cache
    if not DATA_FILE.exists():
        logger.info(
            "[source_checker] %s no existe — ejecuta scripts/seed_factcheckers.py "
            "para tener evaluación con datos curados.",
            DATA_FILE,
        )
        _cache = []
        return _cache
    try:
        _cache = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return _cache
    except Exception as exc:  # noqa: BLE001
        logger.warning("[source_checker] no se pudo leer %s: %s", DATA_FILE, exc)
        _cache = []
        return _cache


def _extract_domain(text: str) -> str | None:
    """Si `text` es una URL, devuelve el dominio. Si no, intenta detectar dominios sueltos."""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://")):
        try:
            host = urlparse(text).hostname
            if host:
                return host.lower().lstrip("www.")
        except Exception:  # noqa: BLE001
            pass
    # heurística: busca un token con punto y sin espacios.
    for tok in text.split():
        tok = tok.strip(".,;:!?()[]\"'<>").lower()
        if "." in tok and " " not in tok and len(tok) < 64:
            return tok.lstrip("www.")
    return None


def evaluar_fuente(url_o_texto: str) -> EvaluacionFuente:
    """Evalúa la credibilidad del dominio asociado a la entrada."""
    domain = _extract_domain(url_o_texto)
    if not domain:
        return {
            "dominio": "",
            "credibilidad": 0.5,
            "categoria": "no_aplica",
            "notas": ["Sin URL/dominio detectable en la entrada."],
            "encontrado": False,
        }

    curated = _load_curated()
    for entry in curated:
        if domain.endswith(entry["dominio"]):
            return {
                "dominio": domain,
                "credibilidad": float(entry.get("credibilidad", 0.7)),
                "categoria": entry.get("categoria", "medio_referencia"),
                "notas": [
                    f"Coincide con '{entry['nombre']}' "
                    f"(idioma {entry.get('idioma', '?')}).",
                ],
                "encontrado": True,
            }

    notas = []
    if any(s in domain for s in (".tk", ".ml", ".cf", ".ga", ".gq")):
        notas.append("TLD asociado a contenido de baja confianza.")
    if domain.count(".") >= 3:
        notas.append("Dominio con muchos subniveles (posible spoofing).")

    return {
        "dominio": domain,
        "credibilidad": 0.4,
        "categoria": "desconocido",
        "notas": notas or ["Dominio no presente en la lista curada."],
        "encontrado": False,
    }
