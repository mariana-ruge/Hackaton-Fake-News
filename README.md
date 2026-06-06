<div align="center">

# 🛡️ VeritasAgent

### Agente multi-paso de verificación de noticias (fake news) con evidencia rastreable

**Powered by Gemini · Google Cloud (ADK + Vertex AI Agent Engine) · Bright Data MCP · Elastic MCP**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5-8E75B2.svg)](https://ai.google.dev/)

[Demo](#-demo) · [Arquitectura](#-arquitectura) · [Cómo funciona](#-cómo-funciona) · [Instalación](#-instalación) · [Roadmap](./IMPLEMENTATION.md)

</div>

---

## 📰 El problema

Las noticias falsas se propagan **6 veces más rápido** que las verdaderas. Los verificadores humanos no dan abasto, y las herramientas existentes suelen:

- Limitarse a responder *"verdadero/falso"* sin mostrar **por qué**.
- Cubrir mal el contenido en **español / LatAm**.
- Re-analizar el mismo bulo viral una y otra vez, gastando tiempo y recursos.

## 💡 La solución

**VeritasAgent** no es un chatbot. Es un **agente autónomo multi-paso** que recibe una **URL, un titular o una afirmación**, ejecuta un flujo de investigación, y devuelve un **veredicto con nivel de confianza y evidencia enlazada**.

Su diferenciador clave es una **fase de triage con búsqueda semántica (Elastic)**: antes de gastar recursos, comprueba si el bulo **ya fue verificado** y, si hay coincidencia fuerte, responde al instante (*early-exit*).

> ⚖️ **Principio rector:** el agente **nunca opina** — siempre cita fuentes. Si no hay evidencia, lo dice ("Sin evidencia suficiente"), nunca inventa un veredicto absoluto.

---

## ✨ Características

| | |
|---|---|
| 🧠 **Multi-paso real** | El agente planifica y decide cuándo profundizar (no es un único prompt) |
| ⚡ **Triage con early-exit** | Búsqueda semántica en Elastic evita re-analizar bulos ya verificados (<2 s) |
| 🌎 **Bilingüe ES/EN** | Cubre fact-checkers de LatAm, poco atendidos en inglés |
| 🔍 **Evidencia rastreable** | Cada veredicto incluye enlaces a las fuentes que lo apoyan o contradicen |
| 🙋 **Human-in-the-loop** | El usuario puede pedir "explica por qué" o re-verificar ignorando la caché |
| 📈 **Memoria que aprende** | Cada verificación alimenta el triage futuro |

---

## 🏗️ Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend · Streamlit (Cloud Run)                            │
│  Input: URL / titular / claim   |   Idioma: ES / EN          │
│  Muestra pasos en vivo + veredicto + evidencia               │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼──────────────────────────────────┐
│  Agente · ADK en Vertex AI Agent Engine · Gemini 2.5         │
│                                                              │
│   [0] Triage (Elastic)  ──► early-exit si match fuerte       │
│   [1] Extractor (Bright Data)                                │
│   [2] Claim Parser (Gemini)                                  │
│   [3] Source Checker                                          │
│   [4] Cross-Reference (Bright Data)                          │
│   [5] Linguistic Analysis (Gemini)                           │
│   [6] Verdict (Gemini)                                        │
│   [7] Persist / Index (Elastic)                              │
└───────┬───────────────────────────────────┬──────────────────┘
        │                                   │
┌───────▼─────────┐                 ┌────────▼─────────┐
│  Bright Data MCP │                 │   Elastic MCP    │
│  scraping + web  │                 │  kNN + BM25 +    │
│  (News, Reuters, │                 │  memoria de      │
│  fact-checkers)  │                 │  verificaciones  │
└──────────────────┘                 └───────────────────┘
```

### 🤝 Integración de partners (MCP)

| Partner | Rol | Superpoder que aporta |
|---|---|---|
| **Bright Data MCP** | Extracción y búsqueda web | Acceso a la fuente original y a fact-checkers sorteando bloqueos anti-bot |
| **Elastic MCP** | Triage semántico + memoria | Búsqueda híbrida (vectorial + léxica) para caché inteligente y recuperación de evidencia |

---

## 🔬 Cómo funciona

El agente ejecuta hasta 8 pasos. El triage decide si hace falta todo el flujo:

| Paso | Tool | Qué hace |
|---|---|---|
| **[0] Triage** | `triage_claim` (Elastic) | Busca el claim por similitud. `score≥0.92` → **early-exit** cacheado |
| **[1] Extractor** | `fetch_article` (Bright Data) | Si es URL, extrae título, cuerpo, autor, fecha y dominio |
| **[2] Claim Parser** | `extract_claims` (Gemini) | Descompone el texto en afirmaciones atómicas verificables |
| **[3] Source Checker** | `check_source_reputation` | Evalúa la reputación del dominio (lista curada + heurísticas) |
| **[4] Cross-Reference** | `search_factcheckers` / `search_trusted_news` (Bright Data) | Busca cada claim en Snopes, AFP, Maldita, Reuters, AP… |
| **[5] Linguistic** | `analyze_language` (Gemini) | Detecta sensacionalismo, clickbait y carga emocional |
| **[6] Verdict** | `build_verdict` (Gemini) | Sintetiza todo en score 0–100 + categoría + confianza |
| **[7] Persist** | `index_verification` (Elastic) | Guarda el caso para alimentar futuros triages |

### Umbrales del triage

```
score >= 0.92          → EARLY EXIT  (mismo claim ya verificado → reusa veredicto)
0.75 <= score < 0.92   → usa los hits como EVIDENCIA, corre el flujo completo
score <  0.75          → flujo completo desde cero
```

> 🔒 **Regla de seguridad:** el early-exit **solo** aplica a claims que *nosotros ya verificamos* (caché propio). Parecerse a una noticia real **no** prueba que sea verdad — las fake news imitan noticias reales. Elastic dice *"es similar a X"*, nunca *"es verdad"*.

### Formato del veredicto

```json
{
  "score": 0-100,
  "category": "Verdadero | Engañoso | Falso | Sin evidencia suficiente",
  "confidence": "alta | media | baja",
  "reasoning": "explicación bilingüe",
  "evidence": [
    { "source": "Reuters", "url": "https://...", "stance": "contradice" }
  ]
}
```

---

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| Razonamiento | **Gemini 2.5** |
| Orquestación | **Agent Development Kit (ADK)** |
| Despliegue del agente | **Vertex AI Agent Engine** |
| Frontend | **Streamlit** en **Cloud Run** |
| Memoria / búsqueda | **Elastic Cloud** (MCP) |
| Extracción web | **Bright Data** (MCP) |
| Secretos | **Google Secret Manager** |
| Lenguaje | **Python 3.11+** |

---

## 📦 Estructura del proyecto

```
Hackaton-Fake-News/
├── LICENSE                     # Apache 2.0
├── README.md                   # este archivo
├── PLAN.md                     # decisiones de arquitectura y técnicas
├── IMPLEMENTATION.md           # hoja de ruta paso a paso
├── .env.example                # plantilla de credenciales
├── requirements.txt
├── Dockerfile                  # imagen para Cloud Run
├── cloudbuild.yaml             # CI/CD
│
├── agent/                      # lógica del agente (ADK)
│   ├── root_agent.py           # define el agente y registra las tools
│   ├── config.py               # modelo, umbrales, idiomas
│   ├── tools/                  # los 8 pasos del flujo
│   ├── mcp/                    # clientes Bright Data y Elastic
│   └── prompts/                # prompts ES/EN por paso
│
├── frontend/
│   └── app.py                  # interfaz Streamlit
│
├── scripts/
│   ├── setup_elastic_index.py  # crea el índice verified_claims
│   └── seed_factcheckers.py    # lista curada de dominios/reputación
│
└── tests/
    ├── test_triage.py
    ├── test_verdict.py
    └── fixtures/
```

---

## 🚀 Instalación

> ⚠️ Proyecto en construcción — ver el progreso en [`IMPLEMENTATION.md`](./IMPLEMENTATION.md).

### Requisitos previos
- Python 3.11+
- Una cuenta de **Google Cloud** con Vertex AI habilitado
- Credenciales de **Bright Data** y **Elastic Cloud**

### Pasos

```bash
# 1. Clonar
git clone https://github.com/<usuario>/Hackaton-Fake-News.git
cd Hackaton-Fake-News

# 2. Entorno virtual
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Configurar credenciales
cp .env.example .env
#   → rellenar GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT,
#     BRIGHTDATA_API_KEY, ELASTIC_CLOUD_ID, ELASTIC_API_KEY

# 5. Crear el índice de Elastic
python scripts/setup_elastic_index.py

# 6. (opcional) Cargar fact-checkers de referencia
python scripts/seed_factcheckers.py
```

### Variables de entorno

| Variable | Descripción |
|---|---|
| `GEMINI_API_KEY` | Clave de la API de Gemini / Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | ID del proyecto de Google Cloud |
| `BRIGHTDATA_API_KEY` | Clave de Bright Data MCP |
| `ELASTIC_CLOUD_ID` | ID del cluster de Elastic Cloud |
| `ELASTIC_API_KEY` | Clave de la API de Elastic |

---

## ▶️ Uso

### Local (frontend)
```bash
streamlit run frontend/app.py
```
Abre `http://localhost:8501`, elige idioma, pega una URL/titular/claim y observa al agente trabajar paso a paso.

### Tests
```bash
pytest
```

---

## 🎬 Demo

> _(pendiente — se añadirá GIF/enlace al video de ~3 min y la URL pública tras el despliegue)_

---

## 🗺️ Roadmap

El plan de implementación detallado, por fases y con criterios de "hecho", está en **[`IMPLEMENTATION.md`](./IMPLEMENTATION.md)**.

- [x] Decisiones de arquitectura (`PLAN.md`)
- [x] Licencia Apache 2.0
- [x] Cimientos del repo
- [ ] Conectividad MCP (Bright Data + Elastic)
- [ ] Tools del agente
- [ ] Orquestación
- [ ] Frontend Streamlit
- [ ] Despliegue en Google Cloud
- [ ] Demo y entrega Devpost

---

## ⚠️ Limitaciones y uso responsable

- VeritasAgent es una **herramienta de apoyo**, no un árbitro final de la verdad.
- Los veredictos siempre incluyen **nivel de confianza** y **fuentes**: revísalas.
- La calidad depende de las fuentes disponibles; un claim sin cobertura se marca como *"Sin evidencia suficiente"*, no como falso.

---

## 📄 Licencia

Distribuido bajo la **Licencia Apache 2.0**. Ver [`LICENSE`](./LICENSE).

---

<div align="center">

Construido para el reto **Google Cloud Agent Builder + Partner MCP**.

</div>