<div align="center">

# 🛡️ VeritasAgent

### Agente verificador de **noticias financieras** y detector de fraudes de inversión

**Powered by Gemini · Google ADK · Vertex AI · FastAPI · Streamlit · Arize Phoenix · Firestore · Bright Data**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-8E75B2.svg)](https://ai.google.dev/)

[Demo](#-demo) · [Arquitectura](#-arquitectura) · [Cómo funciona](#-cómo-funciona) · [Instalación](#-instalación) · [Roadmap](./IMPLEMENTATION.md)

</div>

---

## 📰 El problema

La desinformación financiera se propaga como pólvora: titulares alarmistas sobre el mercado, promesas de rentabilidades imposibles, "gurús" de Telegram, esquemas Ponzi disfrazados de oportunidades únicas. Las víctimas pierden dinero real porque:

- Los titulares económicos son **fáciles de manipular** y difíciles de contrastar.
- Las **promesas de inversión sospechosas** se distribuyen masivamente por redes sociales sin filtros.
- Los **fact-checkers tradicionales** rara vez cubren contenido económico-financiero en español.

## 💡 La solución

**VeritasAgent** es un agente que recibe **un titular económico, una promesa de inversión, una URL o una publicación sospechosa** y devuelve un **análisis estructurado con contexto, riesgo y evidencia**, citando fuentes financieras rigurosas.

> ⚖️ **Principio rector:** el agente **nunca opina** ni da consejos de inversión. Cita fuentes, identifica banderas rojas de estafa, y avisa al usuario cuando algo huele a Ponzi o pseudo-trader.

---

## ✨ Características

| | |
|---|---|
| 💰 **Foco financiero** | Especializado en desinformación económica, criptos, inversiones y fraudes |
| 🚨 **Detección de fraude** | Banderas rojas de Ponzi, pirámides y "pseudo-traders" (rentabilidades garantizadas, FOMO, reclutamiento) |
| 📊 **Métrica de riesgo** | Etiqueta cada caso con incertidumbre Alta / Media / Baja |
| ⏳ **Línea de tiempo** | Reconstruye cómo evolucionó la narrativa en titulares serios |
| 🌍 **Aclaración geopolítica** | Nota de neutralidad obligatoria cuando la noticia involucra gobiernos o líderes |
| 📈 **Observabilidad** | Trazas en Arize Phoenix de cada llamada del agente |

---

## 🏗️ Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend · Streamlit (chat)                                 │
│  Input: titular / promesa / URL / publicación sospechosa     │
│  Render del análisis + estado de salud (Vertex AI/Firestore) │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼──────────────────────────────────┐
│  Backend · FastAPI                                            │
│  Endpoints:  /analizar  /scrape  /health                      │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  Agente · Google ADK (LlmAgent + Gemini 2.5 Flash)            │
│  Sub-agentes:                                                 │
│    • Google Search                                            │
│    • URL Context                                              │
│  Tools MCP:                                                   │
│    • Brave Search (opcional)                                  │
│    • Fetch (mcp-server-fetch)                                 │
│  Scraping externo: Bright Data Scraping Browser (CDP)         │
└───┬──────────────────────────────┬──────────────────┬────────┘
    │                              │                  │
┌───▼─────────┐         ┌──────────▼─────┐   ┌────────▼────────┐
│  Firestore  │         │  Vertex AI     │   │  Arize Phoenix  │
│  análisis + │         │  embeddings    │   │  trazas OTel    │
│  scrapes    │         │  (768 dims)    │   │                 │
└─────────────┘         └────────────────┘   └─────────────────┘
```

> El agente vive en `main.py` como un `LlmAgent` con un prompt especializado en finanzas. La carpeta `agent/tools/` contiene el **esqueleto del refactor multi-paso** (triage → extractor → claim parser → verdict) que es la siguiente iteración del proyecto.

---

## 🔬 Cómo funciona

El agente recibe el texto y ejecuta el siguiente flujo conceptual (definido en su prompt principal):

| Paso | Qué hace |
|---|---|
| **1. Búsqueda multilateral** | Rastrea la noticia en ≥3 medios financieros regulados (Reuters, Bloomberg, prensa económica local) |
| **2. Línea de tiempo** | Reconstruye cómo evolucionó el rumor / dato económico y qué hechos lo confirmaron o desmintieron |
| **3. Detección de fraude** | Busca banderas rojas Ponzi: rentabilidades "garantizadas", urgencia/FOMO, foco en reclutar, lenguaje ostentoso |
| **4. Métrica de riesgo** | Etiqueta Alta / Media / Baja según consenso entre analistas, volatilidad real e indicadores de estafa |
| **5. Aclaración geopolítica** | Si la noticia involucra políticos/gobiernos, añade nota textual de neutralidad cultural |

### Tono y límites
- Objetivo, analítico, educativo, **nunca da consejos de inversión**.
- Si la fuente no tiene historial riguroso → recomienda contrastar, no dictamina.

---

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| Razonamiento | **Gemini 2.5 Flash** (Vertex AI) |
| Framework de agentes | **Google ADK** |
| Autenticación | **ADC** (Application Default Credentials) — la organización bloquea API keys |
| Backend | **FastAPI + Uvicorn** |
| Frontend | **Streamlit** (chat) |
| Persistencia | **Firestore** (análisis + scrapes) |
| Scraping | **Bright Data Scraping Browser** (CDP/WebSocket + Playwright) |
| 🟢 **Track partner del reto** | **Elastic MCP** (triage + memoria semántica) |
| MCPs adicionales | **Bright Data MCP** (scraping/evidencia) · **Arize Phoenix MCP** (datasets + trazas) |
| Persistencia | **Firestore** (log operativo) · **Elastic** (memoria semántica con embeddings) |
| Observabilidad | **Arize Phoenix** + OpenTelemetry |
| Embeddings | **Vertex AI** `text-embedding-004` (768 dims) |
| Despliegue | **Cloud Run** + **Vertex AI Agent Engine** |
| Lenguaje | Python 3.11+ |

---

## 📦 Estructura del proyecto

```
Hackaton-Fake-News/
├── LICENSE                     # Apache 2.0
├── README.md
├── PLAN.md                     # decisiones de arquitectura
├── IMPLEMENTATION.md           # hoja de ruta
├── .env.example                # plantilla de credenciales
├── requirements.txt
├── Dockerfile                  # Cloud Run (Playwright 1.49 + uvicorn)
│
├── main.py                     # FastAPI + ADK root_agent  ← núcleo actual
├── scraper.py                  # Bright Data Scraping Browser
├── esquema_datos.json          # mapping Elastic (referencia futura)
│
├── agent/
│   ├── tools/                  # esqueleto multi-paso (en progreso)
│   │   ├── embeddings.py       # ✅ Vertex AI text-embedding-004
│   │   ├── triage.py           # 🟡 stub
│   │   ├── extractor.py        # 🟡 stub
│   │   ├── claim_parser.py     # 🟡 stub
│   │   ├── source_checker.py   # 🟡 stub
│   │   ├── cross_reference.py  # 🟡 stub
│   │   ├── linguistic.py       # 🟡 stub
│   │   ├── verdict.py          # 🟡 stub
│   │   └── persistence.py      # 🟡 stub
│   ├── mcp/
│   │   └── local_cache.py      # caché local (puente hasta Elastic)
│   └── prompts/                # claim_parser.es · linguistic.es · verdict.es
│
├── frontend/
│   └── app.py                  # chat Streamlit
│
├── scripts/
│   ├── setup_firestore.py      # ✅ permisos + config doc
│   ├── setup_elastic_index.py  # 🟡 stub (mapping definido)
│   └── seed_factcheckers.py    # 🟡 stub (lista definida)
│
└── tests/
    ├── test_triage.py          # xfail hasta implementar la tool
    └── test_verdict.py         # xfail hasta implementar la tool
```

---

## 🚀 Instalación

### Requisitos previos
- **Python 3.11+** (el proyecto usa wheels compatibles con 3.11–3.14)
- **gcloud CLI** ([instalación](https://cloud.google.com/sdk/docs/install))
- Cuenta en **Bright Data** (Scraping Browser endpoint)
- Cuenta en **Arize Phoenix** (API key)
- Acceso a un proyecto de **Google Cloud** con Vertex AI y Firestore habilitados

### Pasos

```bash
# 1. Clonar
git clone https://github.com/mariana-ruge/Hackaton-Fake-News.git
cd Hackaton-Fake-News

# 2. Entorno virtual
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Dependencias
pip install -r requirements.txt
playwright install chromium  # solo si vas a usar scraper.py local

# 4. Autenticación a Gemini (elige UN modo, ver siguiente sección)
#    Modo A (recomendado): gcloud auth application-default login + ADC
#    Modo B (rápido):      pon GOOGLE_API_KEY en .env

# 5. Variables de entorno
cp .env.example .env
#   → revisa la cabecera de Gemini y elige el modo
#   → rellena ELASTIC_*, BRIGHTDATA_API_TOKEN, API_KEY_PHOENIX

# 6. (Opcional) Inicializar Firestore + Elastic + factcheckers
python scripts/setup_firestore.py
python scripts/setup_elastic_index.py
python scripts/seed_factcheckers.py
```

### 🔐 Dos modos de autenticación a Gemini

| | **Modo A · Vertex AI (ADC)** | **Modo B · API key directa** |
|---|---|---|
| **Cuándo usar** | Producción, cuentas corporativas, despliegue | Demos locales, jueces, devs casuales |
| **Pre-requisito** | `gcloud auth application-default login` | API key de [AI Studio](https://aistudio.google.com/app/apikey) |
| **Variables clave** | `GOOGLE_GENAI_USE_VERTEXAI=True` + `GOOGLE_CLOUD_PROJECT` | `GOOGLE_GENAI_USE_VERTEXAI=False` + `GOOGLE_API_KEY` |
| **Cloud Run / Agent Engine** | ✅ | ❌ (solo local) |
| **Firestore** | ✅ | ⚠️ Solo si también pones `GOOGLE_CLOUD_PROJECT` con permisos |
| **Lo verás en `/health`** | `"auth_mode": "vertex_adc"` | `"auth_mode": "api_key"` |

> **Política org:** Si tu organización **bloquea API keys** (caso del proyecto Hackaton-498600), usa **modo A**.
> **Resto:** los dos funcionan igual de bien para el pipeline; **Bright Data, Elastic y Phoenix MCP son agnósticos al modo**.

### Variables de entorno principales

| Variable | Obligatoria | Descripción |
|---|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | ✅ | `True` (ADC) o `False` (API key) |
| `GOOGLE_CLOUD_PROJECT` | ✅ en modo A | ID del proyecto de Google Cloud |
| `GOOGLE_CLOUD_LOCATION` | ✅ en modo A | Región (`us-central1` por defecto) |
| `GOOGLE_API_KEY` | ✅ en modo B | API key de AI Studio |
| `MODEL_NAME` | ✅ | Modelo de Gemini (`gemini-2.5-flash` por defecto) |
| `EMBEDDING_MODEL` | ✅ | `text-embedding-004` (768 dims) |
| `ELASTIC_API_KEY` + `ELASTIC_URL`/`ELASTIC_CLOUD_ID` | 🟢 | Track partner del reto |
| `BRIGHTDATA_API_TOKEN` | ✅ | Para `/scrape` y búsqueda |
| `API_KEY_PHOENIX` | ⚠️ Recomendada | Habilita telemetría + Phoenix MCP |

---

## ▶️ Uso

### Backend (FastAPI)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- `POST /analizar` — recibe `{"texto_noticia": "..."}` y devuelve el análisis.
- `POST /scrape`   — recibe `{"url": "..."}` y devuelve el texto limpio.
- `GET  /health`   — estado de Vertex AI, Firestore, Phoenix, MCPs.

### Frontend (Streamlit)
```bash
streamlit run frontend/app.py
```
Abre `http://localhost:8501` y empieza a chatear. El frontend asume que el backend corre en `http://localhost:8000` (configurable con `API_URL`).

### Tests
```bash
pytest -q
```
Los tests de tools aún en stub están marcados como `xfail` — `pytest` no fallará.

---

## 🎬 Demo

> _(pendiente — se añadirá GIF/enlace al video de ~3 min y la URL pública tras el despliegue)_

---

## 📚 Documentación

Antes de tomar decisiones arquitectónicas, consulta:

- **[`docs/architecture.md`](./docs/architecture.md)** — vista actual del sistema con diagramas mermaid (flujo, datos, triage, componentes, auth).
- **[`docs/adr/`](./docs/adr/)** — historial de decisiones arquitectónicas (ADRs) con su porqué. Léelo cuando dudes de *"¿por qué se hizo así?"*.
- **[`PLAN.md`](./PLAN.md)** — decisiones de alto nivel y arquitectura objetivo.
- **[`IMPLEMENTATION.md`](./IMPLEMENTATION.md)** — hoja de ruta operativa por fases.

> ⚠️ Antes de implementar algo que afecte a más de un módulo, sea difícil de revertir, introduzca una dependencia importante, establezca un patrón nuevo, o que en 3 meses alguien preguntaría *"¿por qué hicimos esto así?"* → **propón un ADR** siguiendo la plantilla en [`docs/adr/README.md`](./docs/adr/README.md).

## 🗺️ Roadmap

El detalle por fases está en **[`IMPLEMENTATION.md`](./IMPLEMENTATION.md)**.

- [x] Cimientos del repo + LICENSE
- [x] Agente reactivo con ADK + GoogleSearch + URL Context
- [x] Backend FastAPI + Firestore (log) + telemetría Phoenix
- [x] Frontend Streamlit
- [x] Bright Data Scraping Browser como puente provisional
- [ ] 🟢 **Track Elastic**: Elastic MCP + índice `verified_claims` + triage semántico
- [ ] Migrar de Brave + Fetch + Scraping Browser → **Bright Data MCP oficial**
- [ ] **Arize Phoenix MCP** como bonus partner (consulta de datasets/trazas)
- [ ] Refactor a flujo **multi-paso determinista** (`agent/tools/`)
- [ ] Despliegue en Cloud Run + Agent Engine
- [ ] Demo + entrega Devpost

---

## ⚠️ Limitaciones y uso responsable

- VeritasAgent es una **herramienta de apoyo**, **no es asesor financiero**.
- Los análisis incluyen riesgo / banderas rojas pero **no dictan decisiones de inversión**.
- La calidad depende de las fuentes disponibles; si no hay cobertura rigurosa, el agente lo dice claramente.
- Para promesas de inversión en redes sociales, ante cualquier duda → **consulta a un asesor regulado**.

---

## 📄 Licencia

Distribuido bajo la **Licencia Apache 2.0**. Ver [`LICENSE`](./LICENSE).

---

<div align="center">

Construido para el reto **Google Cloud Agent Builder + Partner MCP**.

</div>
