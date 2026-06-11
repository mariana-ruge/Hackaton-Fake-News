"""Orquestador determinista del flujo multi-paso de VeritasAgent.

  [0] Triage      (Elastic MCP)                 →  early-exit si score >= 0.92
  [1] Extractor   (texto o URL → contenido)
  [2] Claim Parser (Gemini)                     →  lista de claims atómicos
  [3] Source Checker (lista curada)
  [4] Cross-Reference (Elastic + futuro Bright Data MCP)
  [5] Linguistic   (Gemini)
  [6] Verdict      (Gemini)                     →  veredicto estructurado
  [7] Persist      (Firestore log + Elastic memoria semántica)

Cada paso es opcional y degrada con elegancia si una dependencia falla.
"""

from __future__ import annotations

import logging
import os
from typing import Any, TypedDict

from agent.tools.claim_parser import parsear_claims
from agent.tools.cross_reference import contrastar
from agent.tools.extractor import extraer
from agent.tools.linguistic import analizar as analizar_linguistico
from agent.tools.persistence import guardar_veredicto
from agent.tools.source_checker import evaluar_fuente
from agent.tools.triage import triage as triage_claim
from agent.tools.verdict import (
    ETIQUETA_A_CATEGORIA,
    confianza_a_nivel,
    emitir_veredicto,
)
from agent.tools.vision import extraer_de_imagen

logger = logging.getLogger(__name__)


class PipelineResult(TypedDict, total=False):
    etiqueta: str
    confianza: float
    confianza_nivel: str
    resumen: str
    evidencias_clave: list[str]
    nota_neutralidad: str | None
    triage: dict[str, Any]
    fuente: dict[str, Any]
    linguistico: dict[str, Any]
    claims: list[dict[str, Any]]
    elastic_doc_id: str | None
    pasos_ejecutados: list[str]
    cacheado: bool
    vision: dict[str, Any] | None


async def ejecutar_pipeline(
    entrada: str,
    language: str = "es",
    *,
    imagen: bytes | None = None,
    imagen_mime: str | None = None,
) -> PipelineResult:
    """Ejecuta el flujo multi-paso completo y devuelve un resultado estructurado.

    Si llega `imagen` (captura de pantalla), un paso previo [V] la transcribe
    con Gemini Vision y el claim extraído alimenta el pipeline normal.
    """
    pasos: list[str] = []
    vision_info: dict[str, Any] | None = None
    entrada_efectiva = (entrada or "").strip()

    # ── [V] Visión (solo si llega imagen) ─────────────────────────────────
    if imagen:
        try:
            vision_info = dict(await extraer_de_imagen(imagen, imagen_mime or ""))
            extraido = (
                vision_info.get("claim_principal")
                or vision_info.get("texto_extraido")
                or ""
            )
            if extraido:
                entrada_efectiva = (
                    f"{entrada_efectiva}\n\n[Texto extraído de la imagen]: {extraido}"
                    if entrada_efectiva
                    else extraido
                )
            pasos.append(
                f"[V] visión ({len(vision_info.get('senales_visuales', []))} señales visuales)"
            )
        except ValueError:
            # Input inválido del usuario (mime/tamaño) → el endpoint lo vuelve 400.
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("[pipeline] visión falló: %s — sigo solo con el texto", exc)
            pasos.append("[V] visión (falló — se continúa solo con texto)")

    if not entrada_efectiva:
        return {
            "etiqueta": "Sin evidencia suficiente",
            "confianza": 0.0,
            "confianza_nivel": "baja",
            "resumen": (
                "La imagen no contiene texto legible ni una afirmación verificable, "
                "y no se proporcionó texto adicional."
            ),
            "evidencias_clave": [],
            "nota_neutralidad": None,
            "triage": {"accion": "skipped", "score": 0.0},
            "fuente": {},
            "linguistico": {},
            "claims": [],
            "elastic_doc_id": None,
            "pasos_ejecutados": pasos,
            "cacheado": False,
            "vision": vision_info,
        }

    # ── [0] Triage ────────────────────────────────────────────────────────
    triage_info = await triage_claim(entrada_efectiva, language=language)
    pasos.append("[0] triage")

    # Early exit por caché propia
    if triage_info.get("accion") == "early_exit" and triage_info.get("cached"):
        cached = triage_info["cached"]
        logger.info("[pipeline] EARLY EXIT con score %.3f", triage_info["score"])
        return {
            "etiqueta": cached.get("category", "no_verificable"),
            "confianza": float(cached.get("verdict_score", 0)) / 100.0
                          if isinstance(cached.get("verdict_score"), (int, float)) else 0.5,
            "confianza_nivel": cached.get("confidence", "media"),
            "resumen": cached.get("reasoning", ""),
            "evidencias_clave": [ev.get("url", "") for ev in cached.get("evidence", [])][:10],
            "nota_neutralidad": None,
            "triage": triage_info,
            "fuente": {},
            "linguistico": {},
            "claims": [],
            "elastic_doc_id": cached.get("claim_hash"),
            "pasos_ejecutados": pasos,
            "cacheado": True,
            "vision": vision_info,
        }

    # ── [1] Extractor ─────────────────────────────────────────────────────
    noticia = await extraer(entrada_efectiva)
    pasos.append("[1] extractor")
    texto = noticia.get("cuerpo") or entrada_efectiva
    dominio = noticia.get("dominio")

    # ── [2] Claim Parser ──────────────────────────────────────────────────
    claims = await parsear_claims(texto, language=language)
    pasos.append(f"[2] claim_parser ({len(claims)} claims)")

    # ── [3] Source Checker ────────────────────────────────────────────────
    fuente = evaluar_fuente(noticia.get("url") or entrada_efectiva)
    pasos.append("[3] source_checker")

    # ── [4] Cross-Reference ───────────────────────────────────────────────
    # La búsqueda web (Bright Data MCP) se limita a los primeros N claims:
    # cada búsqueda arranca una sesión MCP (~segundos) y consume cuota.
    max_busquedas = int(os.getenv("CROSS_REFERENCE_MAX_SEARCHES", "3"))
    triage_hits = triage_info.get("hits") or []
    evidencias: list[dict[str, Any]] = []
    for i, c in enumerate(claims or [{"id": "c1", "texto": texto}]):
        ev = await contrastar(
            c["id"], c["texto"],
            triage_hits=triage_hits,
            buscar_web=(i < max_busquedas),
        )
        evidencias.extend(ev)
    pasos.append(f"[4] cross_reference ({len(evidencias)} evidencias)")

    # ── [5] Análisis lingüístico ──────────────────────────────────────────
    linguistico = await analizar_linguistico(texto, language=language)
    # Las señales visuales de la captura cuentan como banderas rojas extra.
    if vision_info and vision_info.get("senales_visuales"):
        linguistico["banderas_rojas"] = [
            f"visual: {s}" for s in vision_info["senales_visuales"]
        ] + list(linguistico.get("banderas_rojas", []))
    pasos.append("[5] linguistic")

    # ── [6] Verdict ───────────────────────────────────────────────────────
    veredicto = await emitir_veredicto(
        claims=list(claims),
        evidencias=evidencias,
        fuente=dict(fuente),
        linguistico=dict(linguistico),
        language=language,
    )
    pasos.append("[6] verdict")

    # ── [7] Persistencia en Elastic ───────────────────────────────────────
    confianza = float(veredicto.get("confianza", 0.3))
    nivel = confianza_a_nivel(confianza)
    categoria = ETIQUETA_A_CATEGORIA.get(veredicto.get("etiqueta", "no_verificable"),
                                          "Sin evidencia suficiente")
    elastic_doc_id = await guardar_veredicto(
        claim_text=texto,
        verdict_score=int(round(confianza * 100)),
        category=categoria,
        confidence=nivel,
        reasoning=veredicto.get("resumen", ""),
        evidence=[{
            "source": ev.get("fuente", ""),
            "url": ev.get("url", ""),
            "stance": ev.get("soporte", "contexto"),
        } for ev in evidencias],
        language=language,
        source_domain=dominio,
    )
    pasos.append("[7] persistence")

    return {
        "etiqueta": categoria,
        "confianza": confianza,
        "confianza_nivel": nivel,
        "resumen": veredicto.get("resumen", ""),
        "evidencias_clave": list(veredicto.get("evidencias_clave", [])),
        "nota_neutralidad": veredicto.get("nota_neutralidad"),
        "triage": triage_info,
        "fuente": dict(fuente),
        "linguistico": dict(linguistico),
        "claims": list(claims),
        "elastic_doc_id": elastic_doc_id,
        "pasos_ejecutados": pasos,
        "cacheado": False,
        "vision": vision_info,
    }
