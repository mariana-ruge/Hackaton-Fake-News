# Architecture Decision Records (ADR)

Este directorio guarda el **historial de decisiones arquitectónicas** del proyecto.
Sirve para responder *"¿por qué hicimos esto así?"* sin tener que rebuscar en commits o issues.

> Formato basado en [Michael Nygard — *Documenting Architecture Decisions*](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) (variante ligera).

---

## ⚠️ Cuándo escribir un nuevo ADR

**Antes de implementar algo que cumpla AL MENOS UNA** de estas condiciones, **pausa y propón un ADR**:

1. Afecta a **más de un módulo** o paquete del repo.
2. Es **difícil o caro de revertir** (migraciones de datos, cambio de SDK, ruptura de API).
3. Introduce o **descarta una dependencia importante** (librería nueva, servicio externo, formato de datos).
4. Establece un **patrón que otros módulos seguirán** (naming de eventos, esquema de config, convenciones de errores).
5. El usuario o un compañero, en 3 meses, preguntaría *"¿por qué hicimos esto así?"*.

Cambios pequeños y locales (un bug fix, un rename, un refactor interno) **no** requieren ADR.

---

## Cómo se numeran y archivan

- Formato del nombre: `NNNN-titulo-en-kebab-case.md` (ej. `0007-triage-umbrales-early-exit.md`).
- Numeración **secuencial e irreversible**: una vez asignado un número, no se reusa aunque el ADR se deprecie.
- Estados posibles:
  - `Proposed` — borrador en discusión.
  - `Accepted` — vigente y aplicado.
  - `Deprecated` — ya no se sigue, pero NO fue reemplazado por otro ADR.
  - `Superseded by ADR-XXXX` — reemplazado; el ADR nuevo enlaza a este.

Cuando un ADR queda obsoleto, **no se borra**: se cambia su `Status` y se añade una nota al inicio que apunte al ADR sucesor.

---

## Plantilla mínima

```markdown
# ADR-NNNN: Título conciso

- **Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX
- **Date:** YYYY-MM-DD
- **Deciders:** quién(es) decidió(eron)
- **Tags:** stack | datos | auth | mcp | ...

## Contexto
¿Qué problema queríamos resolver? ¿Qué fuerzas en juego (técnicas, plazos, reto)?

## Decisión
La elección, en una frase si es posible.

## Consecuencias
- ✅ Positivas
- ⚠️ Negativas / costes
- 🔁 Trade-offs

## Alternativas consideradas
| Opción | Por qué se descartó |
|---|---|
| ... | ... |

## Referencias
- Archivos clave: `path/to/file.py`
- Commit(s): `<hash>` "mensaje"
- Documentos: `PLAN.md §N`, `IMPLEMENTATION.md Fase N`
```

---

## Índice de ADRs

| # | Título | Status | Tags |
|---|---|---|---|
| [0001](0001-orquestacion-adk-agent-engine.md) | Orquestación con ADK + Vertex AI Agent Engine (no low-code) | Accepted | stack, agente |
| [0002](0002-licencia-apache-2-0.md) | Licencia Apache 2.0 | Accepted | legal |
| [0003](0003-dominio-fake-news-financieras.md) | Foco en fake news financieras (Ponzi, pseudo-traders) | Accepted | producto |
| [0004](0004-track-partner-elastic.md) | Track partner del reto = Elastic | Accepted | mcp, reto |
| [0005](0005-persistencia-doble-capa.md) | Persistencia doble capa: Firestore (log) + Elastic (memoria semántica) | Accepted | datos |
| [0006](0006-auth-gemini-dual-adc-api-key.md) | Auth Gemini con soporte dual: ADC + API key directa | Accepted | auth |
| [0007](0007-triage-umbrales-early-exit.md) | Triage con umbrales 0.92 / 0.75 y early-exit determinista | Accepted | agente, datos |
| [0008](0008-bright-data-mcp-reemplaza-brave-fetch.md) | Bright Data MCP sustituye Brave + Fetch + Scraping Browser | Accepted | mcp |
| [0009](0009-arize-phoenix-bonus-partner.md) | Arize Phoenix MCP como bonus partner (junto a OpenTelemetry) | Accepted | mcp, observabilidad |
| [0010](0010-pipeline-determinista-vs-llm-reactivo.md) | Pipeline determinista coexistiendo con LlmAgent reactivo | Accepted | agente |
| [0011](0011-acceso-mcp-desde-pipeline.md) | Acceso a MCPs desde el pipeline: SDK `mcp` directo con sesiones efímeras | Accepted | mcp, patrón |

---

## Lecturas relacionadas

- [`../architecture.md`](../architecture.md) — vista actual de la arquitectura con diagramas mermaid.
- [`../../PLAN.md`](../../PLAN.md) — decisiones de alto nivel y arquitectura objetivo.
- [`../../IMPLEMENTATION.md`](../../IMPLEMENTATION.md) — hoja de ruta operativa por fases.
