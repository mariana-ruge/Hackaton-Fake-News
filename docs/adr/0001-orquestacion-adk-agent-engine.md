# ADR-0001: Orquestación con Google ADK + Vertex AI Agent Engine

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Cristian Hernández, Mariana Ruge
- **Tags:** stack, agente, despliegue

## Contexto

El reto "Build with AI" exige construir un agente con **Google Cloud Agent Builder + Gemini**.
Esa marca paraguas incluye tres formas distintas de construir el agente:

1. **Vertex AI Agent Studio (low-code).** Consola visual donde se conectan tools sin escribir código.
2. **Agent Development Kit (ADK).** Framework Python open source de Google. Se programa el flujo en código y se despliega donde quieras (Cloud Run, Agent Engine, etc.).
3. **Híbrido: ADK + Vertex AI Agent Engine.** Lógica en código (ADK) desplegada en la infra gestionada de Agent Engine (sesiones, escalado, tracing).

Necesitábamos elegir la base porque condiciona TODO lo demás: cómo definimos sub-agentes, cómo conectamos MCPs, cómo desplegamos y cómo demostramos "multi-step mission" al jurado.

Fuerzas en juego:

- 🟢 El reto pide explícitamente "multi-step mission" con control determinista (early-exit, escalado por reputación de fuente).
- 🟢 Necesitamos integrar varios MCPs de partners (Elastic track + bonus).
- 🟡 El plazo del hackathon obliga a iterar rápido.
- 🔴 El low-code dificulta el early-exit determinista (depende del modelo).

## Decisión

Adoptamos el **modo híbrido: ADK + Vertex AI Agent Engine**.

- La lógica del agente se escribe en **Python con ADK** (`main.py` y `agent/`).
- El despliegue final será sobre **Vertex AI Agent Engine** (Fase 6) para aprovechar la infra gestionada y el sello "Agent Builder" del reto.
- El frontend Streamlit y el backend FastAPI viven en Cloud Run.

## Consecuencias

### ✅ Positivas
- Control determinista del flujo multi-paso → el early-exit del triage vive en código, no en el prompt.
- MCP nativo en ADK (`MCPToolset`) → integramos Elastic, Bright Data y Phoenix sin wrappers artesanales.
- Tests unitarios sobre las tools (`pytest`) son triviales.
- Sello "Agent Builder" cumplido al desplegar en Agent Engine.

### ⚠️ Negativas
- Más código que mantener que el modo low-code.
- Curva de aprendizaje de ADK (relativamente nuevo).
- Despliegue en Agent Engine requiere autenticación con ADC (no API key) → motivó ADR-0006.

### 🔁 Trade-offs
- Renunciamos a la consola visual de Agent Studio (rapidez vs control). El reto premia más el control.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Agent Studio low-code** | El control del flujo multi-paso depende del modelo. Difícil garantizar early-exit por umbral. Menos código que mostrar a jueces. |
| **Solo ADK en Cloud Run** | Funciona pero pierde el sello "Agent Builder" oficial del reto. Lo mantenemos como plan B si el despliegue a Agent Engine se atasca. |

## Referencias

- `main.py` — instancia `LlmAgent`, `MCPToolset`, `InMemoryRunner`.
- `agent/pipeline.py` — flujo multi-paso determinista paralelo.
- `PLAN.md §2` — "Híbrido: ADK (lógica) + Vertex AI Agent Engine (despliegue gestionado)".
- `IMPLEMENTATION.md Fase 6` — checklist de despliegue.
