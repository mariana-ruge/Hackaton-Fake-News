"""Tests del módulo verdict (mapeos deterministas, sin LLM)."""

import pytest

from agent.tools.verdict import (
    ETIQUETA_A_CATEGORIA,
    VALID_ETIQUETAS,
    confianza_a_nivel,
)


def test_mapeo_etiqueta_a_categoria_cubre_todas():
    assert set(ETIQUETA_A_CATEGORIA.keys()) == VALID_ETIQUETAS


@pytest.mark.parametrize(
    "conf,esperado",
    [
        (0.0, "baja"),
        (0.3, "baja"),
        (0.44, "baja"),
        (0.45, "media"),
        (0.6, "media"),
        (0.74, "media"),
        (0.75, "alta"),
        (1.0, "alta"),
    ],
)
def test_confianza_a_nivel(conf, esperado):
    assert confianza_a_nivel(conf) == esperado
