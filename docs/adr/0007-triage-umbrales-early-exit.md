# ADR-0007: Triage con umbrales 0.92 / 0.75 y early-exit determinista

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Cristian Hernández
- **Tags:** agente, datos, performance

## Contexto

El plan original del agente exige una **fase de pre-análisis (triage)** que evite ejecutar el flujo caro completo cuando ya hemos verificado un claim antes. Esto es el diferenciador del proyecto: *"si ya verificamos este bulo, no lo verifiquemos otra vez"*.

Dos preguntas críticas:

1. **¿Quién decide el early-exit?** ¿El LLM (en su prompt) o el código (con umbrales numéricos sobre el score de similitud)?
2. **¿Qué umbral usamos?** Si es demasiado bajo, devolvemos falsos cacheos. Si es demasiado alto, casi nunca hay early-exit.

Riesgo importante: las **fake news exitosas imitan noticias reales**. Confundir "similar a un veredicto previo" con "similar a una noticia verdadera" es un fallo grave.

## Decisión

El triage es **determinista en código**, no en el LLM. Define tres rangos sobre el `_score` híbrido (kNN + BM25) que devuelve Elastic:

```
score >= 0.92        → action: "early_exit"  (devuelve veredicto cacheado, <2s)
0.75 <= score < 0.92 → action: "evidence"    (usa hits como contexto, sigue el flujo)
score <  0.75        → action: "fresh"       (flujo completo desde cero)
```

Los umbrales son **configurables** vía env vars (`TRIAGE_EARLY_EXIT_THRESHOLD`, `TRIAGE_EVIDENCE_THRESHOLD`) por si queremos ajustarlos sin redeploy.

**Regla de seguridad** (también documentada en `PLAN.md §3` y en el código):

> El early-exit SOLO es válido contra claims que **nosotros ya verificamos** (caché propio). NO contra "noticias parecidas a una real". Elastic dice *"es similar a X"*, nunca *"es verdad"*.

El índice `verified_claims` **solo** se alimenta con veredictos consolidados por el pipeline (paso [7]), no con cualquier noticia indexada.

## Consecuencias

### ✅ Positivas
- **Latencia <2s** para claims repetidos → demo más impactante.
- Lógica testeable sin LLM (`tests/test_triage.py`).
- Cumple "multi-step mission" del reto: el agente decide qué pasos saltarse.
- Umbrales explícitos en `/health` y `.env`, ajustables sin recompilar.

### ⚠️ Negativas
- Necesitamos un cluster Elastic activo para que el triage haga algo útil (si Elastic falla, todo va a "fresh").
- Los umbrales son arbitrarios al inicio; habrá que tunearlos con datos reales.

### 🔁 Trade-offs
- Renunciamos a la flexibilidad de "deja que el LLM decida" a cambio de garantías de comportamiento.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **LLM decide vía prompt** | No determinista. Imposible garantizar el comportamiento <2s para el caché. Difícil de testear. |
| **Solo BM25 (sin kNN)** | Pierde semántica → un claim reescrito con otras palabras no haría match. |
| **Solo kNN puro** | Vulnerable a embeddings ruidosos en claims muy cortos (titulares). El BM25 ancla el match léxico. |
| **Umbrales únicos (un solo corte)** | El rango intermedio `[0.75, 0.92)` es valioso: hay match pero no es seguro hacer early-exit. Mejor traerlo como contexto. |

## Referencias

- `agent/mcp/elastic_client.py` — `hybrid_search` (kNN + match) y `triage` con umbrales.
- `agent/tools/triage.py` — wrapper async usado por el pipeline.
- `agent/pipeline.py` — early-exit ocurre en `ejecutar_pipeline` antes de cualquier llamada cara.
- `scripts/setup_elastic_index.py` — mapping con `dense_vector(768, cosine)`.
- `tests/test_triage.py` — pruebas deterministas del hash y umbrales.
- `PLAN.md §3` — flujo y regla de seguridad.
