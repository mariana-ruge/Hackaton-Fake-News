# ADR-0014: Dos frontends — landing HTML same-origin para la demo + Streamlit como cliente alternativo

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Cristian Hernández, Mariana Ruge
- **Tags:** ui, frontend, despliegue

## Contexto

El ítem 5.4 del plan pedía que el frontend mostrara el **pipeline multipaso**
(pasos en vivo, badge de early-exit, veredicto con colores) — la mejor carta
de la demo. Había dos caminos:

1. **Extender el chat Streamlit** (`frontend/app.py`) con esa visualización.
2. Crear una **landing HTML dedicada** a partir del diseño generado con Claude
   (el usuario aportó mockups; el enlace de descarga expiró y se implementó
   desde la especificación del prompt).

Factores en juego: Streamlit re-renderiza la página entera por interacción
(las animaciones paso-a-paso quedan toscas), su despliegue exige un servicio
Cloud Run aparte, y el mockup ya definía una estética concreta (dark, chips,
tarjetas) difícil de reproducir fielmente en Streamlit.

## Decisión

Conviven **dos frontends con roles distintos**:

| Frontend | Rol | Cómo se sirve |
|---|---|---|
| `frontend/BlacklightExpose.html` | **UI principal de la demo**: hero + chips de ejemplos, pasos [V]/[0]..[7] animados, early-exit ⚡, veredicto con colores, clip 📎 multimodal (ADR-0013) | **Same-origin desde FastAPI** (`GET /`) — viaja en el mismo contenedor que el backend, sin CORS y sin servicio extra |
| `frontend/app.py` (Streamlit) | Cliente de chat alternativo (endpoint reactivo), con modo `api\|direct` de Mariana | Local o servicio Cloud Run propio — **opcional** |

Consecuencia operativa clave: **desplegar Streamlit deja de ser bloqueante**
para la demo. La URL pública del backend ya incluye la UI completa.

## Consecuencias

### ✅ Positivas
- Demo con la estética del diseño aprobado y animaciones fluidas (JS nativo).
- Un solo servicio Cloud Run cubre API + UI → menos pasos de deploy (6.3/6.6
  pasan a opcionales), menos superficie de fallo, sin CORS.
- HTML estático sin build step ni dependencias — cualquier juez lo entiende.
- `?api=<url>` permite apuntar la landing a otro backend si hiciera falta.

### ⚠️ Negativas
- Dos UIs que mantener; los cambios de contrato del API tocan ambas.
- El HTML no comparte componentes con Streamlit (duplicación visual asumida).
- JS vanilla en un solo archivo: si la UI creciera mucho, habría que migrar
  a un framework (decisión futura, nuevo ADR).

### 🔁 Trade-offs
- Elegimos **fidelidad de demo + simplicidad de deploy** sobre "una sola
  tecnología de frontend".

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Solo Streamlit extendido** | Animaciones por re-render, otro servicio en Cloud Run, estética del mockup difícil de clavar. |
| **SPA (React/Vite)** | Build step + dependencias para una sola pantalla: sobreingeniería para el plazo. |
| **Eliminar Streamlit** | El modo `direct` de Mariana (runner ADK sin FastAPI) es útil para pruebas locales; se conserva como secundario. |

## Referencias

- `frontend/BlacklightExpose.html` — la landing (345+ líneas, archivo único).
- `main.py::landing` — `GET /` con `FileResponse` same-origin.
- `frontend/app.py` — cliente Streamlit con `FRONTEND_MODE=api|direct`.
- ADR-0013 — el clip multimodal vive en esta landing.
- Commits `c907ffc` (landing) y `52453f7` (clip funcional).
