# ADR-0013: Entrada multimodal — capturas de pantalla vía Gemini Vision

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** Cristian Hernández
- **Tags:** api, agente, multimodal

## Contexto

Las fake news financieras circulan principalmente como **pantallazos**:
cadenas de WhatsApp, posts de Instagram de pseudo-traders, "capturas de
ganancias" fabricadas. Hasta ahora el agente solo aceptaba texto/URL, dejando
fuera el formato más común del fraude que combatimos. El stub original de
triage (pre-Fase 8) ya contemplaba `tipo: "imagen"` con OCR — nunca se
implementó.

Gemini 2.5 Flash es **multimodal nativo**: puede transcribir el texto de la
imagen Y describir señales visuales (logos imitados, urgencia gráfica) que un
OCR perdería. No hace falta dependencia nueva.

## Decisión

Se añade un paso **[V] Visión** previo al pipeline, con estas elecciones:

1. **Transporte: JSON con base64** (`imagen_base64` + `imagen_mime` opcionales
   en el body de `POST /analizar/multipaso`), no multipart. Tolera dataURL.
   Límite **4 MB**, mime whitelist PNG/JPEG/WebP.
2. **Arquitectura: la imagen NO atraviesa el pipeline.** `agent/tools/vision.py`
   la convierte en `{texto_extraido, claim_principal, senales_visuales}`; el
   claim extraído alimenta el pipeline normal `[0]..[7]` **sin tocar ninguna
   otra tool** (el triage, Elastic, el verdict operan sobre texto, como siempre).
3. Las `senales_visuales` se inyectan como **banderas rojas** con prefijo
   `visual:` en el análisis lingüístico → llegan al verdict y a la UI.
4. **Degradación**: si la visión falla, el pipeline continúa solo con el texto;
   si no hay ni texto ni extracción, devuelve "Sin evidencia suficiente".
5. **Solo el endpoint multipaso** (el reactivo `/analizar` queda texto-only
   por ahora).
6. Frontend (`BlacklightExpose.html`): el clip 📎 abre selector de archivo,
   valida tipo/tamaño, muestra chip con miniatura y ✕, y la lista de pasos
   muestra `[V] Lectura de la imagen` cuando hay adjunto.

## Consecuencias

### ✅ Positivas
- El caso de uso más común del dominio (pantallazo de WhatsApp) queda cubierto.
- Cero dependencias nuevas; funciona en ambos modos de auth (ADR-0006).
- El pipeline existente no cambia: la visión es un adaptador de entrada.
- Demo: "sube la captura de la estafa que te llegó" es el momento más memorable.

### ⚠️ Negativas
- Base64 infla el payload ~33% (con el límite de 4 MB es irrelevante).
- Una llamada extra a Gemini por request con imagen (+1-3 s de latencia).
- El triage cachea sobre el **texto extraído**: dos pantallazos distintos del
  mismo bulo pueden no hacer early-exit si la transcripción varía mucho
  (mitigado: el claim_principal normaliza bastante).

### 🔁 Trade-offs
- JSON/base64 sobre multipart: pierde streaming de archivos grandes, gana
  simplicidad total en el frontend (un `fetch` igual al de texto). Para
  capturas de pantalla (KBs) es lo correcto.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Multipart/form-data** | Más eficiente para archivos grandes, pero duplica el camino de request en frontend y backend. Innecesario para capturas ≤4 MB. |
| **OCR clásico (Tesseract)** | Dependencia pesada nueva, pierde las señales visuales, y peor con tipografías de apps de mensajería. |
| **Pasar la imagen al LlmAgent reactivo** | El ADK lo soporta, pero perdería el triage/early-exit y el desglose de pasos del multipaso — justo lo que demuestra el reto. |

## Referencias

- `agent/tools/vision.py` — la tool (whitelist, límite, prompt JSON estructurado).
- `agent/pipeline.py` — paso [V], `entrada_efectiva`, merge de señales visuales.
- `main.py` — `NewsQuery.imagen_base64/imagen_mime`, `_decode_imagen` (HTTP 400).
- `frontend/BlacklightExpose.html` — clip funcional + chip de preview + paso [V] en la UI.
- Conversación previa: evaluación "¿puede aceptar imágenes?" (estimación 3-4 h).
