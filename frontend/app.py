"""
Frontend tipo chat para Blacklight Expose.

Dos modos de ejecución, seleccionables con la variable FRONTEND_MODE:
  - "api"    (default): llama a FastAPI en API_URL  → uvicorn main:app
  - "direct":           usa el ADK runner directamente, sin FastAPI

Ejecutar con:
    streamlit run frontend/app.py
    FRONTEND_MODE=direct streamlit run frontend/app.py
"""

from __future__ import annotations

import asyncio
import os

import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
FRONTEND_MODE = os.getenv("FRONTEND_MODE", "api").strip().lower()


# ── Modo directo: carga el runner de main.py una sola vez ─────────────────
@st.cache_resource(show_spinner="Cargando agente…")
def _get_runner():
    """Importa y devuelve el InMemoryRunner de main.py (singleton por proceso)."""
    from main import runner  # noqa: PLC0415
    return runner


def _run_agent_direct(text: str, session_id: str) -> str:
    """Invoca el runner ADK directamente y devuelve el texto de respuesta."""
    from google.genai import types as genai_types  # noqa: PLC0415

    runner = _get_runner()
    user_id = "streamlit_user"

    async def _invoke() -> str:
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
        respuesta = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=text)],
            ),
        ):
            try:
                if hasattr(event, "is_final_response") and event.is_final_response():
                    respuesta = event.content.parts[0].text
            except Exception:  # noqa: BLE001
                respuesta = str(event)
        return respuesta or "El agente procesó la solicitud pero no devolvió respuesta."

    return asyncio.run(_invoke())


st.set_page_config(
    page_title="Blacklight Expose",
    page_icon="🔦",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --blacklight-bg: #f7f8fb;
        --blacklight-panel: #ffffff;
        --blacklight-border: #dde3ee;
        --blacklight-text: #172033;
        --blacklight-muted: #68758a;
    }

    .stApp {
        background: var(--blacklight-bg);
        color: var(--blacklight-text);
    }

    .block-container {
        max-width: 920px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .hero {
        background: var(--blacklight-panel);
        border: 1px solid var(--blacklight-border);
        border-radius: 8px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1rem;
    }

    .hero-title {
        color: var(--blacklight-text);
        font-size: 1.65rem;
        line-height: 1.2;
        font-weight: 720;
        margin: 0 0 .25rem 0;
        letter-spacing: 0;
    }

    .hero-subtitle {
        color: var(--blacklight-muted);
        font-size: .98rem;
        margin: 0;
    }

    .status-row {
        display: flex;
        gap: .5rem;
        flex-wrap: wrap;
        margin-top: .85rem;
    }

    .status-chip {
        border: 1px solid var(--blacklight-border);
        background: #fbfcff;
        color: var(--blacklight-muted);
        border-radius: 999px;
        padding: .25rem .62rem;
        font-size: .82rem;
        white-space: nowrap;
    }

    .stChatMessage {
        border-radius: 8px;
        border: 1px solid rgba(221, 227, 238, .75);
        background: #ffffff;
    }

    div[data-testid="stChatInput"] textarea {
        border-radius: 8px;
    }

    .small-note {
        color: var(--blacklight-muted);
        font-size: .82rem;
        margin-top: .35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_health() -> dict:
    if FRONTEND_MODE == "direct":
        try:
            _get_runner()
            return {"status": "online (directo)", "vertex_ai": "n/a", "firestore": "n/a", "project_id": os.getenv("GOOGLE_CLOUD_PROJECT", "—")}
        except Exception as exc:  # noqa: BLE001
            return {"status": "offline", "error": str(exc)}
    try:
        response = requests.get(f"{API_URL}/health", timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"status": "offline", "error": str(exc)}


def analyze_news(text: str, session_id: str) -> dict:
    if FRONTEND_MODE == "direct":
        answer = _run_agent_direct(text, session_id)
        return {"analisis": answer, "firestore_doc_id": None}
    response = requests.post(
        f"{API_URL}/analizar",
        json={"texto_noticia": text, "session_id": session_id},
        timeout=240,
    )
    response.raise_for_status()
    return response.json()


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hola. Pega una noticia, titular financiero, promesa de inversión "
                "o publicación sospechosa y la analizo con contexto, riesgo y evidencias."
            ),
        }
    ]

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = f"s-{uuid.uuid4().hex[:12]}"


health = get_health()
status = health.get("status", "offline")
firestore = health.get("firestore", "unknown")
vertex_ai = health.get("vertex_ai", "unknown")
project_id = health.get("project_id", "sin proyecto")

st.markdown(
    f"""
    <section class="hero">
        <h1 class="hero-title">Blacklight Expose</h1>
        <p class="hero-subtitle">Chat de verificación para noticias financieras, rumores de mercado y promesas de inversión.</p>
        <div class="status-row">
            <span class="status-chip">API: {status}</span>
            <span class="status-chip">Vertex AI: {vertex_ai}</span>
            <span class="status-chip">Firestore: {firestore}</span>
            <span class="status-chip">Proyecto: {project_id}</span>
            <span class="status-chip">Modo: {FRONTEND_MODE}</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Configuración")
    st.code(API_URL, language="text")
    st.caption("Define API_URL si la API corre en otro host o puerto.")

    if st.button("Limpiar conversación", use_container_width=True):
        import uuid
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Conversación limpia. Envíame la siguiente noticia para analizar.",
            }
        ]
        st.session_state.session_id = f"s-{uuid.uuid4().hex[:12]}"
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("doc_id"):
            st.markdown(
                f"<p class='small-note'>Guardado en Firestore: {message['doc_id']}</p>",
                unsafe_allow_html=True,
            )

prompt = st.chat_input("Pega aquí la noticia o promesa de inversión...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando la noticia..."):
            try:
                result = analyze_news(prompt, st.session_state.session_id)
                answer = result.get("analisis") or "El agente no devolvió contenido."
                doc_id = result.get("firestore_doc_id")
                st.markdown(answer)
                if doc_id:
                    st.markdown(
                        f"<p class='small-note'>Guardado en Firestore: {doc_id}</p>",
                        unsafe_allow_html=True,
                    )
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "doc_id": doc_id}
                )
            except requests.RequestException as exc:
                error_message = (
                    "No pude conectar con la API o el análisis falló. "
                    f"Detalle técnico: {exc}"
                )
                st.error(error_message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_message}
                )
