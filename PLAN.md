# VeritasAgent — Plan Maestro

> Agente multi-paso para verificación de noticias (fake news) con triage por similitud semántica, evidencia rastreable y veredicto con nivel de confianza.
> Construido con **Gemini + Google Cloud (ADK + Agent Engine)** e integrando **2 MCPs de partner: Bright Data + Elastic**.

**Fecha:** 2026-06-05
**Estado:** Diseño aprobado — listo para implementación.

---

## 1. Resumen ejecutivo

VeritasAgent recibe una **URL, titular o afirmación (claim)** y devuelve un **veredicto de credibilidad (0–100) + categoría + evidencia con enlaces**. No es un chatbot: ejecuta un flujo determinista de pasos, decide cuándo profundizar y mantiene al usuario en control (human-in-the-loop).

La pieza diferenciadora es una **fase [0] de pre-análisis (triage) con Elastic**: antes de gastar scraping y razonamiento, busca por similitud semántica si el claim **ya fue verificado** y, si hay coincidencia fuerte, hace **early-exit** devolviendo el resultado cacheado.

### Decisiones cerradas

| Decisión | Elección |
|---|---|
| Idioma | **Español + Inglés (bilingüe)** |
| Frontend | **Streamlit** (hospedado en Cloud Run) |
| Orquestación | **Híbrido: ADK (lógica) + Vertex AI Agent Engine (despliegue gestionado)** |
| Licencia | **Apache 2.0** |
| Google Cloud | **Cuenta con créditos activos: sí** |
| MCPs de partner | **Bright Data (scraping/evidencia) + Elastic (triage + memoria semántica)** |

---

## 2. Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend: Streamlit (Cloud Run)                             │
│  - Input: URL / titular / claim  | selector idioma ES/EN     │
│  - Muestra pasos del agente en vivo + veredicto + evidencia  │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼──────────────────────────────────┐
│  Agente: ADK desplegado en Vertex AI Agent Engine            │
│  Modelo de razonamiento: Gemini 2.5                          │
│                                                              │
│   [0] Triage (Elastic)  ──► early-exit si match fuerte       │
│   [1] Extractor (Bright Data)                                │
│   [2] Claim Parser (Gemini)                                  │
│   [3] Source Checker                                          │
│   [4] Cross-Reference (Bright Data)                          │
│   [5] Linguistic Analysis (Gemini)                           │
│   [6] Verdict (Gemini)                                        │
│   [7] Persist / Index (Elastic)                              │
└───────┬───────────────────────────────────┬──────────────────┘
        │                                   │
┌───────▼─────────┐                 ┌────────▼─────────┐
│  Bright Data MCP │                 │   Elastic MCP    │
│  scraping +      │                 │  búsqueda híbrida │
│  búsqueda web    │                 │  (kNN + BM25) +   │
│  (Google News,   │                 │  almacén de       │
│  fact-checkers,  │                 │  verificaciones   │
│  Reuters/AP)     │                 │                   │
└──────────────────┘                 └───────────────────┘
```

### Por qué Elastic sustituye a MongoDB
Elastic cubre **dos roles a la vez**: (a) búsqueda vectorial/híbrida para el triage y la recuperación de evidencia, y (b) almacén persistente del historial de verificaciones. Una sola pieza, dos superpoderes → menos infraestructura y un partner mejor aprovechado.

---

## 3. Flujo detallado del agente

### [0] Triage / Pre-análisis  — *Elastic MCP*  ⭐ NUEVO
**Objetivo:** evitar el flujo caro si el claim ya está resuelto.

1. Normalizar el input → extraer el claim central (Gemini, llamada barata).
2. Generar embedding del claim.
3. Búsqueda **híbrida (kNN + BM25)** en el índice `verified_claims`.
4. Evaluar el `score` del mejor match contra umbrales:

```
score >= 0.92          → EARLY EXIT: devuelve veredicto cacheado (+ aviso "resultado previo del <fecha>")
0.75 <= score < 0.92   → NO sale; usa los hits como EVIDENCIA candidata y continúa el flujo
score < 0.75           → flujo completo desde cero
```

> ⚠️ **Regla de seguridad:** el early-exit SOLO es válido contra **claims que nosotros ya verificamos** (caché propio). Parecerse a una noticia real NO prueba que sea verdad — las fake news imitan noticias reales. Elastic dice "es similar a X", nunca "es verdad".

### [1] Extractor — *Bright Data MCP*
Si el input es URL: scraping del artículo (título, cuerpo, autor, fecha, dominio). Sortea bloqueos/anti-bot. Si es solo texto, se salta.

### [2] Claim Parser — *Gemini (structured output)*
Descompone el texto en **afirmaciones atómicas verificables**. Salida JSON: `[{claim, tipo, entidades, verificable: bool}]`.

### [3] Source Checker
Reputación del dominio: lista curada + heurísticas (dominio recién registrado, imita medio real, etc.). Salida: `reputation_score` + categoría. Reputación baja → el agente decide hacer cross-reference más agresivo.

### [4] Cross-Reference — *Bright Data MCP*
Por cada claim atómico, busca en:
- **Fact-checkers:** Snopes, AFP Factual, Maldita, Newtral, Colombiacheck (cubre ES/LatAm).
- **Medios de referencia:** Reuters, AP, AFP, EFE.
Recolecta coincidencias, contradicciones y "sin cobertura".

### [5] Linguistic Analysis — *Gemini*
Analiza sensacionalismo, clickbait, carga emocional, llamados a compartir, falta de fuentes citadas. Salida: `manipulation_score` + señales detectadas.

### [6] Verdict — *Gemini*
Sintetiza [3]+[4]+[5] en:
```json
{
  "score": 0-100,
  "category": "Verdadero | Engañoso | Falso | Sin evidencia suficiente",
  "confidence": "alta | media | baja",
  "reasoning": "texto bilingüe",
  "evidence": [{ "source": "...", "url": "...", "stance": "apoya|contradice|neutral" }]
}
```
**Nunca** veredicto absoluto sin evidencia: si no hay datos → "Sin evidencia suficiente".

### [7] Persist / Index — *Elastic MCP*
Indexa el caso completo (claim, embedding, veredicto, evidencia, fecha, idioma) en `verified_claims`. **Alimenta el triage futuro**: la próxima consulta similar saldrá por early-exit.

---

## 4. Herramientas (tools) del agente

| Tool | Backend | Paso |
|---|---|---|
| `triage_claim(claim)` | Elastic MCP | [0] |
| `lookup_cached(claim_hash)` | Elastic MCP | [0] |
| `fetch_article(url)` | Bright Data MCP | [1] |
| `extract_claims(text)` | Gemini | [2] |
| `check_source_reputation(domain)` | Lista curada / API | [3] |
| `search_factcheckers(claim)` | Bright Data MCP | [4] |
| `search_trusted_news(claim)` | Bright Data MCP | [4] |
| `analyze_language(text)` | Gemini | [5] |
| `build_verdict(context)` | Gemini | [6] |
| `index_verification(case)` | Elastic MCP | [7] |

---

## 5. Esquema de datos — índice Elastic `verified_claims`

```json
{
  "mappings": {
    "properties": {
      "claim_text":     { "type": "text" },
      "claim_embedding":{ "type": "dense_vector", "dims": 768, "index": true, "similarity": "cosine" },
      "claim_hash":     { "type": "keyword" },
      "language":       { "type": "keyword" },
      "verdict_score":  { "type": "integer" },
      "category":       { "type": "keyword" },
      "confidence":     { "type": "keyword" },
      "reasoning":      { "type": "text" },
      "evidence":       { "type": "nested",
                          "properties": {
                            "source": {"type":"keyword"},
                            "url":    {"type":"keyword"},
                            "stance": {"type":"keyword"} } },
      "source_domain":  { "type": "keyword" },
      "verified_at":    { "type": "date" },
      "ttl_days":       { "type": "integer" }
    }
  }
}
```
> `ttl_days`: verificaciones sensibles al tiempo expiran (una noticia "actual" no debe cachearse para siempre).

---

## 6. Estructura del repositorio

```
agentes-cloud/                 (raíz del repo público)
├── LICENSE                     # Apache 2.0  (visible en "About")
├── README.md                   # qué es, demo gif, cómo correr, arquitectura
├── PLAN.md                     # este documento
├── .env.example                # claves: GEMINI, BRIGHTDATA, ELASTIC (sin valores)
├── .gitignore
├── requirements.txt
├── Dockerfile                  # imagen para Cloud Run
├── cloudbuild.yaml             # CI/CD a Cloud Run / Agent Engine
│
├── agent/                      # lógica ADK
│   ├── __init__.py
│   ├── root_agent.py           # define el agente y registra tools
│   ├── config.py               # modelo, umbrales (0.92 / 0.75), idiomas
│   ├── tools/
│   │   ├── triage.py           # [0] Elastic
│   │   ├── extractor.py        # [1] Bright Data
│   │   ├── claim_parser.py     # [2] Gemini
│   │   ├── source_checker.py   # [3]
│   │   ├── cross_reference.py  # [4] Bright Data
│   │   ├── linguistic.py       # [5] Gemini
│   │   ├── verdict.py          # [6] Gemini
│   │   └── persistence.py      # [7] Elastic
│   ├── mcp/
│   │   ├── brightdata_client.py
│   │   └── elastic_client.py
│   └── prompts/
│       ├── claim_parser.es.txt / .en.txt
│       ├── linguistic.es.txt   / .en.txt
│       └── verdict.es.txt      / .en.txt
│
├── frontend/
│   └── app.py                  # Streamlit: input, pasos en vivo, veredicto
│
├── scripts/
│   ├── setup_elastic_index.py  # crea el índice verified_claims
│   └── seed_factcheckers.py    # lista curada de dominios/reputación
│
└── tests/
    ├── test_triage.py          # early-exit con umbrales
    ├── test_verdict.py
    └── fixtures/               # claims de ejemplo ES/EN
```

---

## 7. Diferenciadores para el track

- **No es chat:** input estructurado → veredicto trazable con enlaces.
- **Multi-paso real con decisión:** triage decide early-exit; reputación baja escala el cross-reference.
- **Human-in-the-loop:** el usuario puede pedir "explica por qué", aprobar búsquedas costosas, o forzar re-verificación ignorando caché.
- **Bilingüe ES/EN:** cubre fact-checkers de LatAm, poco atendidos en inglés.
- **2 partners MCP bien justificados:** Bright Data (evidencia real sorteando bloqueos) + Elastic (triage semántico + memoria).
- **Eficiencia medible:** noticias virales se verifican una vez; consultas siguientes salen en <2 s por caché.

---

## 8. Entregables del concurso

| Requisito | Plan |
|---|---|
| URL hosted | Cloud Run (Streamlit) |
| Repo público | GitHub, **Apache 2.0** visible en About |
| Demo ~3 min | Noticia viral real → mostrar [0] triage → flujo → veredicto + evidencia; luego repetir para mostrar early-exit |
| Track | Agente funcional con MCP de partner |
| Devpost | Formulario + enlaces |

---

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Costo/cuota de Bright Data | Triage Elastic cachea agresivamente; solo se scrapea lo nuevo |
| Latencia (30–60 s) | Streamlit muestra progreso paso a paso; early-exit <2 s |
| Falso "es real" en triage | Early-exit SOLO contra caché propio verificado, nunca por similitud a noticia real |
| Sesgo del LLM | Veredicto siempre citando fuentes; categoría "Sin evidencia" permitida; nunca absoluto sin datos |
| Caché obsoleto | `ttl_days` expira verificaciones sensibles al tiempo |
| Wording del reto ("Agent Builder") | Desplegado en Vertex AI Agent Engine = ecosistema oficial Agent Builder |

---

## 10. Roadmap de implementación

**Fase 1 — Cimientos (día 1–2)**
1. Repo + LICENSE Apache 2.0 + README + `.env.example`.
2. `setup_elastic_index.py` → crear `verified_claims`.
3. Clientes MCP: `brightdata_client.py`, `elastic_client.py` (conexión + smoke test).

**Fase 2 — Núcleo del agente (día 3–5)**
4. Tools [0]–[7] en ADK, con prompts ES/EN.
5. `root_agent.py` cableando el flujo + umbrales de early-exit.
6. Tests de triage y verdict con fixtures.

**Fase 3 — Frontend + despliegue (día 6–7)**
7. Streamlit con pasos en vivo y selector de idioma.
8. Dockerfile + cloudbuild → Cloud Run.
9. Desplegar agente en Agent Engine.

**Fase 4 — Pulido y entrega (día 8)**
10. Datos semilla de fact-checkers + reputación.
11. Grabar demo de 3 min (caso viral + early-exit).
12. Completar Devpost.

---

## 11. Próximos pasos inmediatos
1. Confirmar credenciales disponibles: API key de Gemini/Vertex, cuenta Bright Data, cluster Elastic (Elastic Cloud).
2. Crear el repo y el esqueleto de carpetas (sección 6).
3. Empezar por `setup_elastic_index.py` y los clientes MCP (es la base de todo el flujo).
```
```
