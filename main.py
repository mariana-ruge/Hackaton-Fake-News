"""
VeritasAgent — API del agente verificador de noticias financieras.

Arranca con:
    uvicorn main:app --host 0.0.0.0 --port 8000

Variables de entorno requeridas (ver .env.example):
    GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, MODEL_NAME,
    BRIGHT_DATA_WS_URL, API_KEY_PHOENIX
    (opcionales) BRAVE_API_KEY
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

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
# Configuración: variables unificadas (ver .env.example)
# ──────────────────────────────────────────────────────────────────────────────
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

if not GOOGLE_CLOUD_PROJECT:
    raise RuntimeError(
        "GOOGLE_CLOUD_PROJECT no está definida. Crea tu .env a partir de .env.example "
        "y rellena el ID del proyecto de Google Cloud."
    )

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
os.environ["GOOGLE_CLOUD_PROJECT"] = GOOGLE_CLOUD_PROJECT
os.environ["GOOGLE_CLOUD_LOCATION"] = GOOGLE_CLOUD_LOCATION

# ──────────────────────────────────────────────────────────────────────────────
# Inicialización de Vertex AI (autenticación vía ADC)
# ──────────────────────────────────────────────────────────────────────────────
import vertexai
from google.cloud import aiplatform

vertexai.init(project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION)

VERTEX_AI_CONNECTED = True
try:
    model_service_client = aiplatform.gapic.ModelServiceClient(
        client_options={"api_endpoint": f"{GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com"}
    )
    parent = f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{GOOGLE_CLOUD_LOCATION}"
    next(iter(model_service_client.list_models(parent=parent)), None)
except Exception as exc:  # noqa: BLE001
    logger.warning(
        "Vertex AI ADC no disponible o sin permisos. Proyecto=%s, región=%s. Error: %s",
        GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, exc,
    )
    VERTEX_AI_CONNECTED = False

# ──────────────────────────────────────────────────────────────────────────────
# MCP toolsets (Brave opcional, Fetch obligatorio)
# ──────────────────────────────────────────────────────────────────────────────
from google.cloud import firestore
from google.api_core import exceptions as gcp_exceptions

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
import sys as _sys

if BRAVE_API_KEY:
    brave_toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-brave-search"],
                env={**os.environ, "BRAVE_API_KEY": BRAVE_API_KEY},
            ),
            timeout=30.0,
        )
    )
else:
    logger.warning("BRAVE_API_KEY no está definida. Brave Search MCP quedará desactivado.")
    brave_toolset = None

fetch_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=_sys.executable,
            args=["-m", "mcp_server_fetch"],
        ),
        timeout=30.0,
    )
)

# ──────────────────────────────────────────────────────────────────────────────
# Observabilidad (Arize Phoenix)
# ──────────────────────────────────────────────────────────────────────────────
PHOENIX_API_KEY = os.getenv("API_KEY_PHOENIX")
PHOENIX_ENABLED = bool(PHOENIX_API_KEY)

if PHOENIX_ENABLED:
    os.environ["PHOENIX_CLIENT_HEADERS"] = f"api_key={PHOENIX_API_KEY}"
    os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "https://app.phoenix.arize.com/v1/traces"

    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"]))
    )
    trace.set_tracer_provider(tracer_provider)
    GoogleADKInstrumentor().instrument()
else:
    logger.warning("API_KEY_PHOENIX no definida. Telemetría desactivada.")


# ──────────────────────────────────────────────────────────────────────────────
# Firestore (persistencia de análisis y scrapes)
# ──────────────────────────────────────────────────────────────────────────────
FIRESTORE_COLLECTION_ANALISIS = os.getenv("FIRESTORE_COLLECTION_ANALISIS", "analisis_noticias")
FIRESTORE_COLLECTION_SCRAPES = os.getenv("FIRESTORE_COLLECTION_SCRAPES", "verificaciones")

try:
    db = firestore.Client(project=GOOGLE_CLOUD_PROJECT)
except Exception as exc:  # noqa: BLE001
    logger.warning("No se pudo inicializar Firestore: %s", exc)
    db = None


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

root_agent = LlmAgent(
    name='Verificar_Fake_News',
    model=MODEL_NAME,
    description=(
        'Agente que contrasta narrativas financieras alarmistas y promesas de inversión '
        'sospechosas en redes sociales con fuentes regulado-rigurosas, y detecta '
        'esquemas Ponzi/piramidales y pseudo-traders.'
    ),
    sub_agents=[],
    instruction=prompt_principal,
    tools=(
        [
            agent_tool.AgentTool(agent=verificar_fake_news_google_search_agent),
            agent_tool.AgentTool(agent=verificar_fake_news_url_context_agent),
        ]
        + ([brave_toolset] if brave_toolset is not None else [])
        + [fetch_toolset]
    ),
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
    # Shutdown: cerrar limpiamente los MCP toolsets
    if brave_toolset is not None:
        try:
            await brave_toolset.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error cerrando brave_toolset: %s", exc)
    try:
        await fetch_toolset.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error cerrando fetch_toolset: %s", exc)


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
        print(f"[WARN] Firestore write fallida en '{collection}': {exc}")
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


async def _fetch_url_with_mcp(url: str) -> str:
    """Obtiene contenido de una URL usando el servidor MCP Fetch por stdio."""
    session = await fetch_toolset._mcp_session_manager.create_session()
    response = await session.call_tool("fetch", arguments={"url": url})
    return _mcp_response_to_text(response)


@app.post("/analizar", summary="Analiza una noticia financiera o promesa de inversión")
async def analizar_noticia(query: NewsQuery):
    try:
        respuesta_final = ""
        user_id = "api_user"
        session_id = "default_session"

        # Crear la sesión si no existe
        existing = await runner.session_service.get_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id
        )
        if existing is None:
            await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=user_id,
                session_id=session_id
            )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=query.texto_noticia)]
            )
        ):
            try:
                if hasattr(event, 'is_final_response') and event.is_final_response():
                    respuesta_final = event.content.parts[0].text
            except Exception:
                respuesta_final = str(event)

        if not respuesta_final:
            respuesta_final = "El agente procesó la solicitud pero no devolvió una respuesta final."

        # Persistencia del análisis para consulta posterior desde GCP
        doc_id = _persist_firestore(
            FIRESTORE_COLLECTION_ANALISIS,
            {
                "texto_noticia": query.texto_noticia,
                "analisis": respuesta_final,
                "agente": root_agent.name,
                "modelo": GEMINI_MODEL,
                "user_id": user_id,
                "session_id": session_id,
                "estado": "completado",
            },
        )

        return JSONResponse(
            content={"analisis": respuesta_final, "firestore_doc_id": doc_id}
        )

    except Exception as e:
        print(f"\n--- ERROR DETALLADO ---\n{e}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scrape", summary="Extrae texto visible de una URL y lo guarda en Firestore")
async def scrape_url(request: ScrapeRequest):
    try:
        texto_limpio = await _fetch_url_with_mcp(request.url)

        doc_id = _persist_firestore(
            FIRESTORE_COLLECTION_SCRAPES,
            {
                "url": request.url,
                "contenido": texto_limpio,
                "estado_extraccion": "exitosa",
                "extractor": "mcp-fetch",
            },
        )

        return {
            "url": request.url,
            "texto": texto_limpio,
            "firestore_doc_id": doc_id,
        }

    except Exception as e:
        _persist_firestore(
            FIRESTORE_COLLECTION_SCRAPES,
            {
                "url": request.url,
                "contenido": None,
                "estado_extraccion": "fallida",
                "extractor": "mcp-fetch",
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail=f"Error al obtener la URL con Fetch MCP: {str(e)}")


@app.get("/health", summary="Verifica el estado del servidor y la telemetría")
def health_check():
    return {
        "status": "online",
        "agent": root_agent.name,
        "model": MODEL_NAME,
        "telemetry": "connected" if PHOENIX_ENABLED else "disabled",
        "firestore": "connected" if db is not None else "unavailable",
        "vertex_ai": "connected" if VERTEX_AI_CONNECTED else "unavailable",
        "brave_mcp": "configured" if brave_toolset is not None else "missing_api_key",
        "project_id": GOOGLE_CLOUD_PROJECT,
        "location": GOOGLE_CLOUD_LOCATION,
    }