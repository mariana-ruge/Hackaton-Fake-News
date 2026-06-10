"""Inicializa Firestore para VeritasAgent.

Uso:
    python scripts/setup_firestore.py

Requiere variables en .env:
    GOOGLE_CLOUD_PROJECT=<gcp-project-id>

Autenticación: Application Default Credentials (ADC).
Antes de correr asegúrate de haber ejecutado:
    gcloud auth application-default login
    gcloud auth application-default set-quota-project <project-id>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore


CONFIG_COLLECTION = "config"
CONFIG_DOC_ID = "veritas_settings"
CLAIMS_COLLECTION = "verified_claims"
TEST_DOC_ID = "test_setup"

VERITAS_SETTINGS = {
    "similarity_threshold_exit": 0.92,
    "similarity_threshold_evidence": 0.75,
    "default_ttl_days": 30,
    "ttl_breaking_news_days": 3,
    "embedding_model": "text-embedding-004",
    "embedding_dims": 768,
    "max_cached_docs_for_search": 200,
}


def _load_env() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()  # fallback: cwd

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("[ERROR] GOOGLE_CLOUD_PROJECT no está definido en .env", file=sys.stderr)
        sys.exit(1)
    return project_id


def _connect(project_id: str) -> firestore.Client:
    try:
        client = firestore.Client(project=project_id)
        # Forzamos una operación ligera para validar credenciales/red
        next(iter(client.collections()), None)
        return client
    except gcp_exceptions.GoogleAPIError as exc:
        print(f"[ERROR] No se pudo conectar a Firestore: {exc}", file=sys.stderr)
        sys.exit(2)


def _write_settings(client: firestore.Client) -> None:
    ref = client.collection(CONFIG_COLLECTION).document(CONFIG_DOC_ID)
    payload = dict(VERITAS_SETTINGS)
    payload["updated_at"] = firestore.SERVER_TIMESTAMP
    ref.set(payload, merge=True)


def _verify_permissions(client: firestore.Client) -> None:
    ref = client.collection(CLAIMS_COLLECTION).document(TEST_DOC_ID)
    ref.set(
        {
            "claim_hash": TEST_DOC_ID,
            "claim_text": "documento de prueba para verificar permisos",
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    snapshot = ref.get()
    if not snapshot.exists:
        raise RuntimeError("La lectura del doc de prueba devolvió vacío.")
    ref.delete()
    after = ref.get()
    if after.exists:
        raise RuntimeError("La eliminación del doc de prueba falló.")


def main() -> int:
    print("==> Cargando configuración (.env)...")
    project_id = _load_env()
    print(f"    PROJECT_ID = {project_id}")

    print("==> Conectando a Firestore...")
    client = _connect(project_id)
    print("    [OK] Conexión establecida.")

    print("==> Verificando permisos (write/read/delete) en 'verified_claims'...")
    try:
        _verify_permissions(client)
    except (gcp_exceptions.GoogleAPIError, RuntimeError) as exc:
        print(f"    [ERROR] Permisos insuficientes: {exc}", file=sys.stderr)
        return 3
    print("    [OK] Permisos correctos.")

    print(f"==> Guardando configuración en {CONFIG_COLLECTION}/{CONFIG_DOC_ID}...")
    try:
        _write_settings(client)
    except gcp_exceptions.GoogleAPIError as exc:
        print(f"    [ERROR] No se pudo guardar config: {exc}", file=sys.stderr)
        return 4
    print("    [OK] Configuración persistida.")

    print()
    print("============================================================")
    print(" Setup de Firestore completado")
    print("------------------------------------------------------------")
    print(f"  Proyecto         : {project_id}")
    print(f"  Conexión         : OK")
    print(f"  Permisos R/W/D   : OK")
    print(f"  Config doc       : {CONFIG_COLLECTION}/{CONFIG_DOC_ID}")
    print(f"  Claims coll.     : {CLAIMS_COLLECTION}")
    print("============================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
