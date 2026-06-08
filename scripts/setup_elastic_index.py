"""
Crea (o recrea) el índice de Elasticsearch para fact-checks y veredictos.

El índice almacena las verificaciones de VeritasAgent y sirve como:
  - capa de triage (búsqueda híbrida kNN + BM25 sobre claims previos)
  - memoria persistente (write-back de cada veredicto)

Uso:
    python scripts/setup_elastic_index.py            # crea si no existe
    python scripts/setup_elastic_index.py --recreate # borra y vuelve a crear

Requiere en el entorno (.env):
    ELASTIC_CLOUD_ID  o  ELASTIC_URL
    ELASTIC_API_KEY
    ELASTIC_INDEX     (default: verified_claims)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Permite importar el paquete `agent` al ejecutar el script directamente.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)
except Exception:  # noqa: BLE001
    pass

from agent.mcp.elastic_client import ElasticClient  # noqa: E402


async def _run(recreate: bool) -> int:
    client = ElasticClient()

    if not client.is_configured():
        print(
            "ERROR: Elastic no está configurado.\n"
            "  Define ELASTIC_API_KEY y (ELASTIC_CLOUD_ID o ELASTIC_URL) en .env\n"
            "  e instala la dependencia: pip install 'elasticsearch>=8.13.0'",
            file=sys.stderr,
        )
        return 1

    await client.connect()

    if not await client.ping():
        print("ERROR: No se pudo conectar a Elasticsearch (ping falló).", file=sys.stderr)
        await client.close()
        return 1

    try:
        es = client._client  # acceso interno controlado para administración
        exists = await es.indices.exists(index=client.index)

        if exists and recreate:
            print(f"Eliminando índice existente '{client.index}'...")
            await es.indices.delete(index=client.index)
            exists = False

        if exists:
            print(f"El índice '{client.index}' ya existe. Nada que hacer.")
        else:
            print(f"Creando índice '{client.index}'...")
            await es.indices.create(index=client.index, body=client.index_mapping())
            print("Índice creado correctamente con mapping dense_vector (768, cosine).")

        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR al crear el índice: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()


def main() -> int:
    recreate = "--recreate" in sys.argv
    return asyncio.run(_run(recreate))


if __name__ == "__main__":
    sys.exit(main())
