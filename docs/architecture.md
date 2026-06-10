# Arquitectura — VeritasAgent

> Vista actual del sistema, con diagramas mermaid que se renderizan automáticamente en GitHub.
> Para entender **por qué** se hizo así, leer los [ADRs](adr/).

---

## 1. Vista de alto nivel

```mermaid
flowchart TB
    subgraph Cliente["Cliente"]
        UI["💬 Streamlit chat<br/>frontend/app.py"]
    end

    subgraph Backend["Backend · Cloud Run"]
        API["⚡ FastAPI<br/>main.py"]
        subgraph Endpoints["Endpoints"]
            E1["/analizar<br/>(reactivo)"]
            E2["/analizar/multipaso<br/>(determinista)"]
            E3["/scrape"]
            E4["/historial"]
            E5["/health"]
        end
    end

    subgraph Agente["Agente · Google ADK"]
        ROOT["🤖 LlmAgent root_agent<br/>Gemini 2.5 Flash"]
        PIPE["🔄 pipeline.ejecutar_pipeline()<br/>orquestador determinista"]
        ROOT -->|reactivo| TOOLS[("agent/tools/*")]
        PIPE -->|secuencial| TOOLS
    end

    subgraph MCPs["MCPs · @stdio"]
        MCP1["🟢 Elastic MCP<br/>(track del reto)"]
        MCP2["🟠 Bright Data MCP"]
        MCP3["🎁 Arize Phoenix MCP<br/>(bonus partner)"]
    end

    subgraph Datos["Persistencia"]
        FS[("🔵 Firestore<br/>log operativo")]
        ES[("🟢 Elasticsearch<br/>memoria semántica")]
    end

    subgraph Servicios["Servicios externos"]
        VX["☁️ Vertex AI<br/>(Gemini + embeddings)"]
        PHX["📡 Arize Phoenix<br/>(OTel traces)"]
    end

    UI --> API
    API --> Endpoints
    E1 --> ROOT
    E2 --> PIPE
    ROOT --> MCP1 & MCP2 & MCP3
    TOOLS --> MCP1 & MCP2
    TOOLS -.->|futuro| MCP3
    PIPE --> ES
    API --> FS
    TOOLS --> VX
    API -.->|OTel| PHX
```

---

## 2. Flujo del endpoint `/analizar/multipaso`

El orquestador `agent/pipeline.py` ejecuta una secuencia determinista de 8 pasos.
Cada paso degrada con elegancia si falla su dependencia.

```mermaid
sequenceDiagram
    autonumber
    actor User as Usuario
    participant API as FastAPI<br/>/analizar/multipaso
    participant P as pipeline.py
    participant TR as triage.py
    participant ES as Elastic MCP
    participant LLM as Gemini<br/>(llm_client)
    participant SC as source_checker.py
    participant FS as Firestore

    User->>API: POST { texto_noticia }
    API->>P: ejecutar_pipeline(texto)

    rect rgb(220, 240, 220)
        Note over P,ES: [0] Triage (Elastic)
        P->>TR: triage(texto)
        TR->>LLM: get_embedding(texto)
        TR->>ES: hybrid_search (kNN + BM25)
        ES-->>TR: hits + scores
    end

    alt score ≥ 0.92  (EARLY EXIT)
        TR-->>P: { accion: early_exit, cached }
        P-->>API: resultado cacheado (<2s)
        API->>FS: log "modo: multipaso, cacheado: true"
        API-->>User: 200 OK
    else 0.75 ≤ score < 0.92  o  fresh
        Note over P,LLM: [1..6] Flujo completo
        P->>P: extraer(texto)
        P->>LLM: parsear_claims (prompt)
        P->>SC: evaluar_fuente(dominio)
        P->>P: contrastar (hits Elastic + búsqueda web vía Bright Data MCP)
        P->>LLM: analizar_linguistico (prompt)
        P->>LLM: emitir_veredicto (prompt)

        Note over P,ES: [7] Persistencia
        P->>LLM: get_embedding(claim)
        P->>ES: index_verification (veredicto + embedding)
        P-->>API: resultado completo
        API->>FS: log "modo: multipaso, completado"
        API-->>User: 200 OK
    end
```

---

## 3. Modelo de datos (doble capa)

Decisión documentada en [ADR-0005](adr/0005-persistencia-doble-capa.md).

```mermaid
erDiagram
    REQUEST ||--|| FIRESTORE_LOG : "se loguea como"
    REQUEST ||--o| ELASTIC_VERDICT : "puede generar"
    ELASTIC_VERDICT ||--o{ EVIDENCIA : "contiene"

    REQUEST {
        string texto_noticia
        timestamp ts
    }

    FIRESTORE_LOG {
        string doc_id PK
        string texto_noticia
        string etiqueta
        float confianza
        list pasos_ejecutados
        bool cacheado
        string elastic_doc_id FK
        string modo "reactivo | multipaso"
        timestamp fecha_analisis
    }

    ELASTIC_VERDICT {
        string claim_hash PK
        text claim_text
        vector claim_embedding "dense_vector(768)"
        keyword language
        int verdict_score "0-100"
        keyword category "Verdadero|Engañoso|Falso|Sin evidencia"
        keyword confidence "alta|media|baja"
        text reasoning
        keyword source_domain
        date verified_at
        int ttl_days
    }

    EVIDENCIA {
        keyword source
        keyword url
        keyword stance "confirma|refuta|contexto"
    }
```

| Colección/Índice | Tecnología | Rol | Cuándo se escribe |
|---|---|---|---|
| `analisis_noticias` | Firestore | Log inmutable de cada `/analizar*` | En cada request, después del análisis |
| `verificaciones` | Firestore | Log de cada `/scrape` | En cada request a `/scrape` |
| `verified_claims` | Elasticsearch | Memoria semántica (triage + recall) | Solo en el paso [7] del pipeline cuando hay un veredicto consolidado |

---

## 4. Triage: máquina de estados

Decisión documentada en [ADR-0007](adr/0007-triage-umbrales-early-exit.md).

```mermaid
stateDiagram-v2
    [*] --> Embedding: claim entra
    Embedding --> HybridSearch: vector + texto
    HybridSearch --> Decision: score del mejor hit

    Decision --> EarlyExit: score ≥ 0.92
    Decision --> Evidence: 0.75 ≤ score < 0.92
    Decision --> Fresh: score < 0.75

    EarlyExit --> [*]: devuelve cacheado<br/>(<2s, salta [1..6])
    Evidence --> Pipeline: hits como contexto<br/>(corre [1..6])
    Fresh --> Pipeline: sin contexto previo<br/>(corre [1..6])

    Pipeline --> [*]: veredicto nuevo<br/>+ index en Elastic
```

---

## 5. Componentes y responsabilidades

```mermaid
flowchart LR
    subgraph agent["agent/"]
        direction TB
        GENAI["genai_client.py<br/>cliente Gemini agnóstico<br/>(ADC | API key)"]
        LLM["llm_client.py<br/>prompts → JSON"]
        PIPE["pipeline.py<br/>orquestador 8 pasos"]

        subgraph tools["tools/"]
            T0["triage.py [0]"]
            T1["extractor.py [1]"]
            T2["claim_parser.py [2]"]
            T3["source_checker.py [3]"]
            T4["cross_reference.py [4]"]
            T5["linguistic.py [5]"]
            T6["verdict.py [6]"]
            T7["persistence.py [7]"]
            EMB["embeddings.py"]
        end

        subgraph mcp["mcp/"]
            EC["elastic_client.py<br/>conexión + hybrid_search + TTL"]
            BD["brightdata_client.py<br/>SDK mcp directo (ADR-0011)"]
            LC["local_cache.py<br/>fallback offline"]
        end

        subgraph data["data/"]
            FC["factcheckers.json<br/>(21 dominios curados)"]
        end
    end

    LLM --> GENAI
    EMB --> GENAI
    PIPE --> T0 --> EC
    PIPE --> T1 --> BD
    T4 --> BD
    PIPE --> T2 --> LLM
    PIPE --> T3 --> FC
    PIPE --> T4
    PIPE --> T5 --> LLM
    PIPE --> T6 --> LLM
    PIPE --> T7 --> EC
    T0 --> EMB
    T7 --> EMB
```

---

## 6. Autenticación a Gemini — modo dual

Decisión documentada en [ADR-0006](adr/0006-auth-gemini-dual-adc-api-key.md).

```mermaid
flowchart LR
    ENV{{".env<br/>GOOGLE_GENAI_USE_VERTEXAI"}}
    ENV -->|"True"| MODE_A
    ENV -->|"False"| MODE_B

    subgraph MODE_A["Modo A · Vertex AI (ADC)"]
        A1[gcloud auth application-default login]
        A2[GOOGLE_CLOUD_PROJECT]
        A1 & A2 --> A3["genai.Client(vertexai=True,...)"]
    end

    subgraph MODE_B["Modo B · API key (AI Studio)"]
        B1[GOOGLE_API_KEY]
        B1 --> B3["genai.Client(api_key=...)"]
    end

    A3 --> CLI{{"agent/genai_client.py<br/>singleton"}}
    B3 --> CLI
    CLI --> USE["llm_client.py + embeddings.py<br/>(agnósticos al modo)"]

    CLI -.->|"despliegue Agent Engine"| AE["✅ solo modo A"]
    CLI -.->|"Cloud Run / local"| LOCAL["✅ ambos modos"]
```

---

## 7. Configuración de entorno (resumen)

Detalles completos en `.env.example`. Aquí solo los grupos:

| Grupo | Variables clave | Para qué sirve |
|---|---|---|
| **Auth Gemini** | `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_API_KEY` | Modelo y embeddings |
| **Modelos** | `MODEL_NAME`, `EMBEDDING_MODEL` | Gemini 2.5 Flash + text-embedding-004 |
| **🟢 Elastic** | `ELASTIC_API_KEY`, `ELASTIC_URL`/`ELASTIC_CLOUD_ID`, `ELASTIC_INDEX` | Track partner del reto |
| **Bright Data** | `BRIGHTDATA_API_TOKEN`, `BRIGHTDATA_WEB_UNLOCKER_ZONE` | Scraping + búsqueda |
| **Phoenix** | `API_KEY_PHOENIX`, `PHOENIX_BASE_URL` | Telemetría + bonus MCP |
| **Triage** | `TRIAGE_EARLY_EXIT_THRESHOLD`, `TRIAGE_EVIDENCE_THRESHOLD`, `CACHE_TTL_DAYS` | Umbrales semánticos |

---

## 8. Endpoints

| Método | Ruta | Modo | Cuándo usar |
|---|---|---|---|
| POST | `/analizar` | Reactivo (LlmAgent decide) | Análisis exploratorio, preguntas libres |
| POST | `/analizar/multipaso` | Determinista (pipeline.py) | Demo del reto, casos repetibles, early-exit garantizado |
| POST | `/scrape` | Bright Data MCP | Extracción de URL como markdown |
| GET | `/historial?limit=N` | Firestore | Auditoría rápida sin búsqueda semántica |
| GET | `/health` | Diagnóstico | Estado de auth, MCPs, telemetría, índices |

---

## 9. Mapa de ADRs por subsistema

| Subsistema | ADRs relevantes |
|---|---|
| Stack y orquestación | [ADR-0001](adr/0001-orquestacion-adk-agent-engine.md), [ADR-0010](adr/0010-pipeline-determinista-vs-llm-reactivo.md) |
| Producto / alcance | [ADR-0003](adr/0003-dominio-fake-news-financieras.md) |
| Datos / persistencia | [ADR-0005](adr/0005-persistencia-doble-capa.md), [ADR-0007](adr/0007-triage-umbrales-early-exit.md) |
| MCPs / partners | [ADR-0004](adr/0004-track-partner-elastic.md), [ADR-0008](adr/0008-bright-data-mcp-reemplaza-brave-fetch.md), [ADR-0009](adr/0009-arize-phoenix-bonus-partner.md), [ADR-0011](adr/0011-acceso-mcp-desde-pipeline.md) |
| Auth / despliegue | [ADR-0006](adr/0006-auth-gemini-dual-adc-api-key.md) |
| Gobernanza / proceso git | [ADR-0012](adr/0012-resolucion-merge-bright-canonica.md) |
| Legal | [ADR-0002](adr/0002-licencia-apache-2-0.md) |

---

## 10. Próximas decisiones probables (sin ADR todavía)

Estos cambios cumplen los criterios de "merecen ADR" pero aún no se han tomado:

- Cómo desplegar a **Vertex AI Agent Engine** (sesiones gestionadas vs Cloud Run plano) — incluye recrear `agent/root_agent.py` (ver ADR-0012 y Fase 6.7).
- Si convertir el `LlmAgent` reactivo en una cadena de **sub-agentes ADK secuenciales**.
- Si migrar el cliente Elastic a **async** (la implementación de `07a808b` queda como referencia).
- Política de **rotación de claves** y manejo de **Secret Manager** en producción.
- Soporte **bilingüe ES/EN** real (hoy los prompts y el pipeline operan en `es`).
