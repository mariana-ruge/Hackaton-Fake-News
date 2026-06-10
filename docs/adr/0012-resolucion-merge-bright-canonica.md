# ADR-0012: Resolución del merge `main` → `Bright` — la arquitectura de Bright es la canónica

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Cristian Hernández (pendiente de socializar con Mariana Ruge)
- **Tags:** gobernanza, git, arquitectura

## Contexto

Durante ~3 días los dos integrantes trabajaron en ramas distintas **sin sincronizar**:

- **`Bright`** acumuló la Fase 8 completa (Elastic MCP track, Bright Data MCP, Phoenix MCP, pipeline multipaso, auth dual ADC/API-key) más los 5 fixes de la auditoría del 2026-06-10 (C2, A1, A2, A4, A5) y 11 ADRs.
- **`main`** recibió el commit `07a808b` de Mariana, que implementó **en paralelo** piezas equivalentes con otras convenciones: un `elastic_client.py` basado en `AsyncElasticsearch`, su propio `triage.py`, `setup_elastic_index.py`, un refactor de `main.py` con helpers `_env_value`, variables legacy (`PROJECT_ID`, `MODEL_ID`, `BRIGHTDATA_API_KEY`), Elastic MCP vía **imagen Docker** (`ELASTIC_MCP_IMAGE`) en lugar de npx, y un módulo nuevo `agent/root_agent.py` que extrae la definición del agente de `main.py`.

Al fusionar `main` en `Bright` colisionaron 7 archivos. No era un conflicto de líneas: eran **dos implementaciones completas del mismo subsistema** con APIs incompatibles entre sí (el pipeline y los tests de Bright dependen de la API síncrona de su `elastic_client`; las tools de `main` esperaban otras firmas).

## Decisión

**La arquitectura de `Bright` es la canónica.** Los 7 conflictos se resolvieron a favor de Bright. Del trabajo de `main` se conservó selectivamente:

| Pieza de `main` | Destino |
|---|---|
| `agent/root_agent.py` (módulo único del agente) | **Retirado del árbol, idea adoptada**: se recreará en la Fase 6.7 adaptado (sin proyecto hardcodeado, sin Brave/Fetch, con auth dual). Recuperable en `07a808b` |
| `BRIGHT_DATA_WS_URL` en `.env.example` | **Conservado** (el fallback `scraper.py` del extractor lo lee) |
| Cliente Elastic async, triage propio, `_env_value`, `ELASTIC_MCP_IMAGE` (Docker) | **Descartados** (ver razones abajo) |
| Eliminación de las dependencias OpenTelemetry en `requirements.txt` | **Revertida** — `main.py` las importa a nivel de módulo; sin ellas el server no arranca |

Razones técnicas del descarte:
- **Cliente async vs síncrono**: el pipeline, las tools y los tests de Bright dependen de la API síncrona (envuelta en `asyncio.to_thread`). Adoptar el async implicaba reescribir 6 módulos + tests sin ganancia funcional para el plazo del reto.
- **Variables legacy** (`PROJECT_ID`/`MODEL_ID`): reintroducían la inconsistencia que la auditoría ya había unificado a `GOOGLE_CLOUD_PROJECT`/`MODEL_NAME`.
- **Elastic MCP por Docker**: requiere Docker-in-Docker, que **Cloud Run no soporta** — el modo npx sí es desplegable.
- **Proyecto hardcodeado** `hackaton-498600` como fallback: reintroducía el riesgo de seguridad que se eliminó (clones de terceros tocando nuestro GCP).

## Consecuencias

### ✅ Positivas
- Una sola arquitectura coherente con los fixes de la auditoría y los ADRs 0001–0011.
- `Bright` contiene todo lo de `main` (0 commits detrás) → el merge `Bright → main` de la Fase 7.6 será fast-forward limpio.
- La buena idea de `main` (módulo `root_agent.py`) queda registrada y planificada en 6.7.

### ⚠️ Negativas
- Trabajo de Mariana mayormente descartado → **coste humano** que requiere conversación, no solo un commit. Su esfuerzo era razonable; el problema fue la falta de sincronización, no la calidad.
- El historial conserva dos implementaciones paralelas que pueden confundir a quien lea `git log`.

### 🔁 Trade-offs
- Elegimos **coherencia + plazo** sobre integrar lo mejor de cada implementación. Una fusión "fina" (p.ej. adoptar el cliente async) habría costado más de un día con riesgo de regresiones a días de la entrega.

## Proceso acordado para evitar repetirlo

1. **`Bright` es la rama de integración** hasta la entrega; `main` solo recibe merges desde `Bright` (Fase 7.6).
2. Antes de implementar un subsistema, **revisar `IMPLEMENTATION.md`** — si el ítem ya está `[x]`, existe código que extender, no reescribir.
3. Las decisiones de arquitectura se consultan en `docs/adr/` antes de elegir convenciones propias.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Quedarse con la implementación de `main`** | Perdía los 5 fixes de la auditoría, la auth dual, el pipeline multipaso y rompía los 3 archivos de tests. |
| **Fusión fina (mezclar lo mejor de ambas)** | Más de un día de trabajo + riesgo de regresiones, a días de la entrega. El cliente async puede adoptarse después como mejora documentada. |
| **Mantener `root_agent.py` tal cual** | Inicializaba Vertex al importar con proyecto hardcodeado y construía toolsets retirados (Brave/Fetch) — código activo engañoso. Mejor recrearlo bien en 6.7. |

## Referencias

- Merge commit `5fffd15` "Merge main en Bright: se conserva la arquitectura de Bright".
- Commit de Mariana: `07a808b` (recuperable: `git show 07a808b:agent/root_agent.py`).
- `IMPLEMENTATION.md` Fase 6.7 — recreación de `root_agent.py`.
- ADR-0006 (auth dual), ADR-0011 (patrón de acceso MCP) — las convenciones que el merge preservó.
