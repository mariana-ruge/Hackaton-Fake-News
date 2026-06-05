# VeritasAgent — Plan de Implementación (paso a paso)

> Este documento es la **hoja de ruta operativa**: qué construir, en qué orden, con qué criterio de "hecho".
> Las decisiones de arquitectura y técnicas viven en `PLAN.md`. Aquí solo se **ejecuta**.

**Repo raíz:** `D:\Trabajos u\Proyectos\agentes-cloud\Hackaton-Fake-News`
**Stack fijado:** Gemini 2.5 · ADK + Vertex AI Agent Engine · Streamlit (Cloud Run) · Bright Data MCP · Elastic MCP · Apache 2.0 · ES/EN

---

## Leyenda de estado
- `[ ]` pendiente · `[~]` en progreso · `[x]` hecho · `[!]` bloqueado

---

## FASE 0 — Cimientos del repo
> Objetivo: repo navegable, instalable y desplegable vacío.

- [x] **0.1** Crear `LICENSE` (Apache 2.0).
- [x] **0.2** Crear `PLAN.md` (arquitectura).
- [x] **0.3** Mover todo a la raíz `Hackaton-Fake-News`.
- [x] **0.4** Crear estructura de carpetas (sección 6 de `PLAN.md`).
- [x] **0.5** `README.md` — qué es, arquitectura, cómo correr local, cómo desplegar.
- [x] **0.6** `.gitignore` — Python, `.env`, artefactos de build, `__pycache__`.
- [x] **0.7** `.env.example` — claves vacías: `GEMINI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `BRIGHTDATA_API_KEY`, `ELASTIC_CLOUD_ID`, `ELASTIC_API_KEY`.
- [x] **0.8** `requirements.txt` — `google-adk`, `google-genai`, `elasticsearch`, `streamlit`, `python-dotenv`, `pydantic`, `pytest`.
- [x] **0.9** `git init` + primer commit + crear repo público en GitHub.

**Criterio de hecho:** `pip install -r requirements.txt` corre limpio; el repo muestra "Apache-2.0" en *About*.

---

## FASE 0.5 — Setup de Google Cloud
> Objetivo: preparar el **proyecto y la infraestructura base** de Google Cloud.
> Nota: aquí NO se "crea un agente" en una consola. Con ADK el agente es código; esto solo prepara el terreno. El agente se despliega a Agent Engine en la Fase 6.

### Requisitos previos
- Cuenta de Google Cloud con **créditos del reto activados**.
- **gcloud CLI** instalado ([guía oficial](https://cloud.google.com/sdk/docs/install)). Verifica con `gcloud version`.

### Pasos

- [ ] **0.5.1** Crear o seleccionar el proyecto.
  ```bash
  # Crear (elige un ID único, minúsculas/guiones)
  gcloud projects create veritas-agent-hackaton --name="VeritasAgent"
  # O seleccionar uno existente
  gcloud config set project veritas-agent-hackaton
  ```

- [ ] **0.5.2** Vincular la cuenta de facturación (necesaria aunque uses créditos).
  ```bash
  gcloud billing accounts list
  gcloud billing projects link veritas-agent-hackaton --billing-account=XXXXXX-XXXXXX-XXXXXX
  ```

- [ ] **0.5.3** Habilitar las APIs necesarias.
  ```bash
  gcloud services enable \
    aiplatform.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com
  ```
  | API | Para qué |
  |---|---|
  | `aiplatform` | Gemini + Vertex AI Agent Engine |
  | `run` | Frontend Streamlit (Fase 6) |
  | `secretmanager` | Guardar claves de Bright Data / Elastic |
  | `cloudbuild` + `artifactregistry` | CI/CD y la imagen Docker |

- [ ] **0.5.4** Autenticación local para que el código use Vertex AI.
  ```bash
  gcloud auth login
  gcloud auth application-default login
  ```

- [ ] **0.5.5** Definir región por defecto.
  ```bash
  gcloud config set ai/region us-central1
  ```

- [ ] **0.5.6** (Recomendado) Service Account para despliegues.
  ```bash
  gcloud iam service-accounts create veritas-agent \
    --display-name="VeritasAgent Runtime"
  # Roles mínimos: Vertex AI User + Secret Manager Accessor
  ```

- [ ] **0.5.7** Rellenar `.env` con `GOOGLE_CLOUD_PROJECT` y `GOOGLE_CLOUD_LOCATION`.

**Criterio de hecho:** `gcloud config list` muestra el proyecto y la región correctos, y `gcloud services list --enabled` lista las 5 APIs.

---

## FASE 1 — Conectividad MCP y datos
> Objetivo: hablar con Bright Data y Elastic antes de tocar la lógica del agente.

- [ ] **1.1** `agent/config.py` — modelo, idiomas, umbrales (`0.92` / `0.75`), TTL, dims embedding (768).
- [ ] **1.2** `agent/mcp/elastic_client.py` — conexión a Elastic Cloud + healthcheck.
- [ ] **1.3** `scripts/setup_elastic_index.py` — crea el índice `verified_claims` (mapping de `PLAN.md` §5).
- [ ] **1.4** `agent/mcp/brightdata_client.py` — conexión Bright Data + smoke test (1 fetch real).
- [ ] **1.5** `scripts/seed_factcheckers.py` — lista curada de dominios + reputación (Snopes, AFP, Maldita, Newtral, Colombiacheck, Reuters, AP…).
- [ ] **1.6** Embeddings: helper en `elastic_client.py` para generar `claim_embedding` con Gemini.

**Criterio de hecho:** un script de prueba indexa 1 claim falso en Elastic y lo recupera por similitud; Bright Data devuelve el cuerpo de 1 URL real.

---

## FASE 2 — Tools del agente (núcleo)
> Objetivo: cada paso del flujo como función testeable de forma aislada.

- [ ] **2.1** `tools/triage.py` — `[0]` busca claim en Elastic, aplica umbrales, decide early-exit.
- [ ] **2.2** `tools/extractor.py` — `[1]` scraping de URL con Bright Data → `{titulo, cuerpo, autor, fecha, dominio}`.
- [ ] **2.3** `prompts/claim_parser.{es,en}.txt` + `tools/claim_parser.py` — `[2]` claims atómicos (JSON estructurado).
- [ ] **2.4** `tools/source_checker.py` — `[3]` reputación de dominio (lista curada + heurísticas).
- [ ] **2.5** `tools/cross_reference.py` — `[4]` busca cada claim en fact-checkers y medios (Bright Data).
- [ ] **2.6** `prompts/linguistic.{es,en}.txt` + `tools/linguistic.py` — `[5]` sensacionalismo/clickbait/sesgo.
- [ ] **2.7** `prompts/verdict.{es,en}.txt` + `tools/verdict.py` — `[6]` score 0–100 + categoría + confianza + evidencia.
- [ ] **2.8** `tools/persistence.py` — `[7]` indexa el caso en Elastic (alimenta triage futuro).

**Criterio de hecho:** cada tool corre por separado con un input de prueba y devuelve su JSON esperado.

---

## FASE 3 — Orquestación del agente
> Objetivo: cablear los pasos con la lógica de decisión (early-exit, escalado).

- [ ] **3.1** `agent/root_agent.py` — registra las 10 tools, define instrucciones del agente (ES/EN).
- [ ] **3.2** Lógica de flujo: `[0]` → early-exit si `score≥0.92`; si no, `[1]…[7]`.
- [ ] **3.3** Escalado: reputación baja en `[3]` → cross-reference más agresivo en `[4]`.
- [ ] **3.4** Human-in-the-loop: opción "explica por qué" y "re-verificar ignorando caché".
- [ ] **3.5** Manejo de errores/timeouts por tool (degradación elegante, nunca veredicto absoluto sin datos).

**Criterio de hecho:** ejecutar el agente con un claim end-to-end en consola produce un veredicto completo y trazable.

---

## FASE 4 — Pruebas
> Objetivo: blindar la lógica crítica.

- [ ] **4.1** `tests/fixtures/` — claims ES/EN: 1 falso conocido, 1 verdadero, 1 engañoso, 1 sin cobertura.
- [ ] **4.2** `tests/test_triage.py` — verifica los 3 umbrales (early-exit, evidencia, flujo completo).
- [ ] **4.3** `tests/test_verdict.py` — estructura del veredicto + categoría "Sin evidencia" cuando aplica.
- [ ] **4.4** Test de regresión de caché: re-consultar un claim ya verificado sale por early-exit.

**Criterio de hecho:** `pytest` pasa en verde.

---

## FASE 5 — Frontend (Streamlit)
> Objetivo: interfaz de demo que muestre el agente "pensando".

- [ ] **5.1** `frontend/app.py` — input (URL/titular/claim) + selector idioma ES/EN.
- [ ] **5.2** Mostrar pasos en vivo (`[0]…[7]`) con indicador de progreso.
- [ ] **5.3** Render del veredicto: score, categoría, confianza, y evidencia con enlaces clicables.
- [ ] **5.4** Badge de early-exit ("resultado cacheado del <fecha>") cuando aplique.

**Criterio de hecho:** `streamlit run frontend/app.py` resuelve un caso real de principio a fin.

---

## FASE 6 — Despliegue (Google Cloud)
> Objetivo: URL pública + agente gestionado.

- [ ] **6.1** `Dockerfile` para el frontend Streamlit.
- [ ] **6.2** `cloudbuild.yaml` — build + deploy a Cloud Run.
- [ ] **6.3** Configurar secretos en Secret Manager (claves de §0.7).
- [ ] **6.4** Desplegar el agente ADK en Vertex AI Agent Engine.
- [ ] **6.5** Desplegar Streamlit en Cloud Run y conectarlo al agente.
- [ ] **6.6** Verificar URL pública funcionando end-to-end.

**Criterio de hecho:** una persona externa abre la URL y verifica una noticia.

---

## FASE 7 — Entrega del concurso
> Objetivo: cumplir todos los entregables de Devpost.

- [ ] **7.1** Pulir `README.md` con GIF/capturas + enlace a la URL hosted.
- [ ] **7.2** Confirmar `LICENSE` visible en *About* del repo público.
- [ ] **7.3** Grabar demo ~3 min: caso viral → flujo completo → repetir para mostrar early-exit.
- [ ] **7.4** Completar formulario Devpost (URL hosted + repo + video + track).
- [ ] **7.5** Seleccionar track: agente funcional con MCP de partner.

**Criterio de hecho:** submission de Devpost enviado y completo.

---

## Orden recomendado de ataque
`0.4 → 0.6 → 0.7 → 0.8 → 0.5` (cimientos) → `1.x` (conectividad, lo más arriesgado primero) → `2.x` → `3.x` → `4.x` → `5.x` → `6.x` → `7.x`.

## Dependencias / riesgos de bloqueo
- **1.x depende de credenciales reales:** Gemini/Vertex, Bright Data, Elastic Cloud. Conseguirlas es lo primero.
- **6.x depende de 1.x y 3.x** funcionando localmente.
- **7.3 (demo) depende de 6.6** (URL viva).
