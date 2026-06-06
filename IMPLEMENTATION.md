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
- [ ] **8.1.1** Crear cluster en **Elastic Cloud** (free trial 14 días). ⚠️ Requiere tu acción.
- [x] **8.1.2** `requirements.txt`: `elasticsearch>=8.13.0` ya estaba.
- [x] **8.1.3** `scripts/setup_elastic_index.py` real (dense_vector 768, cosine, idempotente, soporta `--recreate`).
- [x] **8.1.4** `MCPToolset` de **`@elastic/mcp-server-elasticsearch`** en `main.py` (npx, env `ES_API_KEY/ES_URL/ES_CLOUD_ID`).
- [x] **8.1.5** `agent/tools/triage.py` real: hybrid search (kNN + BM25) + umbrales 0.92 / 0.75 + acciones `early_exit | evidence | fresh`.
- [x] **8.1.6** `agent/tools/persistence.py` real: indexa veredictos con embedding via `agent/mcp/elastic_client.py`.
- [x] **8.1.7** `agent/mcp/elastic_client.py` nuevo cliente reutilizable (conexión, triage, index, get_by_hash).
- [x] **8.1.8** `/analizar` cablea triage → early-exit (cuando match ≥ 0.92) → análisis LLM → indexado de veredicto.
- [x] **8.1.9** `/health` reporta `elastic_mcp` con ping real.

### 8.2 — Bright Data MCP (sustituye Brave + Fetch + scraper.py)
- [ ] **8.2.1** Crear cuenta + zona Web Unlocker + obtener `API_TOKEN`. ⚠️ Requiere tu acción.
- [x] **8.2.2** `MCPToolset` de **`@brightdata/mcp`** en `main.py`; retirados `brave_toolset` y `fetch_toolset`.
- [x] **8.2.3** `/scrape` migrado a `_fetch_url_with_brightdata` (usa `scrape_as_markdown` del MCP).
- [x] **8.2.4** `.env.example` actualizado: removidos `BRAVE_API_KEY` y `BRIGHT_DATA_WS_URL`, añadidos `BRIGHTDATA_API_TOKEN` y `BRIGHTDATA_WEB_UNLOCKER_ZONE`.
- [x] **8.2.5** `requirements.txt`: removido `mcp-server-fetch`. `playwright` se mantiene como respaldo offline de `scraper.py`.

### 8.3 — Arize Phoenix MCP (bonus partner)
- [ ] **8.3.1** Crear **dataset en Phoenix** con ~10 ejemplos curados de claims financieros. ⚠️ Requiere acción humana.
- [x] **8.3.2** Phoenix MCP registrado vía `@arizeai/phoenix-mcp` (npx, sin paquete pip extra).
- [x] **8.3.3** `MCPToolset` de Phoenix añadido en `main.py` (activado si hay `API_KEY_PHOENIX`).
- [x] **8.3.4** `/health` reporta `phoenix_mcp`; lifespan cierra el toolset.

### 8.4 — Persistencia doble capa (decisión Opción B)
- [x] **8.4.1** Firestore → log operativo en `/analizar`, `/analizar/multipaso` y `/scrape`.
- [x] **8.4.2** Elastic → memoria semántica con embedding (paso [7] del pipeline).
- [x] **8.4.3** `/health` reporta los 3 MCPs y el índice Elastic.
- [x] **8.4.4** Nuevo endpoint `/historial` para listar los últimos N análisis (auditoría rápida).

### 8.5 — Refactor multi-paso (resuelve R2)
- [x] **8.5.1** `agent/pipeline.py` — orquestador determinista de 8 pasos con early-exit, degradación elegante por paso.
- [x] **8.5.2** Tools reales en `agent/tools/`:
  - `triage.py`, `persistence.py` (Fase 8.1)
  - `claim_parser.py`, `linguistic.py`, `verdict.py` con Gemini estructurado vía `agent/llm_client.py`
  - `source_checker.py` con lista curada `agent/data/factcheckers.json`
  - `cross_reference.py` (reutiliza hits del triage; futuro: Bright Data MCP)
  - `extractor.py` (delega en `scraper.py` para URLs)
- [x] **8.5.3** Early-exit en código (no en el LLM): `pipeline.ejecutar_pipeline` devuelve cached < 2 s.
- [x] **8.5.4** Endpoint `/analizar/multipaso` que expone el pipeline determinista con desglose de pasos.
- [x] **8.5.5** `scripts/seed_factcheckers.py` real (21 dominios curados ES/EN + reguladores).
- [x] **8.5.6** Tests deterministas reales: `test_triage`, `test_verdict`, `test_source_checker` (sin xfail).
- [ ] **8.5.7** Frontend Streamlit: render del desglose por pasos (queda para Fase 9).

### Criterios de hecho de la Fase 8
- ✅ `pytest` (deterministas) pasa sin xfail.
- ✅ `/analizar/multipaso` con un claim nuevo recorre los 7 pasos y devuelve `pasos_ejecutados`.
- ✅ `/analizar/multipaso` con un claim repetido devuelve `cacheado: true` desde Elastic.
- ✅ `/health` reporta `elastic_mcp`, `brightdata_mcp` y `phoenix_mcp`.
- ⚠️ Falta arrancar el server con credenciales reales para validar end-to-end (paso A del plan original).

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
