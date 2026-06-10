"""
Tools del agente — flujo multi-paso planificado (ver PLAN.md §3).

Estado actual:
    [0] triage           → STUB (NotImplementedError)
    [1] extractor        → STUB  (la lógica real vive temporalmente en `scraper.py`)
    [2] claim_parser     → STUB  (prompt en `agent/prompts/claim_parser.es.txt`)
    [3] source_checker   → STUB
    [4] cross_reference  → STUB
    [5] linguistic       → STUB  (prompt en `agent/prompts/linguistic.es.txt`)
    [6] verdict          → STUB  (prompt en `agent/prompts/verdict.es.txt`)
    [7] persistence      → STUB
    embeddings           → IMPLEMENTADO (Vertex AI text-embedding-004)

Para la entrega actual el agente vive en `main.py` como un LlmAgent reactivo.
Estas tools son el esqueleto del refactor a multi-paso determinista
(triage con early-exit + cross-reference + verdict), pendiente de
implementación en una siguiente iteración.
"""
