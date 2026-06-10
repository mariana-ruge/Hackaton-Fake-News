# ADR-0009: Arize Phoenix MCP como bonus partner

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** Cristian Hernández, Mariana Ruge
- **Tags:** mcp, observabilidad, partner

## Contexto

Mariana ya tenía **Arize Phoenix** integrado en `main.py` como capa de **telemetría OpenTelemetry**, instrumentando ADK automáticamente para enviar trazas a `app.phoenix.arize.com`. Esto da observabilidad gratis y dataset gratis para depurar prompts.

Pero el reto pide específicamente **"MCP server"**, no instrumentación. La telemetría OTel **NO cuenta** como integración MCP.

Sin embargo, Arize **sí tiene un MCP server oficial** (`@arizeai/phoenix-mcp`) que expone vía MCP:
- `list_datasets` / `get_dataset`
- `list_prompts` / `get_prompt`
- `list_experiments` / `get_experiment`
- `list_spans` / `get_span` (consultar trazas pasadas)

Como Elastic ya es el track principal (ver ADR-0004), Phoenix queda libre para ser un **bonus partner** que no compite con el track pero sí refuerza el envío.

## Decisión

Añadimos **Arize Phoenix MCP** (`@arizeai/phoenix-mcp` vía npx) como `MCPToolset` adicional en `main.py`.

- Se activa con la **misma `API_KEY_PHOENIX`** que ya habilita la telemetría OpenTelemetry → cero env vars nuevas obligatorias.
- Se desactiva limpiamente si falta la clave (no rompe el server).
- El agente puede consultar datasets curados de fraudes financieros (caso de uso bonito para la demo).

**Posicionamiento:**
- 🟢 **Track oficial del envío:** Elastic (ADR-0004).
- 🎁 **Bonus partner:** Arize Phoenix (este ADR).

## Consecuencias

### ✅ Positivas
- Integración con **dos partners del reto** (Elastic + Arize) → más sólido frente al jurado.
- Aprovecha el trabajo previo de Phoenix sin pisar al track principal.
- Caso de uso natural: el agente consulta su propio dataset curado de Ponzi conocidos antes de buscar en web.
- `/health` reporta los **tres** MCPs (Elastic, Bright Data, Phoenix) para depuración.

### ⚠️ Negativas
- Una pieza más que mantener.
- Si el dataset de Phoenix está vacío, las llamadas del agente al MCP devuelven listas vacías → sin valor, pero no rompe.

### 🔁 Trade-offs
- Renunciamos a la simplicidad de "un solo MCP" a cambio de robustez del envío al reto.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Solo telemetría (sin MCP)** | No cuenta como integración MCP del reto. Estábamos dejando puntos en la mesa. |
| **Hacer Phoenix el track principal** | Menos diferenciador que Elastic (que aporta triage semántico). Mejor como bonus. |
| **Dynatrace en lugar de Phoenix** | También observabilidad, pero Phoenix ya estaba integrado y nadie en el equipo conoce Dynatrace. |

## Referencias

- `main.py` — `phoenix_toolset` con `npx @arizeai/phoenix-mcp`.
- `.env.example` — `API_KEY_PHOENIX` (compartida con OTel) y `PHOENIX_BASE_URL`.
- Telemetría existente: `tracer_provider`, `GoogleADKInstrumentor` en `main.py`.
- Commit `1b3b9cc` "Fase 8.3 + 8.4 + 8.5: Phoenix MCP, doble capa y pipeline multi-paso".
