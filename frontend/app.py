"""
Frontend tipo chat para consumir la API de VeritasAgent.

Ejecutar con:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(
    page_title="VeritasAgent",
    page_icon="VA",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --veritas-bg: #f7f8fb;
        --veritas-panel: #ffffff;
        --veritas-border: #dde3ee;
        --veritas-text: #172033;
        --veritas-muted: #68758a;
    }

    .stApp {
        background: var(--veritas-bg);
        color: var(--veritas-text);
    }

    .block-container {
        max-width: 920px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .hero {
        background: var(--veritas-panel);
        border: 1px solid var(--veritas-border);
        border-radius: 8px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1rem;
    }

    .hero-title {
        color: var(--veritas-text);
        font-size: 1.65rem;
        line-height: 1.2;
        font-weight: 720;
        margin: 0 0 .25rem 0;
        letter-spacing: 0;
    }

    .hero-subtitle {
        color: var(--veritas-muted);
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
        border: 1px solid var(--veritas-border);
        background: #fbfcff;
        color: var(--veritas-muted);
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
        color: var(--veritas-muted);
        font-size: .82rem;
        margin-top: .35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_health() -> dict:
    try:
        response = requests.get(f"{API_URL}/health", timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"status": "offline", "error": str(exc)}


def analyze_news(text: str) -> dict:
    response = requests.post(
        f"{API_URL}/analizar",
        json={"texto_noticia": text},
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


health = get_health()
status = health.get("status", "offline")
firestore = health.get("firestore", "unknown")
vertex_ai = health.get("vertex_ai", "unknown")
project_id = health.get("project_id", "sin proyecto")

st.markdown(
    f"""
    <section class="hero">
        <h1 class="hero-title">VeritasAgent</h1>
        <p class="hero-subtitle">Chat de verificación para noticias financieras, rumores de mercado y promesas de inversión.</p>
        <div class="status-row">
            <span class="status-chip">API: {status}</span>
            <span class="status-chip">Vertex AI: {vertex_ai}</span>
            <span class="status-chip">Firestore: {firestore}</span>
            <span class="status-chip">Proyecto: {project_id}</span>
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
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Conversación limpia. Envíame la siguiente noticia para analizar.",
            }
        ]
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
                result = analyze_news(prompt)
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
