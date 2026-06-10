# ADR-0011: Acceso a MCPs desde el pipeline — SDK `mcp` directo con sesiones efímeras

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Cristian Hernández
- **Tags:** mcp, agente, patrón

## Contexto

El proyecto tiene **dos consumidores** de los servidores MCP:

1. El **LlmAgent reactivo** (`/analizar`), que recibe los MCPs como `MCPToolset` de ADK — el modelo decide cuándo llamarlos.
2. El **pipeline determinista** (`/analizar/multipaso`), que NO pasa por ADK: sus pasos son funciones Python que necesitan llamar tools concretas (scraping, búsqueda) en momentos concretos.

La primera implementación del pipeline accedía al MCP de Bright Data a través de la **API privada** del toolset de ADK (`brightdata_toolset._mcp_session_manager.create_session()`). Problemas:

- API privada → se rompe sin aviso entre versiones de ADK (hallazgo M1 de la auditoría).
- Las sesiones creadas así nunca se cerraban → fuga de procesos `npx`.
- Acoplaba el pipeline a ADK, cuando su gracia es justamente ser independiente.

## Decisión

Los pasos del pipeline acceden a los servidores MCP mediante un **cliente propio basado en el SDK oficial `mcp`** (`mcp.client.stdio.stdio_client` + `ClientSession`), con **una sesión efímera por llamada**:

- Implementación de referencia: `agent/mcp/brightdata_client.py` (`call_tool`, `scrape_url_markdown`, `search_web`).
- Cada llamada abre el server (`npx @brightdata/mcp`), ejecuta la tool, y cierra todo al salir del context manager. Timeout configurable (`BRIGHTDATA_CALL_TIMEOUT`, 90 s por defecto).
- El `MCPToolset` de ADK se mantiene **solo** para el agente reactivo. **Mismo servidor MCP, dos consumidores.**
- Este patrón es el canónico para cualquier MCP futuro que el pipeline necesite (p.ej. si el triage migrara del cliente `elasticsearch` al Elastic MCP).

## Consecuencias

### ✅ Positivas
- Solo API pública y estable del SDK `mcp` — sobrevive upgrades de ADK.
- Sin fugas: el context manager garantiza el cierre del subproceso.
- El endpoint `/scrape` también lo usa → eliminado el último uso de API privada.
- Narrativa limpia para el reto: la integración MCP se usa desde ambos modos del agente.

### ⚠️ Negativas
- Latencia por llamada: arrancar `npx` cuesta ~1–3 s (npm lo cachea tras la primera vez). En cross-reference se multiplica por claim — mitigado con `CROSS_REFERENCE_MAX_SEARCHES` (3 por defecto).
- Sin reuso de sesión → no hay estado compartido entre llamadas (para nuestras tools stateless es irrelevante).

### 🔁 Trade-offs
- Elegimos **robustez y simplicidad sobre rendimiento**. Si la latencia doliera en producción, el siguiente paso sería una sesión persistente con lifecycle gestionado en el `lifespan` de FastAPI — se documentaría como nuevo ADR.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **API privada del MCPToolset de ADK** | Era lo que había: frágil entre versiones, sesiones sin cerrar (M1). |
| **Sesión persistente global** | Más rápida, pero atada al event loop, requiere lifecycle cuidadoso y reconexión ante caídas del subproceso. Complejidad prematura. |
| **API REST de Bright Data directa** | Funciona, pero abandona MCP — debilita la narrativa del reto y duplica formatos de respuesta. |

## Referencias

- `agent/mcp/brightdata_client.py` — implementación de referencia.
- `agent/tools/extractor.py` y `agent/tools/cross_reference.py` — consumidores.
- `main.py::_fetch_url_with_brightdata` — `/scrape` migrado al cliente.
- Commit `e8ba27c` "fix(pipeline): Bright Data MCP en extractor/cross-reference…".
- Hallazgos A2 y M1 de la revisión del 2026-06-10 (ver `IMPLEMENTATION.md §9.0`).
