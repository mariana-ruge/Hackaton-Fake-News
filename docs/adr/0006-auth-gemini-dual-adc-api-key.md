# ADR-0006: Auth Gemini con soporte dual ADC + API key directa

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** Cristian Hernández
- **Tags:** auth, dx, despliegue

## Contexto

Originalmente todo el código asumía **Vertex AI con ADC** (Application Default Credentials) porque la organización del proyecto `hackaton-498600` **bloquea API keys** por política de seguridad. Esto se descubrió cuando la consola devolvió:

> *"La política de seguridad de tu organización no permite las claves de API. Usa las credenciales predeterminadas de la aplicación (ADC) en su lugar."*

Eso es perfecto para nosotros, pero **deja fuera a cualquier juez o dev externo** que quiera probar el repo. Para ellos, `gcloud auth application-default login` es fricción innecesaria: solo quieren pegar una API key y arrancar.

Como el repo es público y el reto se evalúa por jueces externos, esto importa.

## Decisión

Soportamos **dos modos de autenticación** controlados por una sola variable: `GOOGLE_GENAI_USE_VERTEXAI`.

| Variable | Modo A (ADC / Vertex) | Modo B (API key / AI Studio) |
|---|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | `True` | `False` |
| Requiere | `gcloud auth application-default login` + `GOOGLE_CLOUD_PROJECT` | Solo `GOOGLE_API_KEY` |
| Cloud Run / Agent Engine | ✅ | ❌ (solo local) |
| Firestore | ✅ | ⚠️ Solo si también pones `GOOGLE_CLOUD_PROJECT` |
| MCPs (Elastic / Bright Data / Phoenix) | ✅ | ✅ (son independientes) |

La elección se hace en `agent/genai_client.py` con un singleton del `google.genai.Client()` que detecta el modo automáticamente. Falla rápido con mensaje accionable si la combinación es inválida.

## Consecuencias

### ✅ Positivas
- **Onboarding cero fricción para jueces / devs casuales**: clone + API key + run.
- El equipo interno sigue usando ADC sin tocar nada.
- Un solo entrypoint (`get_client()`) → el resto del código no sabe ni se entera del modo.
- `/health` reporta el modo elegido para depuración (`"auth_mode": "vertex_adc" | "api_key"`).

### ⚠️ Negativas
- Más documentación en `.env.example` y README (los dos bloques de configuración).
- Hay que recordar que **Agent Engine solo soporta modo A**.
- Firestore queda desactivado si alguien usa modo B sin GCP, pero al menos degrada limpiamente.

### 🔁 Trade-offs
- Renunciamos a la simplicidad de "una sola forma" a cambio de **portabilidad** del repo público.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Solo ADC** | Cualquier juez sin gcloud no puede correr el repo en 2 minutos. |
| **Solo API key** | Bloqueado por la política org del proyecto principal. Y además impide Agent Engine. |
| **Detección automática silenciosa** | Demasiada magia: si falla, el error es opaco. Mejor exigir una variable explícita y un mensaje accionable. |

## Referencias

- `agent/genai_client.py` — singleton `get_client()` con detección de modo.
- `agent/llm_client.py` — usa el cliente unificado para generación.
- `agent/tools/embeddings.py` — usa el cliente unificado para embeddings.
- `main.py` — `vertexai.init()` se ejecuta solo si `USE_VERTEXAI=True`.
- `.env.example` — sección "Gemini — elige UN modo de autenticación".
- README — sección "🔐 Dos modos de autenticación a Gemini".
- Commit `f27d1c2` "Auth Gemini: soporte dual ADC + API key directa".
