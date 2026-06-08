from fastapi.responses import JSONResponse
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)  # Carga .env explícito y prioriza sus valores


def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")

# --- Workaround: silencia el AttributeError cosmético de google-genai al cerrar
# clientes BaseApiClient que nunca instanciaron su httpx async.
import asyncio
import logging


def _silence_genai_aclose(loop, context):
    exc = context.get("exception")
    if isinstance(exc, AttributeError) and "_async_httpx_client" in str(exc):
        return
    loop.default_exception_handler(context)


try:
    asyncio.get_event_loop().set_exception_handler(_silence_genai_aclose)
except RuntimeError:
    pass
logging.getLogger("asyncio").setLevel(logging.ERROR)

# --- Dependencias del runtime de la API ---
from google.genai import types as genai_types
from google.cloud import firestore
from google.api_core import exceptions as gcp_exceptions

# --- Agente, toolsets y configuración (definidos en agent/root_agent.py) ---
# El agente se define una sola vez allí; aquí solo se consume.
from agent.root_agent import (
    root_agent,
    GEMINI_MODEL,
    VERTEX_AI_CONNECTED,
    brave_toolset,
    fetch_toolset,
    brightdata_toolset,
    elastic_toolset,
    active_toolsets,
)


# ==========================================
# 1.b CONFIGURACIÓN DE FIRESTORE
# ==========================================
PROJECT_ID = _env_value("PROJECT_ID", "hackaton-498600")
FIRESTORE_COLLECTION_ANALISIS = _env_value("FIRESTORE_COLLECTION_ANALISIS", "analisis_noticias")
FIRESTORE_COLLECTION_SCRAPES = _env_value("FIRESTORE_COLLECTION_SCRAPES", "verificaciones")

try:
    db = firestore.Client(project=PROJECT_ID)
except Exception as exc:  # noqa: BLE001
    print(f"[WARN] No se pudo inicializar Firestore: {exc}")
    db = None


# ==========================================
# 1.c CONFIGURACIÓN DE ELASTIC (triage + memoria)
# ==========================================
from agent.mcp.elastic_client import get_elastic_client
from agent.tools.triage import triage_semantico

elastic_client = get_elastic_client()
ELASTIC_ENABLED = elastic_client.is_configured()
if ELASTIC_ENABLED:
    print(f"[INFO] Elastic configurado (índice='{elastic_client.index}'). Triage + memoria activos.")
else:
    print("[WARN] Elastic no configurado (faltan ELASTIC_*). El agente funciona sin triage/memoria.")

# --- Elastic como herramienta MCP del agente -------------------------------
# El toolset MCP de Elastic se construye en agent/root_agent.py (se importa
# arriba). Aquí solo vive la capa programática (triage + memoria write-back).


async def _indexar_verificacion_elastic(texto_noticia: str, analisis: str, claim_hash: str) -> None:
    """Write-back: guarda la verificación en Elastic para futuros triages."""
    if not ELASTIC_ENABLED:
        return
    try:
        from agent.tools.embeddings import get_embedding

        embedding = await get_embedding(texto_noticia)
        await elastic_client.ensure_index()
        await elastic_client.index_verification(
            {
                "claim_hash": claim_hash,
                "claim_text": texto_noticia,
                "claim_embedding": embedding,
                "analisis": analisis,
                "veredicto": "analizado",
                "fuente": root_agent.name,
                "idioma": "es",
            }
        )
    except Exception as exc:  # noqa: BLE001 - nunca rompe el flujo principal
        print(f"[WARN] No se pudo indexar la verificación en Elastic: {exc}")


# ==========================================
# 3. CONFIGURACIÓN DEL RUNNER (El Motor)
# ==========================================
from google.adk.runners import InMemoryRunner
# El motor instanciará lo que necesite internamente
runner = InMemoryRunner(agent=root_agent)


# ==========================================
# 4. CONFIGURACIÓN DE LA API (FastAPI)
# ==========================================
app = FastAPI(
    title="Verificar Fake News API",
    description="API del agente financiero para la Hackathon usando Google ADK y Elastic",
    version="1.0.0"
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
        # ----------------------------------------------------------------
        # [0] TRIAGE: ¿ya verificamos esta noticia? (memoria Elastic)
        # ----------------------------------------------------------------
        decision = await triage_semantico(query.texto_noticia)
        if decision["early_exit"] and decision.get("cached_doc"):
            cached = decision["cached_doc"]
            return JSONResponse(
                content={
                    "analisis": cached.get("analisis", ""),
                    "firestore_doc_id": None,
                    "early_exit": True,
                    "triage_source": decision["source"],
                    "triage_score": round(decision["score"], 4),
                    "verificado_en": cached.get("verified_at"),
                }
            )

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

        try:
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
        except Exception as run_exc:  # noqa: BLE001 - un fallo de herramienta no debe romper la petición
            print(f"[WARN] El agente encontró un error durante la ejecución (se continúa): {run_exc}")

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

        # [7] Write-back: alimenta la memoria de Elastic para triages futuros.
        await _indexar_verificacion_elastic(
            query.texto_noticia, respuesta_final, decision["claim_hash"]
        )

        return JSONResponse(
            content={
                "analisis": respuesta_final,
                "firestore_doc_id": doc_id,
                "early_exit": False,
                "triage_source": decision["source"],
                "triage_score": round(decision["score"], 4),
            }
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


@app.on_event("shutdown")
async def shutdown_mcp_toolsets():
    for toolset in active_toolsets():
        await toolset.close()
    if ELASTIC_ENABLED:
        await elastic_client.close()


@app.get("/health", summary="Verifica el estado del servidor y sus integraciones")
def health_check():
    return {
        "status": "online",
        "agent": "Verificar_Fake_News",
        "firestore": "connected" if db is not None else "unavailable",
        "vertex_ai": "connected" if VERTEX_AI_CONNECTED else "unavailable",
        "brave_mcp": "configured" if brave_toolset is not None else "missing_api_key",
        "brightdata_mcp": "configured" if brightdata_toolset is not None else "missing_api_key",
        "elastic": "configured" if ELASTIC_ENABLED else "unavailable",
        "elastic_mcp": "configured" if elastic_toolset is not None else "unavailable",
        "project_id": PROJECT_ID,
    }