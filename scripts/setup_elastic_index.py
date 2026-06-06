"""
Crea (o recrea) el índice de Elasticsearch para fact-checks y veredictos.
Uso:  python scripts/setup_elastic_index.py
"""

import os
import sys


INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "claim_id":      {"type": "keyword"},
            "claim_texto":   {"type": "text"},
            "fuente":        {"type": "keyword"},
            "url":           {"type": "keyword"},
            "veredicto":     {"type": "keyword"},
            "confianza":     {"type": "float"},
            "fecha":         {"type": "date"},
            "resumen":       {"type": "text"},
            "evidencias":    {"type": "text"},
        }
    }
}


def main() -> int:
    elastic_url = os.getenv("ELASTIC_URL")
    if not elastic_url:
        print("ERROR: ELASTIC_URL no definida.", file=sys.stderr)
        return 1

    # TODO: implementar creación real con elasticsearch-py
    print("Mapping a aplicar:")
    print(INDEX_MAPPING)
    print("(Implementación pendiente)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
