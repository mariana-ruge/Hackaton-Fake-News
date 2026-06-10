# ADR-0004: Track partner del reto = Elastic

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** Cristian Hernández, Mariana Ruge
- **Tags:** mcp, reto, partner

## Contexto

El reto "Build with AI" pide:

> *"Pick **one** [partner] and build with their MCP server."*

Los 6 partners oficiales (Devpost):
1. Arize
2. Elastic
3. Fivetran
4. GitLab
5. MongoDB
6. Dynatrace

El estado del repo en el momento de la decisión era:

- Mariana ya tenía **Arize Phoenix vía OpenTelemetry** (telemetría, NO MCP).
- Yo había implementado **Bright Data Scraping Browser** (vía WebSocket, NO MCP, NO partner).
- También había **Brave Search MCP** y **Fetch MCP** (Anthropic, NO partners).
- El plan original (`PLAN.md v1`) ya mencionaba Elastic como capa de memoria semántica para el triage.

Riesgo crítico: **ningún MCP en el código era de un partner**. Sin track válido el envío puede invalidarse.

## Decisión

El **track oficial del envío al reto es Elastic**.

- Implementamos `@elastic/mcp-server-elasticsearch` como `MCPToolset` en `main.py`.
- Elastic cubre **dos roles** simultáneos: triage semántico (paso [0]) y memoria de veredictos (paso [7]).
- Phoenix MCP se añade como **bonus partner** (ver ADR-0009), no como track.
- Bright Data se mantiene **sin contar para el track** (ver ADR-0008).

## Consecuencias

### ✅ Positivas
- Recuperamos el diferenciador del plan original: caché semántica con early-exit.
- Se aprovechan **trabajos previos** (`esquema_datos.json`, `local_cache.py`, `setup_elastic_index.py` estaban semi-listos).
- Free trial 14 días de Elastic Cloud cubre la ventana del reto.
- Genera un caso de uso vendible: *"agente que aprende de cada verificación"*.

### ⚠️ Negativas
- Requiere mantener un cluster Elastic (Cloud o self-hosted) además de Firestore.
- Si Elastic se cae, el triage degrada a "fresh" (no rompe, pero pierde el diferenciador).

### 🔁 Trade-offs
- Renunciamos a Arize y MongoDB como track principal. Phoenix se queda como bonus.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Arize como track** | Lo más rápido (Phoenix ya estaba), pero menos diferenciador. Se aprovecha igualmente como bonus. |
| **MongoDB** | Sustituiría Firestore con búsqueda vectorial — refactor grande y poco encaje extra. |
| **Fivetran / GitLab / Dynatrace** | Off-topic para verificación de noticias financieras. |
| **Múltiples tracks** | El reto dice "Pick one". Forzar varios podría invalidar. |

## Referencias

- `main.py` — `elastic_toolset` (npx `@elastic/mcp-server-elasticsearch`).
- `agent/mcp/elastic_client.py` — cliente reutilizable.
- `agent/tools/triage.py` — paso [0] del pipeline.
- `agent/tools/persistence.py` — paso [7] del pipeline.
- `scripts/setup_elastic_index.py` — índice `verified_claims` con `dense_vector(768)`.
- Commit `7f38d93` "Fase 8.1 + 8.2: Elastic MCP (track) y Bright Data MCP".
