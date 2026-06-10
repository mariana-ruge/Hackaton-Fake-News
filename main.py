"""
VeritasAgent — API del agente verificador de noticias financieras.

Track partner del reto: 🟢 Elastic MCP
MCPs adicionales:        Bright Data MCP (scraping/búsqueda)
Telemetría:              Arize Phoenix vía OpenTelemetry

Arranca con:
    uvicorn main:app --host 0.0.0.0 --port 8000

Variables de entorno requeridas (ver .env.example):
    # Auth Gemini — elige UNO de los dos modos:
    #  A) Vertex AI / ADC (recomendado para org y producción):
    #       GOOGLE_GENAI_USE_VERTEXAI=True
    #       GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION
    #  B) API key directa (fácil para devs/jueces locales):
    #       GOOGLE_GENAI_USE_VERTEXAI=False
    #       GOOGLE_API_KEY
    MODEL_NAME, EMBEDDING_MODEL
    ELASTIC_URL (o ELASTIC_CLOUD_ID), ELASTIC_API_KEY, ELASTIC_INDEX,
    BRIGHTDATA_API_TOKEN,
    API_KEY_PHOENIX (recomendada para telemetría + bonus MCP)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv(override=True)  # carga el .env (sus valores tienen prioridad)

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("veritas")
logging.getLogger("asyncio").setLevel(logging.ERROR)


def _silence_genai_aclose(loop, context):
    """Silencia el AttributeError cosmético de google-genai al cerrar clientes."""
    exc = context.get("exception")
    if isinstance(exc, AttributeError) and "_async_httpx_client" in str(exc):
        return
    loop.default_exception_handler(context)


try:
    asyncio.get_event_loop().set_exception_handler(_silence_genai_aclose)
except RuntimeError:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# Telemetría (Arize Phoenix)
# ──────────────────────────────────────────────────────────────────────────────
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

# ──────────────────────────────────────────────────────────────────────────────
# Google ADK
# ──────────────────────────────────────────────────────────────────────────────
from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool, url_context
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from google.genai import types as genai_types
from mcp import StdioServerParameters

# ──────────────────────────────────────────────────────────────────────────────
# Configuración: dos modos de autenticación soportados.
#   Modo A · Vertex AI (ADC)  → GOOGLE_GENAI_USE_VERTEXAI=True + ADC
#   Modo B · API key directa  → GOOGLE_GENAI_USE_VERTEXAI=False + GOOGLE_API_KEY
# ──────────────────────────────────────────────────────────────────────────────
from agent.genai_client import describe_auth, get_config as _get_genai_config

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

# Forzamos la lectura del modo ahora para detectar errores temprano.
_genai_cfg = _get_genai_config()
USE_VERTEXAI = (_genai_cfg.mode == "vertex_adc")

# Para compatibilidad con código que lee estas env vars directamente:
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True" if USE_VERTEXAI else "False"
if USE_VERTEXAI:
    os.environ["GOOGLE_CLOUD_PROJECT"] = GOOGLE_CLOUD_PROJECT or ""
    os.environ["GOOGLE_CLOUD_LOCATION"] = GOOGLE_CLOUD_LOCATION

# ──────────────────────────────────────────────────────────────────────────────
# Inicialización de Vertex AI (solo si el modo elegido es ADC)
# ──────────────────────────────────────────────────────────────────────────────
VERTEX_AI_CONNECTED = False

if USE_VERTEXAI:
    import vertexai
    from google.cloud import aiplatform

    vertexai.init(project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION)

    try:
        model_service_client = aiplatform.gapic.ModelServiceClient(
            client_options={"api_endpoint": f"{GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com"}
        )
        parent = f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{GOOGLE_CLOUD_LOCATION}"
        next(iter(model_service_client.list_models(parent=parent)), None)
        VERTEX_AI_CONNECTED = True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Vertex AI ADC no disponible o sin permisos. Proyecto=%s, región=%s. Error: %s",
            GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, exc,
        )
else:
    logger.info(
        "Modo API key directa. Vertex AI Agent Engine NO podrá usarse hasta cambiar a "
        "GOOGLE_GENAI_USE_VERTEXAI=True. Cloud Run y todo lo local funciona igual."
    )

# ──────────────────────────────────────────────────────────────────────────────
# MCP toolsets
#   🟢 Elastic MCP    — track partner del reto: triage + memoria semántica.
#   Bright Data MCP   — scraping + búsqueda web (sustituye Brave + Fetch + scraper.py).
# ──────────────────────────────────────────────────────────────────────────────
from google.cloud import firestore
from google.api_core import exceptions as gcp_exceptions

# --- Elastic MCP (track del reto) ---
ELASTIC_URL = os.getenv("ELASTIC_URL")
ELASTIC_CLOUD_ID = os.getenv("ELASTIC_CLOUD_ID")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "verified_claims")

if ELASTIC_API_KEY and (ELASTIC_URL or ELASTIC_CLOUD_ID):
    elastic_env = {
        **os.environ,
        "ES_API_KEY": ELASTIC_API_KEY,
        "ES_URL": ELASTIC_URL or "",
        "ES_CLOUD_ID": ELASTIC_CLOUD_ID or "",
    }
    elastic_toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@elastic/mcp-server-elasticsearch"],
                env=elastic_env,
            ),
            timeout=60.0,
        )
    )
else:
    logger.warning(
        "Elastic MCP desactivado: faltan ELASTIC_API_KEY y/o ELASTIC_URL/ELASTIC_CLOUD_ID."
    )
    elastic_toolset = None

# --- Bright Data MCP ---
BRIGHTDATA_API_TOKEN = os.getenv("BRIGHTDATA_API_TOKEN")
BRIGHTDATA_WEB_UNLOCKER_ZONE = os.getenv("BRIGHTDATA_WEB_UNLOCKER_ZONE", "mcp_unlocker")

if BRIGHTDATA_API_TOKEN:
    brightdata_env = {
        **os.environ,
        "API_TOKEN": BRIGHTDATA_API_TOKEN,
        "WEB_UNLOCKER_ZONE": BRIGHTDATA_WEB_UNLOCKER_ZONE,
    }
    brightdata_toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@brightdata/mcp"],
                env=brightdata_env,
            ),
            timeout=60.0,
        )
    )
else:
    logger.warning("BRIGHTDATA_API_TOKEN no definido. Bright Data MCP quedará desactivado.")
    brightdata_toolset = None

# ──────────────────────────────────────────────────────────────────────────────
# Arize Phoenix — UNA sola configuración cubre dos roles:
#   1. Telemetría OpenTelemetry: GoogleADKInstrumentor envía trazas a Phoenix.
#   2. Phoenix MCP (bonus partner): el agente consulta datasets/trazas vía MCP.
# Ambos comparten `API_KEY_PHOENIX`. Si falta la clave, los dos quedan
# desactivados limpiamente — el resto del agente sigue funcionando.
# ──────────────────────────────────────────────────────────────────────────────
PHOENIX_API_KEY = os.getenv("API_KEY_PHOENIX")
PHOENIX_BASE_URL = os.getenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com")
PHOENIX_ENABLED = bool(PHOENIX_API_KEY)

# --- 1. Telemetría OpenTelemetry → Phoenix ---
if PHOENIX_ENABLED:
    os.environ["PHOENIX_CLIENT_HEADERS"] = f"api_key={PHOENIX_API_KEY}"
    os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = f"{PHOENIX_BASE_URL.rstrip('/')}/v1/traces"

    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"]))
    )
    trace.set_tracer_provider(tracer_provider)
    GoogleADKInstrumentor().instrument()
else:
    logger.warning("API_KEY_PHOENIX no definida. Telemetría OTel desactivada.")

# --- 2. Phoenix MCP (bonus partner) ---
# Servidor oficial: @arizeai/phoenix-mcp (npx). Permite al agente consultar
# datasets curados (ej. ejemplos de fraudes financieros) y trazas pasadas.
if PHOENIX_ENABLED:
    phoenix_env = {
        **os.environ,
        "PHOENIX_API_KEY": PHOENIX_API_KEY,
        "PHOENIX_BASE_URL": PHOENIX_BASE_URL,
    }
    phoenix_toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@arizeai/phoenix-mcp"],
                env=phoenix_env,
            ),
            timeout=60.0,
        )
    )
else:
    logger.info("Phoenix MCP desactivado (sin API_KEY_PHOENIX).")
    phoenix_toolset = None


# ──────────────────────────────────────────────────────────────────────────────
# Firestore (persistencia de análisis y scrapes)
# ──────────────────────────────────────────────────────────────────────────────
FIRESTORE_COLLECTION_ANALISIS = os.getenv("FIRESTORE_COLLECTION_ANALISIS", "analisis_noticias")
FIRESTORE_COLLECTION_SCRAPES = os.getenv("FIRESTORE_COLLECTION_SCRAPES", "verificaciones")

# Firestore necesita un project ID válido; si no hay (modo API key sin GCP),
# queda desactivado limpiamente y los endpoints siguen funcionando.
db = None
if GOOGLE_CLOUD_PROJECT:
    try:
        db = firestore.Client(project=GOOGLE_CLOUD_PROJECT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo inicializar Firestore: %s", exc)
else:
    logger.info(
        "Firestore desactivado: no hay GOOGLE_CLOUD_PROJECT. Los endpoints funcionan "
        "pero no se guardará historial."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Definición de agentes (Google ADK)
# ──────────────────────────────────────────────────────────────────────────────
verificar_fake_news_google_search_agent = LlmAgent(
    name='Verificar_Fake_News_google_search_agent',
    model=MODEL_NAME,
    description='Agent specialized in performing Google searches.',
    sub_agents=[],
    instruction='Use the GoogleSearchTool to find information on the web.',
    tools=[GoogleSearchTool()],
)

verificar_fake_news_url_context_agent = LlmAgent(
    name='Verificar_Fake_News_url_context_agent',
    model=MODEL_NAME,
    description='Agent specialized in fetching content from URLs.',
    sub_agents=[],
    instruction='Use the UrlContextTool to retrieve content from provided URLs.',
    tools=[url_context],
)

# System Prompt final consolidado y optimizado
prompt_principal = """Eres un analista de medios financieros avanzado, verificador de hechos neutral y experto en prevención de fraudes. Tu objetivo es combatir la desinformación económica, el alarmismo financiero y proteger a los usuarios de esquemas Ponzi, estafas piramidales y "pseudo-traders" en redes sociales. Deconstruyes narrativas de inversión y analizas la polarización económica, explicando la información de forma accesible, estructurada y amigable.

Misión y Flujo de Trabajo:
Cuando el usuario te presente un titular económico, una promesa de inversión, un enlace sospechoso o una alerta de la bolsa, debes realizar estrictamente los siguientes pasos:

1. Búsqueda Multilateral y Verificación de Fuentes: Utiliza tus herramientas de búsqueda para rastrear la noticia o la oportunidad de inversión en al menos 3 medios financieros confiables y regulados (ej. Reuters, Bloomberg, prensa económica local). Si la información proviene de una red social, evalúa la credibilidad de la página o perfil. Sugiere al usuario rectificar si la fuente no tiene historial de rigor periodístico o financiero.
2. Línea de Tiempo del Mercado / Noticia: Reconstruye la evolución de la noticia o tendencia. Muestra cronológicamente cuándo surgió el rumor o dato, cómo reaccionaron los titulares financieros y qué hechos confirmaron o desmintieron la narrativa con el paso de los días.
3. Detección de Fraude y "Pseudo-traders": Analiza la promesa de inversión en busca de banderas rojas (red flags) típicas de esquemas Ponzi o pirámides. Evalúa si el texto incluye: Promesas de rentabilidad inusualmente altas o "garantizadas" sin riesgo, sentido de urgencia extrema o FOMO, enfoque en reclutar a otras personas, o uso de lenguaje ostentoso.
4. Análisis de Incertidumbre y Riesgo: Identifica el lenguaje alarmista. Proporciona una "Métrica de Incertidumbre/Riesgo" (Alta, Media, Baja) basada en la falta de consenso entre analistas serios, la volatilidad real del activo o la presencia de indicadores de estafa.
5. Aclaración Geopolítica Obligatoria: Si la noticia económica involucra políticas de Estado, sanciones, líderes políticos o gobiernos, DEBES incluir textualmente la siguiente advertencia al final de tu análisis: 
"Nota de neutralidad: La postura, acciones o declaraciones de una figura política o gobierno representan una agenda institucional específica y no deben generalizarse como el reflejo de la cultura, identidad o voluntad de toda la nación o sus ciudadanos."

Tono: Objetivo, analítico, educativo y amigable. No emitas juicios de valor propios, no des consejos financieros de inversión y muestra empatía si el usuario parece estar a punto de caer en una estafa. También debes ser capaz de analizar la inflación y el estado de los países, explicando la variación de los precios de los productos de la canasta básica sin juicios."""

_agent_tools: list[Any] = [
    agent_tool.AgentTool(agent=verificar_fake_news_google_search_agent),
    agent_tool.AgentTool(agent=verificar_fake_news_url_context_agent),
]
if brightdata_toolset is not None:
    _agent_tools.append(brightdata_toolset)
if elastic_toolset is not None:
    _agent_tools.append(elastic_toolset)
if phoenix_toolset is not None:
    _agent_tools.append(phoenix_toolset)

root_agent = LlmAgent(
    name='Verificar_Fake_News',
    model=MODEL_NAME,
    description=(
        'Agente que contrasta narrativas financieras alarmistas y promesas de inversión '
        'sospechosas en redes sociales con fuentes regulado-rigurosas, detecta esquemas '
        'Ponzi/piramidales y pseudo-traders, y consulta su memoria de verificaciones '
        'previas mediante Elastic.'
    ),
    sub_agents=[],
    instruction=prompt_principal,
    tools=_agent_tools,
)


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────
runner = InMemoryRunner(agent=root_agent)


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI (lifespan moderno reemplaza @app.on_event)
# ──────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nada extra por ahora (la inicialización ocurre arriba)
    yield
    # Shutdown: cerrar limpiamente los MCP toolsets activos
    for name, toolset in (
        ("elastic_toolset", elastic_toolset),
        ("brightdata_toolset", brightdata_toolset),
        ("phoenix_toolset", phoenix_toolset),
    ):
        if toolset is None:
            continue
        try:
            await toolset.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error cerrando %s: %s", name, exc)


app = FastAPI(
    title="VeritasAgent API",
    description=(
        "Agente verificador de noticias financieras (Google ADK + Vertex AI). "
        "Detecta desinformación económica, estafas Ponzi y promesas de inversión sospechosas."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

class NewsQuery(BaseModel):
    texto_noticia: str


class ScrapeRequest(BaseModel):
    url: str


# ──────────────────────────────────────────────────────────────────────────────
# Tools de los pasos del agente (triage + persistencia en Elastic)
# ──────────────────────────────────────────────────────────────────────────────
from agent.mcp.elastic_client import get_default_client as _get_elastic
from agent.pipeline import ejecutar_pipeline
from agent.tools.triage import triage as triage_claim


def _persist_firestore(collection: str, payload: dict) -> str | None:
    """Guarda `payload` en Firestore y devuelve el doc_id (o None si falla)."""
    if db is None:
        return None
    try:
        doc_ref = db.collection(collection).document()
        payload = {**payload, "fecha_analisis": firestore.SERVER_TIMESTAMP}
        doc_ref.set(payload)
        return doc_ref.id
    except gcp_exceptions.GoogleAPIError as exc:
        logger.warning("Firestore write fallida en '%s': %s", collection, exc)
        return None


def _mcp_response_to_text(response) -> str:
    """Extrae texto de una respuesta MCP CallToolResult de forma tolerante."""
    content = getattr(response, "content", None)
    if not content:
        return str(response)

    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
        elif isinstance(item, dict) and item.get("text"):
            parts.append(item["text"])
        else:
            parts.append(str(item))
    return "\n".join(parts).strip()


async def _fetch_url_with_brightdata(url: str) -> str:
    """Obtiene contenido de una URL usando Bright Data MCP por stdio.

    El servidor `@brightdata/mcp` expone una tool de scraping principal
    (`scrape_as_markdown`) que devuelve la página en markdown limpio,
    sorteando anti-bot automáticamente.
    """
    if brightdata_toolset is None:
        raise RuntimeError(
            "Bright Data MCP no está configurado (falta BRIGHTDATA_API_TOKEN)."
        )
    session = await brightdata_toolset._mcp_session_manager.create_session()
    response = await session.call_tool("scrape_as_markdown", arguments={"url": url})
    return _mcp_response_to_text(response)


@app.post("/analizar", summary="Analiza una noticia financiera o promesa de inversión")
async def analizar_noticia(query: NewsQuery):
    """
    Flujo:
      [0] Triage semántico en Elastic. Si `score >= 0.92` → EARLY EXIT (cacheado).
      [1..6] Si no hay match fuerte, el agente LLM hace el análisis completo.
      [7] El análisis se guarda en Firestore (log operativo).

    Nota: este endpoint NO indexa en Elastic. El índice `verified_claims`
    solo recibe veredictos estructurados del pipeline (/analizar/multipaso);
    indexar aquí texto libre con placeholders envenenaría el caché del triage.
    """
    user_id = "api_user"
    session_id = "default_session"

    # ── [0] Triage  ────────────────────────────────────────────────────────
    triage_info: dict[str, Any] = {"accion": "skipped", "score": 0.0}
    try:
        triage_info = dict(await triage_claim(query.texto_noticia))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[/analizar] triage falló: %s — sigo en modo fresh", exc)
        triage_info = {"accion": "fresh", "score": 0.0, "motivo": str(exc)}

    if triage_info.get("accion") == "early_exit" and triage_info.get("cached"):
        cached = triage_info["cached"]
        logger.info(
            "[/analizar] EARLY EXIT con score %.3f (claim_hash=%s)",
            triage_info["score"], cached.get("claim_hash"),
        )
        respuesta = (
            f"[Resultado cacheado del {cached.get('verified_at', 'fecha desconocida')}]\n\n"
            f"Categoría: {cached.get('category', '?')} "
            f"(confianza: {cached.get('confidence', '?')}, score: {cached.get('verdict_score', '?')})\n\n"
            f"{cached.get('reasoning', '(sin razonamiento guardado)')}"
        )
        doc_id = _persist_firestore(
            FIRESTORE_COLLECTION_ANALISIS,
            {
                "texto_noticia": query.texto_noticia,
                "analisis": respuesta,
                "agente": root_agent.name,
                "modelo": MODEL_NAME,
                "user_id": user_id,
                "session_id": session_id,
                "estado": "early_exit",
                "triage_score": triage_info["score"],
            },
        )
        return JSONResponse({
            "analisis": respuesta,
            "firestore_doc_id": doc_id,
            "triage": triage_info,
        })

    # ── [1..6] Flujo completo con el agente LLM ───────────────────────────
    try:
        respuesta_final = ""

        existing = await runner.session_service.get_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if existing is None:
            await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=user_id,
                session_id=session_id,
            )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=query.texto_noticia)],
            ),
        ):
            try:
                if hasattr(event, 'is_final_response') and event.is_final_response():
                    respuesta_final = event.content.parts[0].text
            except Exception:  # noqa: BLE001
                respuesta_final = str(event)

        if not respuesta_final:
            respuesta_final = (
                "El agente procesó la solicitud pero no devolvió una respuesta final."
            )

        # ── [7a] Log operativo en Firestore (siempre) ─────────────────────
        doc_id = _persist_firestore(
            FIRESTORE_COLLECTION_ANALISIS,
            {
                "texto_noticia": query.texto_noticia,
                "analisis": respuesta_final,
                "agente": root_agent.name,
                "modelo": MODEL_NAME,
                "user_id": user_id,
                "session_id": session_id,
                "estado": "completado",
                "triage_score": triage_info.get("score", 0.0),
                "triage_accion": triage_info.get("accion"),
            },
        )

        return JSONResponse({
            "analisis": respuesta_final,
            "firestore_doc_id": doc_id,
            "triage": triage_info,
        })

    except Exception as e:  # noqa: BLE001
        logger.exception("Error en /analizar")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/analizar/multipaso",
    summary="Flujo multi-paso determinista: triage → claims → fuente → linguistic → verdict",
)
async def analizar_multipaso(query: NewsQuery):
    """Ejecuta el pipeline determinista de `agent/pipeline.py` y devuelve
    el desglose completo de pasos (ideal para la demo del reto).
    """
    try:
        resultado = await ejecutar_pipeline(query.texto_noticia, language="es")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error en /analizar/multipaso")
        raise HTTPException(status_code=500, detail=str(exc))

    # Log operativo en Firestore (para historial)
    doc_id = _persist_firestore(
        FIRESTORE_COLLECTION_ANALISIS,
        {
            "texto_noticia": query.texto_noticia,
            "etiqueta": resultado.get("etiqueta"),
            "confianza": resultado.get("confianza"),
            "confianza_nivel": resultado.get("confianza_nivel"),
            "resumen": resultado.get("resumen"),
            "pasos_ejecutados": resultado.get("pasos_ejecutados", []),
            "cacheado": resultado.get("cacheado", False),
            "elastic_doc_id": resultado.get("elastic_doc_id"),
            "agente": root_agent.name,
            "modelo": MODEL_NAME,
            "estado": "completado",
            "modo": "multipaso",
        },
    )

    return JSONResponse({**resultado, "firestore_doc_id": doc_id})


@app.get("/historial", summary="Últimos N análisis guardados en Firestore")
def historial(limit: int = 10):
    """Devuelve los últimos análisis para auditoría rápida (no semántico)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Firestore no disponible")
    try:
        docs = (
            db.collection(FIRESTORE_COLLECTION_ANALISIS)
            .order_by("fecha_analisis", direction=firestore.Query.DESCENDING)
            .limit(max(1, min(limit, 100)))
            .stream()
        )
        items = []
        for d in docs:
            data = d.to_dict() or {}
            items.append({
                "doc_id": d.id,
                "texto_noticia": (data.get("texto_noticia") or "")[:200],
                "etiqueta": data.get("etiqueta"),
                "confianza": data.get("confianza"),
                "modo": data.get("modo", "reactivo"),
                "estado": data.get("estado"),
                "fecha": str(data.get("fecha_analisis")) if data.get("fecha_analisis") else None,
            })
        return {"items": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/scrape", summary="Extrae texto visible de una URL y lo guarda en Firestore")
async def scrape_url(request: ScrapeRequest):
    try:
        texto_limpio = await _fetch_url_with_brightdata(request.url)

        doc_id = _persist_firestore(
            FIRESTORE_COLLECTION_SCRAPES,
            {
                "url": request.url,
                "contenido": texto_limpio,
                "estado_extraccion": "exitosa",
                "extractor": "brightdata-mcp",
            },
        )

        return {
            "url": request.url,
            "texto": texto_limpio,
            "firestore_doc_id": doc_id,
        }

    except Exception as e:  # noqa: BLE001
        _persist_firestore(
            FIRESTORE_COLLECTION_SCRAPES,
            {
                "url": request.url,
                "contenido": None,
                "estado_extraccion": "fallida",
                "extractor": "brightdata-mcp",
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener la URL con Bright Data MCP: {e}",
        )


@app.get("/health", summary="Verifica el estado del servidor y la telemetría")
def health_check():
    # Comprobamos Elastic con un ping síncrono pero rápido.
    elastic_status = "disabled"
    if elastic_toolset is not None:
        try:
            elastic_status = "connected" if _get_elastic().healthy() else "unavailable"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Elastic ping fallido: %s", exc)
            elastic_status = "unavailable"

    return {
        "status": "online",
        "agent": root_agent.name,
        "model": MODEL_NAME,
        "auth": describe_auth(),                # NEW: modo elegido (vertex_adc | api_key)
        "telemetry": "connected" if PHOENIX_ENABLED else "disabled",
        "firestore": "connected" if db is not None else "unavailable",
        "vertex_ai": (
            "connected" if VERTEX_AI_CONNECTED
            else ("disabled" if not USE_VERTEXAI else "unavailable")
        ),
        "elastic_mcp": elastic_status,
        "brightdata_mcp": "configured" if brightdata_toolset is not None else "missing_token",
        "phoenix_mcp": "configured" if phoenix_toolset is not None else "disabled",
        "project_id": GOOGLE_CLOUD_PROJECT,
        "location": GOOGLE_CLOUD_LOCATION,
        "elastic_index": ELASTIC_INDEX,
    }