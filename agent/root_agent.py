"""
root_agent.py — Definición y cableado del agente VeritasAgent (Google ADK).

Único lugar donde se define el agente. Tanto la API (`main.py`) como un futuro
despliegue en Vertex AI Agent Engine importan `root_agent` desde aquí.

Centraliza:
- Inicialización de Vertex AI (Gemini).
- Construcción de los toolsets MCP de partner (Brave, Fetch, Bright Data, Elastic).
- El prompt del sistema y los sub-agentes (Google Search / URL Context).
- El `root_agent` que cablea el flujo [0]-[7] descrito en PLAN.md.
- Los umbrales de early-exit del triage (re-exportados desde agent.tools.triage).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Cargar el .env del repositorio (idempotente; main.py también lo hace).
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)


def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


# --- Google ADK ---
from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters

# --- Vertex AI ---
import vertexai
from google.cloud import aiplatform

# Umbrales de early-exit: definidos una sola vez en el triage, re-exportados aquí.
from agent.tools.triage import EARLY_EXIT_THRESHOLD, EVIDENCE_THRESHOLD  # noqa: F401


# ==========================================================================
# 1. Inicialización de Vertex AI (Gemini)
# ==========================================================================
VERTEX_PROJECT = _env_value("PROJECT_ID", "hackaton-498600")
VERTEX_LOCATION = _env_value("VERTEX_LOCATION", "us-central1")
os.environ["PROJECT_ID"] = VERTEX_PROJECT
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
os.environ["GOOGLE_CLOUD_PROJECT"] = VERTEX_PROJECT
os.environ["GOOGLE_CLOUD_LOCATION"] = VERTEX_LOCATION
vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)

VERTEX_AI_CONNECTED = True
try:
    _model_client = aiplatform.gapic.ModelServiceClient(
        client_options={"api_endpoint": f"{VERTEX_LOCATION}-aiplatform.googleapis.com"}
    )
    _parent = f"projects/{VERTEX_PROJECT}/locations/{VERTEX_LOCATION}"
    next(iter(_model_client.list_models(parent=_parent)), None)
except Exception as exc:  # noqa: BLE001
    print(
        "[WARN] Vertex AI ADC no disponible o sin permisos. "
        f"Proyecto={VERTEX_PROJECT}, región={VERTEX_LOCATION}. Error: {exc}"
    )
    VERTEX_AI_CONNECTED = False

GEMINI_MODEL = _env_value("MODEL_ID") or _env_value("GEMINI_MODEL", "gemini-2.5-flash")


# ==========================================================================
# 2. Toolsets MCP de partner
# ==========================================================================
def _docker_disponible() -> bool:
    """True si el daemon de Docker responde (necesario para el MCP de Elastic)."""
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _build_brave_toolset() -> MCPToolset | None:
    api_key = _env_value("BRAVE_API_KEY")
    if not api_key:
        print("[WARN] BRAVE_API_KEY no está definida. Brave Search MCP quedará desactivado.")
        return None
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-brave-search"],
                env={**os.environ, "BRAVE_API_KEY": api_key},
            ),
            timeout=30.0,
        )
    )


def _build_fetch_toolset() -> MCPToolset:
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_server_fetch"],
            ),
            timeout=30.0,
        )
    )


def _build_brightdata_toolset() -> MCPToolset | None:
    # El partner Bright Data expone su servidor MCP oficial (@brightdata/mcp) con
    # herramientas de scraping y búsqueda web que sortean bloqueos anti-bot.
    # Cubre los pasos [1] Extractor y [4] Cross-Reference del flujo del agente.
    api_key = (
        _env_value("BRIGHTDATA_API_KEY")
        or _env_value("BRIGHT_DATA_API_KEY")
        or _env_value("API_TOKEN")
    )
    if not api_key:
        print("[WARN] BRIGHTDATA_API_KEY no está definida. Bright Data MCP quedará desactivado.")
        return None
    toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@brightdata/mcp"],
                env={**os.environ, "API_TOKEN": api_key},
            ),
            timeout=60.0,
        )
    )
    print("[INFO] Bright Data MCP toolset activo (servidor MCP oficial @brightdata/mcp).")
    return toolset


def _build_elastic_toolset() -> MCPToolset | None:
    # El partner Elastic expone su servidor MCP oficial (list_indices, get_mappings,
    # search, esql, get_shards) para consultar la memoria de verificaciones en
    # lenguaje natural. Requiere Docker; sin él, el triage/memoria siguen activos.
    url = _env_value("ELASTIC_URL")
    api_key = _env_value("ELASTIC_API_KEY")
    image = _env_value("ELASTIC_MCP_IMAGE", "docker.elastic.co/mcp/elasticsearch")
    if not (url and api_key):
        print("[WARN] ELASTIC_URL/ELASTIC_API_KEY no definidos. Elastic MCP toolset desactivado.")
        return None
    if not _docker_disponible():
        print("[WARN] Docker no disponible. Elastic MCP toolset desactivado "
              "(el triage y la memoria de Elastic siguen funcionando sin Docker).")
        return None
    toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="docker",
                args=[
                    "run", "-i", "--rm",
                    "-e", "ES_URL",
                    "-e", "ES_API_KEY",
                    image,
                    "stdio",
                ],
                env={**os.environ, "ES_URL": url, "ES_API_KEY": api_key},
            ),
            timeout=60.0,
        )
    )
    print("[INFO] Elastic MCP toolset activo (servidor MCP oficial de Elasticsearch).")
    return toolset


brave_toolset = _build_brave_toolset()
fetch_toolset = _build_fetch_toolset()
brightdata_toolset = _build_brightdata_toolset()
elastic_toolset = _build_elastic_toolset()


def active_toolsets() -> list[MCPToolset]:
    """Toolsets MCP activos, para cierre ordenado en el shutdown de la API."""
    return [
        t for t in (brave_toolset, fetch_toolset, brightdata_toolset, elastic_toolset)
        if t is not None
    ]


# ==========================================================================
# 3. Sub-agentes especializados
# ==========================================================================
google_search_agent = LlmAgent(
    name='Verificar_Fake_News_google_search_agent',
    model=GEMINI_MODEL,
    description='Agent specialized in performing Google searches.',
    sub_agents=[],
    instruction='Use the GoogleSearchTool to find information on the web.',
    tools=[GoogleSearchTool()],
)

url_context_agent = LlmAgent(
    name='Verificar_Fake_News_url_context_agent',
    model=GEMINI_MODEL,
    description='Agent specialized in fetching content from URLs.',
    sub_agents=[],
    instruction='Use the UrlContextTool to retrieve content from provided URLs.',
    tools=[url_context],
)


# ==========================================================================
# 4. Prompt del sistema (flujo [0]-[7])
# ==========================================================================
PROMPT_PRINCIPAL = """Eres un analista de medios financieros avanzado, verificador de hechos neutral y experto en prevención de fraudes. Tu objetivo es combatir la desinformación económica, el alarmismo financiero y proteger a los usuarios de esquemas Ponzi, estafas piramidales y "pseudo-traders" en redes sociales. Deconstruyes narrativas de inversión y analizas la polarización económica, explicando la información de forma accesible, estructurada y amigable.

Misión y Flujo de Trabajo:
Cuando el usuario te presente un titular económico, una promesa de inversión, un enlace sospechoso o una alerta de la bolsa, debes realizar estrictamente los siguientes pasos:

0. Memoria de Verificaciones (Elastic): Antes de investigar desde cero, usa las herramientas de Elasticsearch (search/esql) SOLO sobre el índice exacto llamado `verified_claims` (no inventes ni uses ningún otro nombre de índice). Si una herramienta de Elasticsearch falla o el índice no existe, ignórala y continúa el análisis con el resto de herramientas. Si existe un veredicto previo nuestro y sigue vigente, reutílizalo y cítalo en vez de repetir el análisis. Nunca asumas que una noticia es real solo porque se parezca a otra; el atajo solo aplica a afirmaciones que NOSOTROS ya verificamos.
1. Búsqueda Multilateral y Verificación de Fuentes: Utiliza tus herramientas de búsqueda para rastrear la noticia o la oportunidad de inversión en al menos 3 medios financieros confiables y regulados (ej. Reuters, Bloomberg, prensa económica local). Cuando una URL esté bloqueada, protegida con anti-bot o requieras extraer el contenido completo de un artículo o buscar en fact-checkers (Snopes, AFP Factual, Maldita, Newtral, Colombiacheck), usa las herramientas de Bright Data (scraping y búsqueda web) que sortean bloqueos. Si la información proviene de una red social, evalúa la credibilidad de la página o perfil. Sugiere al usuario rectificar si la fuente no tiene historial de rigor periodístico o financiero.
2. Línea de Tiempo del Mercado / Noticia: Reconstruye la evolución de la noticia o tendencia. Muestra cronológicamente cuándo surgió el rumor o dato, cómo reaccionaron los titulares financieros y qué hechos confirmaron o desmintieron la narrativa con el paso de los días.
3. Detección de Fraude y "Pseudo-traders": Analiza la promesa de inversión en busca de banderas rojas (red flags) típicas de esquemas Ponzi o pirámides. Evalúa si el texto incluye: Promesas de rentabilidad inusualmente altas o "garantizadas" sin riesgo, sentido de urgencia extrema o FOMO, enfoque en reclutar a otras personas, o uso de lenguaje ostentoso.
4. Análisis de Incertidumbre y Riesgo: Identifica el lenguaje alarmista. Proporciona una "Métrica de Incertidumbre/Riesgo" (Alta, Media, Baja) basada en la falta de consenso entre analistas serios, la volatilidad real del activo o la presencia de indicadores de estafa.
5. Aclaración Geopolítica Obligatoria: Si la noticia económica involucra políticas de Estado, sanciones, líderes políticos o gobiernos, DEBES incluir textualmente la siguiente advertencia al final de tu análisis: 
"Nota de neutralidad: La postura, acciones o declaraciones de una figura política o gobierno representan una agenda institucional específica y no deben generalizarse como el reflejo de la cultura, identidad o voluntad de toda la nación o sus ciudadanos."

Tono: Objetivo, analítico, educativo y amigable. No emitas juicios de valor propios, no des consejos financieros de inversión y muestra empatía si el usuario parece estar a punto de caer en una estafa. También debes ser capaz de analizar la inflación y el estado de los países, explicando la variación de los precios de los productos de la canasta básica sin juicios."""


# ==========================================================================
# 5. Agente raíz (cablea sub-agentes + toolsets MCP de partner)
# ==========================================================================
root_agent = LlmAgent(
    name='Verificar_Fake_News',
    model=GEMINI_MODEL,
    description='Este agente busca contrastar un mundo en redes sociales alarmista y reactivo y convertirlo en uno más analítico y confiable, enfocado en economía global y prevención de fraudes.',
    sub_agents=[],
    instruction=PROMPT_PRINCIPAL,
    tools=(
        [
            agent_tool.AgentTool(agent=google_search_agent),
            agent_tool.AgentTool(agent=url_context_agent),
        ]
        + ([brave_toolset] if brave_toolset is not None else [])
        + [fetch_toolset]
        + ([brightdata_toolset] if brightdata_toolset is not None else [])
        + ([elastic_toolset] if elastic_toolset is not None else [])
    ),
)
