"""Script de despliegue del agente VeritasAgent en Vertex AI Agent Engine.

Ejecutar (con ADC activo y Modo A configurado en .env):

    python scripts/deploy_agent_engine.py [--staging-bucket gs://...]

El script:
1. Construye el AdkApp con GlobalGemini.
2. Crea o actualiza el Agent Engine en Vertex AI.
3. Imprime el resource_name del agente desplegado.
4. Opcionalmente ejecuta una consulta de prueba contra el agente remoto.

Variables de entorno requeridas (del .env):
    GOOGLE_GENAI_USE_VERTEXAI=True
    GOOGLE_CLOUD_PROJECT
    GOOGLE_CLOUD_LOCATION  (default: us-central1)
    MODEL_NAME             (default: gemini-2.5-flash)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("deploy_agent_engine")


def _check_prereqs() -> None:
    """Falla rápido si falta alguna variable de entorno obligatoria."""
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower()
    if use_vertex not in {"1", "true", "yes", "on"}:
        sys.exit(
            "ERROR: GOOGLE_GENAI_USE_VERTEXAI debe ser True para desplegar en Agent Engine.\n"
            "  Edita .env → GOOGLE_GENAI_USE_VERTEXAI=True\n"
            "  Luego: gcloud auth application-default login"
        )
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        sys.exit("ERROR: GOOGLE_CLOUD_PROJECT no definido en .env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Despliega VeritasAgent en Vertex AI Agent Engine")
    parser.add_argument(
        "--staging-bucket",
        default=os.getenv("AGENT_ENGINE_STAGING_BUCKET"),
        help="GCS bucket para artefactos de staging (ej. gs://mi-bucket). "
             "También se puede definir como AGENT_ENGINE_STAGING_BUCKET en .env",
    )
    parser.add_argument(
        "--display-name",
        default="VeritasAgent",
        help="Nombre a mostrar en la consola de Agent Engine (default: VeritasAgent)",
    )
    parser.add_argument(
        "--test-query",
        default=None,
        help="Si se especifica, ejecuta esta consulta contra el agente desplegado tras el deploy.",
    )
    args = parser.parse_args()

    _check_prereqs()

    # Importamos aquí para que los errores de prereq se muestren primero.
    import vertexai
    from vertexai import agent_engines

    from agent.engine_app import build_adk_app

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    vertexai.init(project=project, location=location)
    logger.info("Vertex AI inicializado → project=%s, location=%s", project, location)

    # ── 1. Construir el AdkApp ──────────────────────────────────────────────
    logger.info("Construyendo AdkApp…")
    adk_app = build_adk_app()
    logger.info("AdkApp construido correctamente.")

    # ── 2. Crear / desplegar en Agent Engine ───────────────────────────────
    deploy_kwargs: dict = {"agent_engine": adk_app, "display_name": args.display_name}
    if args.staging_bucket:
        deploy_kwargs["staging_bucket"] = args.staging_bucket

    logger.info("Desplegando en Vertex AI Agent Engine (esto puede tardar varios minutos)…")
    remote_agent = agent_engines.create(**deploy_kwargs)
    logger.info("✅ Agente desplegado exitosamente.")
    logger.info("   resource_name : %s", remote_agent.resource_name)
    logger.info("   Consola       : https://console.cloud.google.com/vertex-ai/agents?project=%s", project)

    # ── 3. Consulta de prueba opcional ─────────────────────────────────────
    if args.test_query:
        logger.info("Ejecutando consulta de prueba remota: %r", args.test_query)
        session = remote_agent.create_session(user_id="deploy-test")
        response = remote_agent.query(
            input=args.test_query,
            session_id=session["id"],
        )
        print("\n─── Respuesta del agente remoto ───")
        print(response)
        print("───────────────────────────────────\n")


if __name__ == "__main__":
    main()
