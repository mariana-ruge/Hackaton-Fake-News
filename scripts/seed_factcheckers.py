"""
Carga inicial de fact-checkers conocidos en el índice de Elasticsearch.
Uso:  python scripts/seed_factcheckers.py
"""

import sys


FACTCHECKERS_SEED = [
    {"nombre": "Maldita.es",        "dominio": "maldita.es",        "idioma": "es", "credibilidad": 0.9},
    {"nombre": "Newtral",           "dominio": "newtral.es",        "idioma": "es", "credibilidad": 0.9},
    {"nombre": "AFP Factual",       "dominio": "factual.afp.com",   "idioma": "es", "credibilidad": 0.9},
    {"nombre": "Chequeado",         "dominio": "chequeado.com",     "idioma": "es", "credibilidad": 0.9},
    {"nombre": "PolitiFact",        "dominio": "politifact.com",    "idioma": "en", "credibilidad": 0.85},
    {"nombre": "Snopes",            "dominio": "snopes.com",        "idioma": "en", "credibilidad": 0.85},
    {"nombre": "Reuters Fact Check","dominio": "reuters.com",       "idioma": "en", "credibilidad": 0.9},
]


def main() -> int:
    # TODO: implementar inserción real con elasticsearch-py
    for fc in FACTCHECKERS_SEED:
        print(f"  · {fc['nombre']} ({fc['dominio']})")
    print(f"Total: {len(FACTCHECKERS_SEED)} fact-checkers (semilla).")
    print("(Implementación pendiente)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
