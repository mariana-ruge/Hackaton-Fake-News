# VeritasAgent — Plan de Implementación (paso a paso)

> Hoja de ruta operativa: qué construir, en qué orden, con qué criterio de "hecho".
> Las decisiones de arquitectura viven en `PLAN.md`. Aquí solo se **ejecuta**.

**Repo raíz:** `D:\Trabajos u\Proyectos\agentes-cloud\Hackaton-Fake-News`
**Branch activa:** `Bright`
**Dominio:** Fake news financieras (desinformación económica, esquemas Ponzi, promesas de inversión sospechosas).
**Stack actual (rama Bright):** Gemini 2.5 Flash · Google ADK · Vertex AI / API key (auth dual) · FastAPI · Streamlit · **Firestore (log) + Elastic (memoria semántica)** · **Elastic MCP** 🟢 (track) · **Bright Data MCP** · **Arize Phoenix MCP** (bonus).

**Track del reto:** 🟢 **Elastic** (`Pick one and build with their MCP server`).
**Documentación arquitectónica:** [`docs/architecture.md`](docs/architecture.md) · [`docs/adr/`](docs/adr/) (12 ADRs).

> **Regla del documento:** cada tema vive en UNA sola fase (checkboxes canónicos).
> El "Runbook" final solo ordena referencias — no duplica checkboxes.

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
- [x] **1.1** `agent/tools/embeddings.py` — embeddings 768 dims agnósticos a Vertex/API key (ver ADR-0006), cache LRU + retries.
- [x] **1.2** `scraper.py` — Bright Data Scraping Browser (Playwright + CDP). **Queda como respaldo offline** desde la Fase 8.2.
- [x] **1.3** `agent/mcp/local_cache.py` — caché local (puente histórico, no se usa en producción tras 8.1.7).
- [x] **1.4** `scripts/setup_firestore.py` — verifica permisos + escribe `config/veritas_settings`.
- [x] **1.5** `scripts/setup_elastic_index.py` — **REAL** (implementado en 8.1.3): `dense_vector(768)`, idempotente, soporta `--recreate`.
- [x] **1.6** `scripts/seed_factcheckers.py` — **REAL** (implementado en 8.5.5): escribe `agent/data/factcheckers.json` con 21 dominios curados.
- [x] **1.7** `agent/mcp/elastic_client.py` — **CREADO** (8.1.7): conexión + `hybrid_search` (kNN + BM25) + `triage` con umbrales + `index_verification` + `get_by_hash`.

---

## FASE 2 — Tools del agente (núcleo)
> ✅ Las tools están **implementadas** y se usan desde `agent/pipeline.py` (endpoint `/analizar/multipaso`).
> El endpoint `/analizar` reactivo del LlmAgent sigue disponible en paralelo (decisión ADR-0010).

- [x] **2.1** `tools/triage.py` — **REAL** (8.5.2): genera embedding, búsqueda en Elastic (decisión por kNN, ver ADR-0007), devuelve `early_exit | evidence | fresh`.
- [x] **2.2** `tools/extractor.py` — **REAL** (`e8ba27c`): para URLs, cadena Bright Data MCP → `scraper.py` legado → texto crudo; reporta `extractor_usado`.
- [x] **2.3a** Prompt `prompts/claim_parser.es.txt`.
- [x] **2.3b** `tools/claim_parser.py` — **REAL** (8.5.2): Gemini con `response_mime_type=application/json`, devuelve lista de claims atómicos.
- [x] **2.4** `tools/source_checker.py` — **REAL** (8.5.2): consulta `agent/data/factcheckers.json` + heurísticas (TLD sospechoso, spoofing).
- [x] **2.5** `tools/cross_reference.py` — **REAL** (`e8ba27c`): memoria Elastic (hits del triage) + **búsqueda web por claim vía Bright Data MCP** (cap `CROSS_REFERENCE_MAX_SEARCHES`).
- [x] **2.6a** Prompt `prompts/linguistic.es.txt`.
- [x] **2.6b** `tools/linguistic.py` — **REAL** (8.5.2): scoring de alarmismo/sesgo/clickbait + banderas rojas.
- [x] **2.7a** Prompt `prompts/verdict.es.txt`.
- [x] **2.7b** `tools/verdict.py` — **REAL** (8.5.2): emite veredicto estructurado + mapeos `etiqueta→categoría` y `confianza→nivel`.
- [x] **2.8** `tools/persistence.py` — **REAL** (8.1.6): indexa el veredicto en Elastic con embedding (paso [7] del pipeline).

---

## FASE 3 — Orquestación del agente
- [x] **3.1** `main.py` — `root_agent` con GoogleSearch + URL Context + **Bright Data MCP + Elastic MCP + Phoenix MCP** (Brave/Fetch retirados en 8.2).
- [x] **3.2** Endpoints FastAPI `/analizar`, `/scrape`, `/health` (lifespan moderno).
- [x] **3.3** Persistencia automática a Firestore por cada análisis y scrape.
- [x] **3.4** Telemetría Phoenix instrumentando ADK.
- [x] **3.5** Orquestación multi-paso con triage + early-exit + degradación elegante — vive en `agent/pipeline.py` y se expone vía `POST /analizar/multipaso` (8.5.4). Decisión documentada en ADR-0010.

---

## FASE 4 — Pruebas
- [x] **4.1** `tests/test_triage.py` — **REAL** (8.5.6): `claim_hash` estable, umbrales coherentes, ping a Elastic con `skipif` por credenciales.
- [x] **4.2** `tests/test_verdict.py` — **REAL** (8.5.6): cobertura de mapeos y `confianza_a_nivel` con casos parametrizados.
- [x] **4.2b** `tests/test_source_checker.py` — **NUEVO** (8.5.6): dominio curado, desconocido, sin URL, TLD sospechoso.
- [ ] **4.3** `tests/fixtures/` — claims reales (titulares económicos verdaderos / falsos / engañosos).
- [ ] **4.4** Test end-to-end de `/analizar/multipaso` con un caso real (requiere credenciales).
- **4.5** Smoke test end-to-end (requiere `.env` real; valida también M8 — `task_type` en embeddings — y el parseo de la SERP):
  - [ ] **4.5.1** Arrancar backend + frontend localmente.
  - [ ] **4.5.2** `/health`: `auth_mode`, `vertex_ai`, `firestore`, `elastic_mcp`, `brightdata_mcp`, `phoenix_mcp` correctos.
  - [ ] **4.5.3** `/analizar/multipaso` con un Ponzi típico → veredicto + `pasos_ejecutados`.
  - [ ] **4.5.4** Repetir el mismo claim → `cacheado: true` y latencia <2 s.
  - [ ] **4.5.5** Confirmar logs en Firestore y doc en Elastic.

---

## FASE 5 — Frontend (Streamlit)
- [x] **5.1** `frontend/app.py` — chat consumiendo `/analizar` con healthcheck en cabecera.
- [x] **5.2** Estilos custom + chips de estado (Vertex AI, Firestore, proyecto).
- [x] **5.3** Persistencia visual del análisis y `firestore_doc_id`.
- **5.4** Mostrar el pipeline multipaso en la UI (la mejor carta de la demo):
  - [ ] **5.4.1** Toggle "Modo: reactivo / multipaso" que elige el endpoint.
  - [ ] **5.4.2** Render del desglose: `pasos_ejecutados`, `triage` (badge de early-exit), `fuente`, `linguistico`, evidencias.
  - [ ] **5.4.3** `etiqueta` con color (verde/ámbar/rojo) + `confianza_nivel`.
  - [ ] **5.4.4** Chips de estado de los 3 MCPs (ya disponibles en `/health`).

---

## FASE 8 — Migración a la arquitectura definitiva (decisión Opción B)
> ℹ️ **Numeración histórica**: esta fase se definió después de las Fases 6/7, pero su
> ejecución va ANTES del despliegue — por eso el documento la ubica aquí.
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
  - `cross_reference.py` (memoria Elastic + búsqueda web vía Bright Data MCP, `e8ba27c`)
  - `extractor.py` (Bright Data MCP → `scraper.py` legado → texto, `e8ba27c`)
- [x] **8.5.3** Early-exit en código (no en el LLM): `pipeline.ejecutar_pipeline` devuelve cached < 2 s.
- [x] **8.5.4** Endpoint `/analizar/multipaso` que expone el pipeline determinista con desglose de pasos.
- [x] **8.5.5** `scripts/seed_factcheckers.py` real (21 dominios curados ES/EN + reguladores).
- [x] **8.5.6** Tests deterministas reales: `test_triage`, `test_verdict`, `test_source_checker` (sin xfail).
- **8.5.7** Frontend con desglose por pasos → checklist canónico en **5.4** (sin checkbox aquí).

### Criterios de hecho de la Fase 8
- ✅ `pytest` (deterministas) pasa sin xfail.
- ✅ `/analizar/multipaso` con un claim nuevo recorre los 7 pasos y devuelve `pasos_ejecutados`.
- ✅ `/analizar/multipaso` con un claim repetido devuelve `cacheado: true` desde Elastic.
- ✅ `/health` reporta `elastic_mcp`, `brightdata_mcp` y `phoenix_mcp`.
- ⚠️ Falta arrancar el server con credenciales reales para validar end-to-end (smoke test 4.5).

---

## FASE 6 — Despliegue (Google Cloud)
- [x] **6.1** `Dockerfile` del backend (Playwright 1.49 + Node 20 para los MCPs + uvicorn).
- [ ] **6.2** `cloudbuild.yaml` para Cloud Run (backend FastAPI).
- [ ] **6.3** `Dockerfile`/servicio para **Streamlit** (separado del backend).
- [ ] **6.4** **Secret Manager** para `API_KEY_PHOENIX`, `ELASTIC_API_KEY`, `BRIGHTDATA_API_TOKEN`.
- [ ] **6.5** Desplegar backend en **Cloud Run** (us-central1).
- [ ] **6.6** Desplegar frontend en **Cloud Run** apuntando a la URL del backend.
- [ ] **6.7** Desplegar el agente a **Vertex AI Agent Engine** (solo modo A — ADC, ver ADR-0006). Recrear aquí el módulo `agent/root_agent.py` (idea de Mariana en `07a808b`) adaptado a la arquitectura actual: sin proyecto hardcodeado, sin Brave/Fetch, con auth dual.
- [ ] **6.8** Verificación end-to-end con URL pública.

---

## FASE 7 — Entrega del concurso
- [ ] **7.0** Sincronizar README con el código: stack y diagrama aún dicen "Bright Data Scraping Browser (CDP/WebSocket)" — desde 8.2 es Bright Data MCP. (Hallazgo M7.)
- [ ] **7.1** README con GIF/captura + URL hosted.
- [x] **7.2** `LICENSE` Apache 2.0 visible en *About* del repo.
- [ ] **7.3** Demo ~3 min: caso Ponzi/pseudo-trader → veredicto → repetición para mostrar early-exit. Subir a YouTube/Vimeo.
- [ ] **7.4** Formulario Devpost completado (URL repo + URL hosted + video + track).
- [ ] **7.5** Track del envío: 🟢 **Elastic** (ver ADR-0004).
- [~] **7.6** **Merge `Bright` → `main`**: hecho dos veces (PR #1 `7a90b5a` + merge `d5aeb53` del 2026-06-10). ⚠️ Cada commit nuevo en `Bright` reabre la brecha — **repetir el merge como último paso antes de enviar a Devpost**.

---

## ⚠️ Riesgos del reto — estado actual

| ID | Riesgo | Estado | Notas |
|---|---|---|---|
| **R1** | Ningún MCP usado es de partner del reto | ✅ **Resuelto en código** | Elastic MCP (track) + Phoenix MCP (bonus) integrados como `MCPToolset`. Falta validar con cluster real. |
| **R2** | El agente no es multi-paso real | ✅ **Resuelto** | Pipeline determinista en `agent/pipeline.py` expuesto por `/analizar/multipaso`. Devuelve `pasos_ejecutados`. |
| **R3** | No hay caché semántica con Elastic | ✅ **Resuelto en código** | Triage con umbrales 0.92/0.75 + index automático. Falta validar con cluster real. |
| **R4** | README alineado a finanzas | ✅ Resuelto | — |
| **R5** | Brave + Fetch no aportan al track | ✅ Resuelto | Removidos en 8.2. Bright Data MCP los cubre. |
| **R6** | Sin credenciales reales, todo está sin validar end-to-end | 🟡 **Pendiente** | Bloqueante para la demo y el despliegue (Fase 6). |
| **R7** | Sin URL pública aún | 🟡 Pendiente | Fase 6 (Cloud Run + Agent Engine). |
| **R8** | Sin video de demo ni submission Devpost | 🟡 Pendiente | Fase 7. |

---

## 🔐 Seguridad — incidente de claves (auditoría 2026-06-10)
> Fixes de código ya aplicados en la misma auditoría: C2 + A1 (`4d6ae6f`), A2 + A4 + A5 + M1 (`e8ba27c`), orden Phoenix (`f91ff7d`). Detalle en ADR-0005/0007 (enmiendas) y ADR-0011.

- [ ] **S.1** 🔴 **Rotar claves expuestas**: el commit `d7a18f0` (público en `origin/main`) contiene el `.env` real con `API_KEY_PHOENIX` y `BRAVE_API_KEY`. Rotar Phoenix en app.phoenix.arize.com y revocar Brave. ⚠️ Acción humana urgente.
- [ ] **S.2** Decidir con Mariana si se **purga la historia** (`git filter-repo --path .env --invert-paths` + force-push coordinado) o se aceptan las claves *revocadas* en el historial.
- [ ] **S.3** Decidir protección de la API pública en Cloud Run: backend con `--no-allow-unauthenticated` invocado solo por el frontend (service account), o aceptar el riesgo de abuso de cuota durante la evaluación.

---

## 🏁 Runbook — orden de ataque final
> Solo **referencias** a los checkboxes canónicos de cada fase — aquí no se marca nada.

| # | Qué | Dónde está el checklist | Quién | Estimado |
|---|---|---|---|---|
| 1 | Rotar claves expuestas | **S.1** | 🙋 Tú | 10 min |
| 2 | Cuentas y credenciales (ADC, APIs, Elastic Cloud, Bright Data, dataset Phoenix) | **0.5.2–0.5.7**, **8.1.1**, **8.2.1**, **8.3.1** | 🙋 Tú | ~45 min |
| 3 | Artefactos de deploy (cloudbuild + Dockerfile Streamlit) | **6.2**, **6.3** | 🤖 | ~1 h |
| 4 | Frontend multipaso | **5.4.1–5.4.4** | 🤖 | ~1.5 h |
| 5 | Smoke test end-to-end | **4.5.1–4.5.5** | 🤝 Juntos | ~30 min |
| 6 | Decisiones: purga historia + protección API | **S.2**, **S.3** | 🙋 Tú + Mariana | decisión |
| 7 | Deploy (Secret Manager, Cloud Run ×2, Agent Engine, URL) | **6.4–6.8** | 🤝 Juntos | ~3 h |
| 8 | Merge `Bright` → `main` | **7.6** | 🙋 Tú + Mariana | 15 min |
| 9 | Entrega (README final, demo, Devpost) | **7.0–7.5** | 🙋 Tú | ~3 h |

**Total estimado: ~1 día de trabajo enfocado.**
