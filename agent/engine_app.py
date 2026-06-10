"""Integración con Vertex AI Agent Engine (Google Cloud Agent Builder).

Este módulo NO modifica ninguna lógica del agente existente.
Solo envuelve el ``root_agent`` definido en ``main.py`` dentro de un
``AdkApp`` — el adaptador que Agent Engine necesita para gestionar
sesiones, callbacks y despliegue en Vertex AI.

Uso típico:
    from agent.engine_app import build_adk_app
    app = build_adk_app()        # AdkApp listo para desplegar o probar
    app.query(input="Titulares...")  # prueba local antes de desplegar

Por qué ``GlobalGemini``:
    Los modelos de la serie gemini-2.x/3.x solo se sirven desde el
    endpoint ``global``.  Cuando Agent Engine ejecuta el agente en una
    región específica (p.ej. ``us-central1``), el cliente ADK construye
    el endpoint desde esa región y recibe un "model not found".
    ``GlobalGemini`` sobreescribe solo el ``api_client`` para pinear
    ``location="global"`` sin cambiar nada más del agente.

Solo disponible en Modo A (Vertex AI / ADC).
"""

from __future__ import annotations

import logging
import os
from functools import cached_property

from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Guardia de modo: este módulo requiere Vertex AI (ADC).
# ──────────────────────────────────────────────────────────────────────────────
_use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {
    "1", "true", "yes", "on"
}
if not _use_vertex:
    raise EnvironmentError(
        "agent.engine_app requiere GOOGLE_GENAI_USE_VERTEXAI=True (Modo A / ADC). "
        "Agent Engine no está disponible con API key directa."
    )

import vertexai  # noqa: E402
from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.adk.tools import agent_tool, url_context  # noqa: E402
from google.adk.tools.google_search_tool import GoogleSearchTool  # noqa: E402
from google.genai import Client  # noqa: E402
from vertexai.agent_engines import AdkApp  # noqa: E402
from agent.prompts._agent_prompt import PROMPT_PRINCIPAL  # noqa: E402

GOOGLE_CLOUD_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

vertexai.init(project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION)


# ──────────────────────────────────────────────────────────────────────────────
# GlobalGemini: pínea el cliente al endpoint global para garantizar acceso
# a los modelos Gemini independientemente de la región del Agent Engine.
# ──────────────────────────────────────────────────────────────────────────────
class GlobalGemini(Gemini):
    """Gemini con ``api_client`` forzado a ``location='global'``.

    Agent Engine despliega el agente en una región (ej. ``us-central1``).
    El ADK construye el cliente con esa región, pero los modelos Gemini
    2.x/3.x solo están disponibles desde el endpoint ``global``.
    """

    @cached_property
    def api_client(self) -> Client:
        return Client(vertexai=True, location="global")


# ──────────────────────────────────────────────────────────────────────────────
# Sub-agentes y root_agent — misma lógica que main.py pero usando GlobalGemini.
# El prompt se importa desde agent/prompts/_agent_prompt.py (fuente única).
# ──────────────────────────────────────────────────────────────────────────────


def _build_root_agent() -> LlmAgent:
    """Construye el agente ADK con GlobalGemini para uso en Agent Engine."""
    _model = GlobalGemini(model=MODEL_NAME)

    google_search_agent = LlmAgent(
        name="Verificar_Fake_News_google_search_agent",
        model=_model,
        description="Agent specialized in performing Google searches.",
        instruction="Use the GoogleSearchTool to find information on the web.",
        tools=[GoogleSearchTool()],
    )

    url_context_agent = LlmAgent(
        name="Verificar_Fake_News_url_context_agent",
        model=_model,
        description="Agent specialized in fetching content from URLs.",
        instruction="Use the UrlContextTool to retrieve content from provided URLs.",
        tools=[url_context],
    )

    return LlmAgent(
        name="Verificar_Fake_News",
        model=_model,
        description=(
            "Agente que contrasta narrativas financieras alarmistas y promesas de inversión "
            "sospechosas en redes sociales con fuentes regulado-rigurosas, detecta esquemas "
            "Ponzi/piramidales y pseudo-traders, y consulta su memoria de verificaciones "
            "previas mediante Elastic."
        ),
        instruction=PROMPT_PRINCIPAL,
        tools=[
            agent_tool.AgentTool(agent=google_search_agent),
            agent_tool.AgentTool(agent=url_context_agent),
        ],
    )


def build_adk_app() -> AdkApp:
    """Devuelve un ``AdkApp`` listo para desplegar o probar localmente.

    Ejemplo de prueba local (sin desplegar)::

        app = build_adk_app()
        response = app.query(
            input="¿Es verdad que Bitcoin llegará a 1M$ este año?",
            user_id="test-user",
            session_id="test-session",
        )
        print(response)
    """
    return AdkApp(agent=_build_root_agent(), enable_tracing=True)
