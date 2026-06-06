# VeritasAgent — Plan de Implementación (paso a paso)

> Hoja de ruta operativa: qué construir, en qué orden, con qué criterio de "hecho".
> Las decisiones de arquitectura viven en `PLAN.md`. Aquí solo se **ejecuta**.

**Repo raíz:** `D:\Trabajos u\Proyectos\agentes-cloud\Hackaton-Fake-News`
**Dominio:** Fake news financieras (desinformación económica, esquemas Ponzi, promesas de inversión sospechosas).
**Stack objetivo:** Gemini 2.5 Flash · Google ADK · Vertex AI (ADC) · FastAPI · Streamlit (Cloud Run) · **Firestore (log) + Elastic (memoria semántica)** · **Bright Data MCP** · **Elastic MCP** 🟢 (track) · **Arize Phoenix MCP** (bonus).

**Track del reto:** 🟢 **Elastic** (`Pick one and build with their MCP server`).

---

## Leyenda de estado
- `[ ]` pendiente · `[~]` en progreso · `[x]` hecho · `[!]` bloqueado/riesgo

---

## FASE 0 — Cimientos del repo
- [x] **0.1** `LICENSE` (Apache 2.0).
- [x] **0.2** `PLAN.md`.
- [x] **0.3** Repo en `Hackaton-Fake-News`.
- [x] **0.4** Estructura de carpetas.
- [x] **0.5** `README.md`.
- [x] **0.6** `.gitignore`.
- [x] **0.7** `.env.example` unificado (ADC + Phoenix + Bright Data + Elastic + Firestore + Brave).
- [x] **0.8** `requirements.txt` consolidado (ADK 1.14, Vertex AI, FastAPI, Phoenix, Playwright, Elastic, pytest).
- [x] **0.9** Repo público en GitHub: `mariana-ruge/Hackaton-Fake-News`.

---

## FASE 0.5 — Setup de Google Cloud
> ⚠️ Con ADK el agente vive en código. Esta fase prepara el terreno (proyecto + APIs + auth). El agente se despliega a Agent Engine en la Fase 6.

- [x] **0.5.1** Proyecto `hackaton-498600` creado.
- [ ] **0.5.2** Vincular cuenta de facturación.
- [ ] **0.5.3** Habilitar APIs (`aiplatform`, `run`, `secretmanager`, `cloudbuild`, `artifactregistry`, `firestore`).
- [ ] **0.5.4** ADC localmente (la org **bloquea API keys**).
  ```bash
  gcloud auth login
  gcloud auth application-default login
  gcloud auth application-default set-quota-project hackaton-498600
  ```
- [ ] **0.5.5** Región por defecto (`us-central1`).
- [ ] **0.5.6** Service Account `veritas-agent` (Vertex AI User + Secret Manager Accessor).
- [ ] **0.5.7** Rellenar `.env` (`GOOGLE_CLOUD_PROJECT=hackaton-498600`).

---

## FASE 1 — Conectividad y datos
- [x] **1.1** `agent/tools/embeddings.py` — Vertex AI `text-embedding-004` (768 dims, cache LRU, retries).
- [x] **1.2** `scraper.py` — Bright Data Scraping Browser (Playwright + CDP).
- [x] **1.3** `agent/mcp/local_cache.py` — caché local para iterar sin Elastic.
- [x] **1.4** `scripts/setup_firestore.py` — verifica permisos + escribe `config/veritas_settings`.
- [ ] **1.5** `scripts/setup_elastic_index.py` — **STUB**, implementar inserción real con `elasticsearch-py`.
- [ ] **1.6** `scripts/seed_factcheckers.py` — **STUB**, implementar inserción real (lista lista pero no se persiste).
- [ ] **1.7** `agent/mcp/elastic_client.py` — **falta**, conexión + búsqueda híbrida (kNN + BM25).

---

## FASE 2 — Tools del agente (núcleo)
> Estas tools son el esqueleto del refactor a multi-paso determinista. **Para la entrega actual `main.py` define un único LlmAgent reactivo que cubre todo de forma orgánica.**

- [ ] **2.1** `tools/triage.py` — **STUB**, busca claim en Elastic, decide early-exit.
- [ ] **2.2** `tools/extractor.py` — **STUB**, refactor mover `scraper.py` aquí.
- [x] **2.3a** Prompt `prompts/claim_parser.es.txt` — listo.
- [ ] **2.3b** `tools/claim_parser.py` — **STUB**, cablear el prompt con Gemini.
- [ ] **2.4** `tools/source_checker.py` — **STUB**.
- [ ] **2.5** `tools/cross_reference.py` — **STUB**.
- [x] **2.6a** Prompt `prompts/linguistic.es.txt` — listo.
- [ ] **2.6b** `tools/linguistic.py` — **STUB**, cablear el prompt con Gemini.
- [x] **2.7a** Prompt `prompts/verdict.es.txt` — listo.
- [ ] **2.7b** `tools/verdict.py` — **STUB**, cablear el prompt con Gemini.
- [ ] **2.8** `tools/persistence.py` — **STUB**. Hoy persistimos en Firestore desde `main.py`.

---

## FASE 3 — Orquestación del agente
- [x] **3.1** `main.py` — `root_agent` con GoogleSearch + URL Context + Brave + Fetch.
- [x] **3.2** Endpoints FastAPI `/analizar`, `/scrape`, `/health` (lifespan moderno).
- [x] **3.3** Persistencia automática a Firestore por cada análisis y scrape.
- [x] **3.4** Telemetría Phoenix instrumentando ADK.
- [ ] **3.5** **(refactor pendiente)** orquestación multi-paso con triage + early-exit + escalado.

---

## FASE 4 — Pruebas
- [x] **4.1** `tests/test_triage.py` — marcado `xfail` hasta que la tool se implemente.
- [x] **4.2** `tests/test_verdict.py` — marcado `xfail` hasta que la tool se implemente.
- [ ] **4.3** `tests/fixtures/` — claims reales (titulares económicos verdaderos / falsos / engañosos).
- [ ] **4.4** Test end-to-end de `/analizar` con un caso real.

---

## FASE 5 — Frontend (Streamlit)
- [x] **5.1** `frontend/app.py` — chat consumiendo `/analizar` con healthcheck en cabecera.
- [x] **5.2** Estilos custom + chips de estado (Vertex AI, Firestore, proyecto).
- [x] **5.3** Persistencia visual del análisis y `firestore_doc_id`.
- [ ] **5.4** Mostrar pasos del agente en vivo (requiere refactor multi-paso de la Fase 3.5).

---

## FASE 6 — Despliegue (Google Cloud)
- [x] **6.1** `Dockerfile` (Playwright 1.49 + Python + uvicorn).
- [ ] **6.2** `cloudbuild.yaml` para Cloud Run.
- [ ] **6.3** Secret Manager para `API_KEY_PHOENIX`, `BRIGHT_DATA_WS_URL`, `BRAVE_API_KEY`.
- [ ] **6.4** Desplegar el agente a Vertex AI Agent Engine.
- [ ] **6.5** Cloud Run para el backend FastAPI y otro servicio para Streamlit.
- [ ] **6.6** Verificación end-to-end con URL pública.

---

## FASE 7 — Entrega del concurso
- [ ] **7.1** README con GIF/captura + URL hosted.
- [x] **7.2** `LICENSE` Apache 2.0 visible en *About*.
- [ ] **7.3** Demo ~3 min: caso viral económico → análisis → veredicto.
- [ ] **7.4** Formulario Devpost.
- [ ] **7.5** Track: agente funcional con MCP de partner.

---

## ⚠️ Riesgos abiertos para el reto

| ID | Riesgo | Estado | Mitigación |
|---|---|---|---|
| **R1** | Ningún MCP usado es de partner del reto | 🟡 En progreso | Track elegido: **Elastic** (paso [0]/[7]). Bonus: **Arize Phoenix MCP** ya con Phoenix activo |
| **R2** | El agente no es multi-paso real | 🔴 Abierto | Implementar `tools/triage.py` → `verdict.py` + orquestador en `main.py` (Fase 8) |
| **R3** | No hay caché semántica con Elastic | 🔴 Abierto | Resolver en Fase 8 (triage + index real) |
| **R4** | README ya alineado a finanzas | ✅ Resuelto | — |
| **R5** | Brave + Fetch no aportan al track | 🟡 A retirar | Sustituir por Bright Data MCP oficial (cubre fetch+search) |

---

## FASE 8 — Migración a la arquitectura definitiva (decisión Opción B)
> Objetivo: cumplir el track Elastic, sumar Phoenix MCP como bonus partner, y dejar Firestore como log operativo (NO como memoria semántica).

### 8.1 — Elastic MCP (track partner) 🟢
- [ ] **8.1.1** Crear cluster en **Elastic Cloud** (free trial 14 días — suficiente para el reto).
- [ ] **8.1.2** Añadir a `requirements.txt`: cliente del MCP oficial (`elasticsearch` ya está; se añade el toolset MCP en `main.py`).
- [ ] **8.1.3** Implementar `scripts/setup_elastic_index.py` real → crea índice `verified_claims` con el mapping de `esquema_datos.json` (dense_vector 768).
- [ ] **8.1.4** Conectar **Elastic MCP** en `main.py` como `MCPToolset` del agente.
- [ ] **8.1.5** Implementar `agent/tools/triage.py` → usa el MCP para búsqueda híbrida + umbrales 0.92 / 0.75.
- [ ] **8.1.6** Implementar `agent/tools/persistence.py` → indexa el veredicto consolidado en Elastic.
- [ ] **8.1.7** Migrar `agent/mcp/local_cache.py` a usar Elastic (queda como fallback offline).

### 8.2 — Bright Data MCP (sustituye Brave + Fetch + scraper.py)
- [ ] **8.2.1** Cuenta + endpoint del **Bright Data MCP** oficial.
- [ ] **8.2.2** En `main.py`: añadir `MCPToolset` de Bright Data y **retirar** `brave_toolset` y `fetch_toolset`.
- [ ] **8.2.3** Limpiar `scraper.py` (queda solo como referencia o se borra).
- [ ] **8.2.4** Actualizar `.env.example`: quitar `BRAVE_API_KEY` y `BRIGHT_DATA_WS_URL`, añadir `BRIGHTDATA_MCP_*`.
- [ ] **8.2.5** Actualizar `requirements.txt`: quitar `mcp-server-fetch` (lo cubre Bright Data MCP).

### 8.3 — Arize Phoenix MCP (bonus partner)
- [ ] **8.3.1** Crear un **dataset en Phoenix** con ~10 ejemplos curados de claims financieros (verdaderos/engañosos/falsos).
- [ ] **8.3.2** Añadir `arize-phoenix-mcp` a `requirements.txt`.
- [ ] **8.3.3** Conectar **Phoenix MCP** en `main.py` como `MCPToolset` para que el agente consulte el dataset en el paso [6].
- [ ] **8.3.4** Documentar en README cómo se reciclan trazas / datasets vía MCP.

### 8.4 — Persistencia doble capa (decisión Opción B)
- [ ] **8.4.1** Firestore → **solo log de requests** (input + output + timestamp + doc_id). Ya está implementado, mantener.
- [ ] **8.4.2** Elastic → **memoria semántica** (claim_text + embedding + verdict + evidence). Implementado en 8.1.
- [ ] **8.4.3** En `/health` añadir el estado de **Elastic** y de los 3 MCPs.

### 8.5 — Refactor multi-paso (resuelve R2)
- [ ] **8.5.1** En `main.py`: definir `root_agent` con **sub-agentes secuenciales** (uno por paso) en vez de un `LlmAgent` reactivo.
- [ ] **8.5.2** Cablear cada `agent/tools/<paso>.py` como tool del sub-agente correspondiente.
- [ ] **8.5.3** Lógica de early-exit en orquestador (no en el LLM): si triage `score≥0.92` → return cacheado.
- [ ] **8.5.4** Frontend Streamlit: mostrar los pasos en vivo (requiere streaming desde FastAPI).

### Criterios de hecho de la Fase 8
- `pytest` pasa (los `xfail` empiezan a pasar de verdad).
- `/analizar` con un claim nuevo recorre los 7 pasos visibles en Phoenix.
- `/analizar` con un claim repetido devuelve early-exit en <2 s.
- `/health` reporta `elastic_mcp`, `brightdata_mcp` y `phoenix_mcp` como `connected`.

---

## Orden de ataque sugerido (próximos pasos)

1. **8.1.1 + 8.1.3** — Crear cluster Elastic e implementar `setup_elastic_index.py`. (2 h)
2. **8.1.4 + 8.1.5** — Cablear Elastic MCP en `main.py` y `triage.py`. (3 h)
3. **8.2.1 + 8.2.2** — Migrar a Bright Data MCP. (3 h)
4. **8.3.x** — Phoenix MCP + dataset. (2 h)
5. **8.5.x** — Refactor multi-paso. (1 día)
6. **Fase 6** — Despliegue.
7. **Fase 7** — Demo + Devpost.

**Tiempo total estimado de la Fase 8:** ~3 días de trabajo enfocado.
