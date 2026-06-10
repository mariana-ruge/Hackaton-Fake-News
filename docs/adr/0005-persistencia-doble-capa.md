# ADR-0005: Persistencia doble capa — Firestore (log) + Elastic (memoria semántica)

- **Status:** Accepted (amended 2026-06-10)
- **Date:** 2026-06-07
- **Deciders:** Cristian Hernández, Mariana Ruge
- **Tags:** datos, persistencia

> **Enmienda 2026-06-10 — política de escritura en Elastic:** la primera
> implementación hacía que `/analizar` (reactivo) también indexara en
> `verified_claims`, con placeholders (`verdict_score=0`,
> `category=no_verificable`) porque el LLM reactivo no produce veredicto
> estructurado. Eso **envenenaba el caché**: un claim repetido hacía
> early-exit devolviendo esa basura como veredicto autoritativo (hallazgo
> C2 de la auditoría). Regla desde entonces: **solo el pipeline multipaso
> escribe en `verified_claims`** (produce veredictos estructurados de
> verdad); `/analizar` se limita al log de Firestore. Commit `4d6ae6f`.

## Contexto

El plan original (`PLAN.md v1`) tenía **una sola capa** de persistencia: Elastic, que cubría a la vez búsqueda semántica y almacén histórico. La sección §3 lo justificaba como *"una pieza, dos superpoderes"*.

Durante la implementación, Mariana añadió **Firestore** por su cuenta (con `scripts/setup_firestore.py`, colecciones `analisis_noticias` y `verificaciones`, y persistencia automática en `/analizar` y `/scrape`).

Al revisar:
- Firestore ya tenía código funcional y se integraba bien con Cloud Run.
- Quitarlo requería refactor del endpoint y perdíamos un componente útil.
- Mantenerlo "como está" duplicaba responsabilidades con Elastic.

Necesitábamos decidir el modelo de datos antes de seguir.

## Decisión

Adoptamos **doble capa de persistencia con roles diferenciados** (Opción B en la conversación de decisión):

| Capa | Tecnología | Rol | Cuándo escribe |
|---|---|---|---|
| **Operativa / auditoría** | **Firestore** | Log inmutable de cada request `/analizar*` y `/scrape` (input + output + metadatos) | En cada request del backend |
| **Memoria semántica** | **Elastic** | Índice `verified_claims` con `dense_vector(768)` para triage por similitud | Solo al consolidar un veredicto en el paso [7] del pipeline |

Cada capa tiene **información distinta**:
- Firestore guarda *requests* con su texto crudo, timestamps, `firestore_doc_id` para auditoría rápida y endpoint `/historial`.
- Elastic guarda *veredictos consolidados* con embedding, evidencias y `claim_hash`.

## Consecuencias

### ✅ Positivas
- **Cada herramienta hace lo que mejor sabe:** Firestore = lectura por id ultrarrápida; Elastic = búsqueda híbrida vectorial.
- **No duplicamos información:** texto de entrada → Firestore; veredicto + embedding → Elastic.
- Aprovechamos el código de Mariana sin tirarlo.
- Aprovechamos el partner del reto (Elastic) sin tener que forzarlo a hacer log operativo.
- Endpoint `/historial` (sobre Firestore) es trivialmente fácil.

### ⚠️ Negativas
- Dos sistemas que mantener (cuenta GCP + cluster Elastic).
- Si los devs no leen este ADR, podrían pensar que es redundancia.

### 🔁 Trade-offs
- Renunciamos a la simplicidad de "una sola capa" del plan original a cambio de claridad de roles y aprovechar trabajo existente.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **A. Quitar Firestore (volver al plan original)** | Implicaba refactor del endpoint y perder código funcional. Para un plazo de hackathon es trabajo innecesario. |
| **C. Mantener como estaba (sin roles claros)** | Generaba confusión: "¿dónde guardo qué?". |
| **MongoDB como única capa** | Implicaba refactor mayor y cambio de partner del reto (ver ADR-0004). |

## Referencias

- `main.py` — `_persist_firestore` y `guardar_veredicto` (Elastic).
- `agent/pipeline.py` — paso [7] indexa en Elastic; el log a Firestore vive en `main.py` después del pipeline.
- `scripts/setup_firestore.py` — colecciones e índices.
- `scripts/setup_elastic_index.py` — índice `verified_claims`.
- `PLAN.md §2` — sección "Estrategia de doble capa de persistencia".
- Commit `f8aafb7` "Arquitectura: track partner Elastic + doble capa de persistencia".
