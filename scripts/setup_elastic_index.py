"""Crea (o recrea) el índice de Elasticsearch para VeritasAgent.

Uso:
    python scripts/setup_elastic_index.py             # crea si no existe
    python scripts/setup_elastic_index.py --recreate  # borra y crea (peligroso)

Lee `.env`:
    ELASTIC_URL          (o ELASTIC_CLOUD_ID)
    ELASTIC_API_KEY
    ELASTIC_INDEX        (por defecto: verified_claims)
    EMBEDDING_MODEL      (por defecto: text-embedding-004 → 768 dims)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError, BadRequestError

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = "verified_claims"

# Mapping del índice. Mantén `dims` alineado con `EMBEDDING_MODEL` en `.env`.
INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "claim_text":      {"type": "text"},
            "claim_embedding": {
                "type": "dense_vector",
                "dims": 768,
                "index": True,
                "similarity": "cosine",
            },
            "claim_hash":      {"type": "keyword"},
            "language":        {"type": "keyword"},
            "verdict_score":   {"type": "integer"},
            "category":        {"type": "keyword"},
            "confidence":      {"type": "keyword"},
            "reasoning":       {"type": "text"},
            "evidence": {
                "type": "nested",
                "properties": {
                    "source": {"type": "keyword"},
                    "url":    {"type": "keyword"},
                    "stance": {"type": "keyword"},
                },
            },
            "source_domain":   {"type": "keyword"},
            "verified_at":     {"type": "date"},
            "ttl_days":        {"type": "integer"},
        }
    },
}


def _load_env() -> dict:
    load_dotenv(ROOT / ".env")
    url = os.getenv("ELASTIC_URL")
    cloud_id = os.getenv("ELASTIC_CLOUD_ID")
    api_key = os.getenv("ELASTIC_API_KEY")
    index = os.getenv("ELASTIC_INDEX", DEFAULT_INDEX)

    if not api_key:
        print("[ERROR] ELASTIC_API_KEY no está definida en .env", file=sys.stderr)
        sys.exit(1)
    if not (url or cloud_id):
        print("[ERROR] Define ELASTIC_URL o ELASTIC_CLOUD_ID en .env", file=sys.stderr)
        sys.exit(1)

    return {"url": url, "cloud_id": cloud_id, "api_key": api_key, "index": index}


def _connect(cfg: dict) -> Elasticsearch:
    kwargs = {"api_key": cfg["api_key"], "request_timeout": 30}
    if cfg["cloud_id"]:
        kwargs["cloud_id"] = cfg["cloud_id"]
    else:
        kwargs["hosts"] = [cfg["url"]]
    es = Elasticsearch(**kwargs)
    if not es.ping():
        print("[ERROR] No se pudo conectar a Elasticsearch (ping falló).", file=sys.stderr)
        sys.exit(2)
    return es


def _create_index(es: Elasticsearch, index: str, recreate: bool = False) -> None:
    exists = es.indices.exists(index=index)
    if exists and recreate:
        print(f"    [WARN] Borrando índice existente '{index}' (--recreate)…")
        es.indices.delete(index=index)
        exists = False

    if exists:
        print(f"    [OK] Índice '{index}' ya existe. Nada que hacer.")
        return

    try:
        es.indices.create(index=index, body=INDEX_MAPPING)
        print(f"    [OK] Índice '{index}' creado con dense_vector(768).")
    except BadRequestError as exc:
        print(f"    [ERROR] No se pudo crear el índice: {exc}", file=sys.stderr)
        sys.exit(3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup del índice Elastic de VeritasAgent")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Borra el índice antes de crearlo (destruye datos).",
    )
    args = parser.parse_args()

    print("==> Cargando configuración (.env)…")
    cfg = _load_env()
    print(f"    Índice: {cfg['index']}")
    target = cfg["cloud_id"] or cfg["url"]
    print(f"    Cluster: {target}")

    print("==> Conectando a Elasticsearch…")
    es = _connect(cfg)
    info = es.info()
    print(f"    [OK] Conectado a {info['name']} ({info['version']['number']}).")

    print("==> Aplicando mapping…")
    _create_index(es, cfg["index"], recreate=args.recreate)

    print()
    print("============================================================")
    print(" Setup de Elasticsearch completado")
    print("------------------------------------------------------------")
    print(f"  Cluster        : {info['cluster_name']}")
    print(f"  Versión        : {info['version']['number']}")
    print(f"  Índice         : {cfg['index']}")
    print(f"  Vector dims    : 768 (cosine)")
    print("============================================================")
    print()
    print("Siguiente paso:  python scripts/seed_factcheckers.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
