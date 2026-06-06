"""Tests del módulo de triage.

Pruebas unitarias del cliente Elastic sin necesidad de cluster (mocks).
Los tests end-to-end requieren Elastic real y se etiquetan con `@requires_elastic`.
"""

from __future__ import annotations

import os

import pytest

from agent.mcp.elastic_client import (
    EARLY_EXIT_THRESHOLD,
    EVIDENCE_THRESHOLD,
    ElasticClient,
    claim_hash,
)


def test_claim_hash_es_estable():
    a = claim_hash("Bitcoin va a colapsar mañana")
    b = claim_hash("  bitcoin va a colapsar mañana  ")
    c = claim_hash("Bitcoin va a colapsar mañana.")  # punto final → distinto
    assert a == b, "el hash debe ser tolerante a espacios y mayúsculas"
    assert a != c, "puntuación trailing sí debe cambiar el hash"


def test_umbrales_dentro_de_rango_valido():
    assert 0.0 < EVIDENCE_THRESHOLD < EARLY_EXIT_THRESHOLD < 1.0


@pytest.mark.skipif(
    not (os.getenv("ELASTIC_API_KEY") and (os.getenv("ELASTIC_URL") or os.getenv("ELASTIC_CLOUD_ID"))),
    reason="Sin credenciales de Elastic — saltando test de integración",
)
def test_elastic_ping_real():
    client = ElasticClient()
    assert client.healthy(), "el cluster Elastic no responde al ping"
