"""Genera/actualiza `agent/data/factcheckers.json` con la lista curada.

Uso:
    python scripts/seed_factcheckers.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "agent" / "data" / "factcheckers.json"

FACTCHECKERS = [
    # Fact-checkers en español
    {"nombre": "Maldita.es",         "dominio": "maldita.es",          "idioma": "es", "categoria": "fact_checker",     "credibilidad": 0.90},
    {"nombre": "Newtral",            "dominio": "newtral.es",          "idioma": "es", "categoria": "fact_checker",     "credibilidad": 0.90},
    {"nombre": "AFP Factual",        "dominio": "factual.afp.com",     "idioma": "es", "categoria": "fact_checker",     "credibilidad": 0.92},
    {"nombre": "Chequeado",          "dominio": "chequeado.com",       "idioma": "es", "categoria": "fact_checker",     "credibilidad": 0.90},
    {"nombre": "Colombiacheck",      "dominio": "colombiacheck.com",   "idioma": "es", "categoria": "fact_checker",     "credibilidad": 0.88},
    # Fact-checkers en inglés
    {"nombre": "PolitiFact",         "dominio": "politifact.com",      "idioma": "en", "categoria": "fact_checker",     "credibilidad": 0.88},
    {"nombre": "Snopes",             "dominio": "snopes.com",          "idioma": "en", "categoria": "fact_checker",     "credibilidad": 0.85},
    {"nombre": "FactCheck.org",      "dominio": "factcheck.org",       "idioma": "en", "categoria": "fact_checker",     "credibilidad": 0.88},
    {"nombre": "Reuters Fact Check", "dominio": "reuters.com",         "idioma": "en", "categoria": "fact_checker",     "credibilidad": 0.90},
    # Medios financieros de referencia
    {"nombre": "Reuters",            "dominio": "reuters.com",         "idioma": "en", "categoria": "medio_referencia", "credibilidad": 0.92},
    {"nombre": "Bloomberg",          "dominio": "bloomberg.com",       "idioma": "en", "categoria": "medio_referencia", "credibilidad": 0.92},
    {"nombre": "Financial Times",    "dominio": "ft.com",              "idioma": "en", "categoria": "medio_referencia", "credibilidad": 0.92},
    {"nombre": "WSJ",                "dominio": "wsj.com",             "idioma": "en", "categoria": "medio_referencia", "credibilidad": 0.90},
    {"nombre": "Associated Press",   "dominio": "apnews.com",          "idioma": "en", "categoria": "medio_referencia", "credibilidad": 0.92},
    {"nombre": "EFE",                "dominio": "efe.com",             "idioma": "es", "categoria": "medio_referencia", "credibilidad": 0.88},
    {"nombre": "Expansión",          "dominio": "expansion.com",       "idioma": "es", "categoria": "medio_referencia", "credibilidad": 0.85},
    {"nombre": "El Economista",      "dominio": "eleconomista.es",     "idioma": "es", "categoria": "medio_referencia", "credibilidad": 0.82},
    {"nombre": "Cinco Días",         "dominio": "cincodias.elpais.com","idioma": "es", "categoria": "medio_referencia", "credibilidad": 0.85},
    # Organismos reguladores
    {"nombre": "CNMV",               "dominio": "cnmv.es",             "idioma": "es", "categoria": "regulador",        "credibilidad": 0.95},
    {"nombre": "SEC",                "dominio": "sec.gov",             "idioma": "en", "categoria": "regulador",        "credibilidad": 0.97},
    {"nombre": "CONSAR",             "dominio": "gob.mx",              "idioma": "es", "categoria": "regulador",        "credibilidad": 0.90},
]


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(FACTCHECKERS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] Escritos {len(FACTCHECKERS)} dominios curados en {OUT}")
    print("Categorías:",
          ", ".join(sorted(set(f["categoria"] for f in FACTCHECKERS))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
