# ADR-0008: Bright Data MCP sustituye Brave + Fetch + Scraping Browser

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** Cristian Hernández
- **Tags:** mcp, scraping

## Contexto

En un momento dado, el código tenía **tres mecanismos distintos** para hacer scraping y búsqueda web:

1. **Brave Search MCP** (`@modelcontextprotocol/server-brave-search`) → búsquedas web vía API de Brave.
2. **Fetch MCP** (`mcp-server-fetch`) → descarga simple de URLs estáticas.
3. **Bright Data Scraping Browser** (vía WebSocket + Playwright en `scraper.py`) → navegador real para sitios con JS y anti-bot.

Esto era resultado de la evolución incremental: cada uno se añadió para cubrir un caso que el anterior no resolvía. Pero acumulaba:

- 3 librerías → 3 superficies de error.
- Ninguno cuenta para el "partner MCP" del reto.
- Brave es de Brave (no partner), Fetch es de Anthropic (no partner), Bright Data Scraping Browser ni siquiera es MCP.

Bright Data tiene un **MCP oficial** (`@brightdata/mcp`) que cubre las tres funciones:
- `search_engine` → reemplaza Brave.
- `scrape_as_markdown` → reemplaza Fetch para páginas estáticas.
- `scrape_as_markdown` con Web Unlocker → reemplaza el Scraping Browser para anti-bot.

## Decisión

Sustituimos los tres por **Bright Data MCP oficial** (`@brightdata/mcp` vía npx):

- Se elimina `brave_toolset` en `main.py`.
- Se elimina `fetch_toolset` en `main.py`.
- Se elimina la dependencia `mcp-server-fetch` en `requirements.txt`.
- Se mantiene `scraper.py` como **respaldo offline** y para debugging local, pero no se usa en los endpoints.
- El endpoint `/scrape` ahora llama a `_fetch_url_with_brightdata` (usa la tool `scrape_as_markdown` del MCP).

**Aclaración importante:** Bright Data **NO es partner del reto**. No cuenta para el track (eso es Elastic, ver ADR-0004). Pero sigue siendo una herramienta valiosa que cubre tres roles con un solo proveedor y simplifica el stack.

## Consecuencias

### ✅ Positivas
- **Una sola integración** para tres funciones → menos código, menos env vars, menos cosas que pueden fallar.
- Web Unlocker incluido → ya no hace falta mantener Playwright para sitios con anti-bot.
- Configuración por **token único** (`BRIGHTDATA_API_TOKEN`) en lugar de WebSocket URLs y API keys diversas.
- Si en el futuro queremos cambiar de partner para esta capa, hay un solo `MCPToolset` que tocar.

### ⚠️ Negativas
- Dependencia de un proveedor de pago (free trial limitado).
- Si Bright Data se cae, `/scrape` deja de funcionar y el agente solo puede analizar texto pegado.

### 🔁 Trade-offs
- Renunciamos a la diversidad de proveedores a cambio de simplicidad y un MCP "real".

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Mantener los tres** | Triple complejidad sin valor diferencial. Confuso para alguien que clone el repo. |
| **Solo Brave + Fetch** | No cubre sitios con JS dinámico o anti-bot, frecuentes en medios financieros (WSJ, FT). |
| **Solo Playwright** | Requiere navegador local (Chromium), no escala bien en Cloud Run y tarda más. |
| **Cambiar a Apify MCP** | Funcionalidad parecida pero Apify tampoco es partner del reto y exige refactor adicional. |

## Referencias

- `main.py` — `brightdata_toolset` con `npx @brightdata/mcp` y `_fetch_url_with_brightdata`.
- `requirements.txt` — eliminado `mcp-server-fetch`; mantenido `playwright` solo como respaldo offline.
- `.env.example` — `BRIGHTDATA_API_TOKEN` y `BRIGHTDATA_WEB_UNLOCKER_ZONE`.
- `scraper.py` — sigue en el repo pero ya no lo usan los endpoints.
- Commit `7f38d93` "Fase 8.1 + 8.2: Elastic MCP (track) y Bright Data MCP".
