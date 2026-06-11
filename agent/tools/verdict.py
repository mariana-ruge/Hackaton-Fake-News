"""[6] Verdict — consolida claims, evidencias, fuente y lingüístico en un veredicto.

Usa el prompt `agent/prompts/verdict.<lang>.txt`.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import Any, Literal, TypedDict

from agent.llm_client import generate_json

logger = logging.getLogger(__name__)

Etiqueta = Literal["verdadero", "engañoso", "falso", "no_verificable"]
VALID_ETIQUETAS = {"verdadero", "engañoso", "falso", "no_verificable"}


class Veredicto(TypedDict, total=False):
    etiqueta: Etiqueta
    confianza: float
    resumen: str
    evidencias_clave: list[str]
    nota_neutralidad: str | None


_FALLBACK: Veredicto = {
    "etiqueta": "no_verificable",
    "confianza": 0.3,
    "resumen": "No hubo evidencia suficiente para emitir un veredicto.",
    "evidencias_clave": [],
    "nota_neutralidad": None,
}


def _clip01(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, x))


def _parse_iso_date(value: Any) -> dt.date | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def _build_temporal_context(claims: list[dict[str, Any]]) -> dict[str, Any]:
    today = dt.date.today()
    parsed: list[dt.date] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        d = _parse_iso_date(c.get("fecha_referida"))
        if d is not None:
            parsed.append(d)

    past_count = sum(1 for d in parsed if d < today)
    future_count = sum(1 for d in parsed if d > today)
    present_count = sum(1 for d in parsed if d == today)

    return {
        "fecha_actual": today.isoformat(),
        "fechas_detectadas": [d.isoformat() for d in sorted(set(parsed))],
        "claims_pasado": past_count,
        "claims_presente": present_count,
        "claims_futuro": future_count,
    }


async def emitir_veredicto(
    claims: list[dict[str, Any]],
    evidencias: list[dict[str, Any]],
    fuente: dict[str, Any],
    linguistico: dict[str, Any],
    *,
    language: str = "es",
) -> Veredicto:
    """Llama a Gemini con todo el contexto y devuelve el veredicto estructurado."""
    temporal = _build_temporal_context(claims)
    try:
        data = await generate_json(
            "verdict",
            language=language,
            variables={
                "claims": json.dumps(claims, ensure_ascii=False),
                "evidencias": json.dumps(evidencias, ensure_ascii=False),
                "fuente": json.dumps(fuente, ensure_ascii=False),
                "linguistico": json.dumps(linguistico, ensure_ascii=False),
                "fecha_actual": temporal["fecha_actual"],
                "contexto_temporal": json.dumps(temporal, ensure_ascii=False),
            },
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[verdict] fallo Gemini/JSON: %s", exc)
        return dict(_FALLBACK)  # type: ignore[return-value]

    if not isinstance(data, dict):
        logger.warning("[verdict] respuesta no es dict: %r", type(data).__name__)
        return dict(_FALLBACK)  # type: ignore[return-value]

    etiqueta = str(data.get("etiqueta", "no_verificable")).lower()
    if etiqueta not in VALID_ETIQUETAS:
        etiqueta = "no_verificable"

    confianza = _clip01(data.get("confianza", 0.3))
    if etiqueta == "no_verificable":
        # Evita presentar "sin evidencia" con una seguridad engañosamente alta.
        confianza = min(confianza, 0.45)

    resumen = str(data.get("resumen", "")).strip() or _FALLBACK["resumen"]
    if (
        temporal["claims_futuro"] == 0
        and temporal["claims_pasado"] > 0
        and re.search(r"\bfutur[oa]s?\b", resumen, flags=re.IGNORECASE)
    ):
        resumen = (
            f"Las fechas mencionadas corresponden al pasado respecto a {temporal['fecha_actual']}. "
            + resumen
        )

    return {
        "etiqueta": etiqueta,  # type: ignore[typeddict-item]
        "confianza": confianza,
        "resumen": resumen,
        "evidencias_clave": [str(e) for e in (data.get("evidencias_clave") or [])][:10],
        "nota_neutralidad": data.get("nota_neutralidad"),
    }


# Mapping de etiqueta interna → categoría externa (la que persistimos en Elastic)
ETIQUETA_A_CATEGORIA: dict[str, str] = {
    "verdadero": "Verdadero",
    "engañoso": "Engañoso",
    "falso": "Falso",
    "no_verificable": "Sin evidencia suficiente",
}


def confianza_a_nivel(conf: float) -> str:
    if conf >= 0.75:
        return "alta"
    if conf >= 0.45:
        return "media"
    return "baja"
