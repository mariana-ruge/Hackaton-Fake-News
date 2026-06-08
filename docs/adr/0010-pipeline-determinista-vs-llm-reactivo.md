# ADR-0010: Pipeline determinista coexistiendo con LlmAgent reactivo

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** Cristian Hernández
- **Tags:** agente, arquitectura

## Contexto

Llegamos al refactor multi-paso con **dos enfoques posibles** y sin tiempo para experimentar largo:

### Enfoque A — LlmAgent reactivo (lo que Mariana ya tenía)
`root_agent = LlmAgent(prompt_principal, tools=[GoogleSearch, URLContext, Brave, Fetch])`. El modelo decide a cada paso qué tool llamar. Flexible y conciso, pero:
- Difícil garantizar early-exit determinista (depende del LLM).
- Difícil testear paso por paso.
- El reto pide "multi-step mission" → un solo LlmAgent reactivo parece poco "step".

### Enfoque B — Pipeline determinista (`agent/pipeline.py`)
`triage → extractor → claim_parser → source_checker → cross_reference → linguistic → verdict → persistence`. Cada paso es una función con su propio test, sus propios errores y su propia degradación. Más código, más control.

Las dos opciones tienen sentido para casos distintos:
- **Reactivo** brilla con preguntas abiertas (*"¿qué piensas de este texto?"*).
- **Determinista** brilla cuando hay que garantizar pasos (*"siempre triagear, siempre persistir"*).

## Decisión

Mantenemos **ambos enfoques en paralelo**, expuestos como endpoints distintos:

| Endpoint | Modo | Cuándo se usa |
|---|---|---|
| `POST /analizar` | Reactivo (LlmAgent + triage como hint) | Análisis exploratorio, preguntas libres. Mantiene comportamiento previo. |
| `POST /analizar/multipaso` | Determinista (pipeline.py) | Demo del reto, casos donde queremos desglose paso a paso, latencia <2s en cache. |

El **pipeline determinista** comparte tools con el LlmAgent (las dos rutas usan el mismo `triage.py`, `verdict.py`, etc.). No duplicamos lógica, solo orquestación.

## Consecuencias

### ✅ Positivas
- **El reto se demuestra mejor con `/analizar/multipaso`** (devuelve `pasos_ejecutados`, `triage`, `fuente`, `linguistico`, etc.).
- Mantenemos compatibilidad con la primera versión que ya funcionaba (`/analizar`).
- Cada endpoint puede evolucionar a su ritmo sin romper al otro.
- Pipeline testeado paso por paso con `pytest`.
- Si en el futuro queremos sustituir el LlmAgent por sub-agentes secuenciales, el pipeline ya está listo.

### ⚠️ Negativas
- Dos endpoints distintos pueden confundir a quien clone el repo. Hay que documentarlo bien.
- Bug en una tool afecta a ambos endpoints.

### 🔁 Trade-offs
- Renunciamos a la simplicidad de "un solo endpoint" a cambio de tener **control determinista** disponible para la demo.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Solo el LlmAgent reactivo** | No demuestra "multi-step mission" del reto de forma convincente. |
| **Solo el pipeline determinista** | Perdíamos la flexibilidad para preguntas libres. Y borrar el código de Mariana sin un beneficio enorme no era rentable. |
| **Sub-agentes ADK secuenciales** | El ADK soporta sub-agentes encadenados pero el orquestador en Python da más control y es más testeable. Lo dejamos para una iteración futura si hace falta. |

## Referencias

- `agent/pipeline.py` — orquestador determinista.
- `main.py` — `root_agent` (LlmAgent) y los dos endpoints.
- `agent/tools/*` — tools compartidas entre ambos modos.
- `agent/llm_client.py` — helper para los pasos del pipeline que llaman a Gemini.
- Commit `1b3b9cc` "Fase 8.3 + 8.4 + 8.5: Phoenix MCP, doble capa y pipeline multi-paso".
