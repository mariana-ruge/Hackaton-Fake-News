"""Tests del módulo de triage.

El triage es parte del flujo multi-paso planificado. Mientras la tool sea
un stub, marcamos los tests como xfail para no romper CI.
"""

import pytest

from agent.tools import triage as triage_mod


@pytest.mark.xfail(reason="triage aún no implementado (stub: NotImplementedError)", strict=True)
def test_triage_clasifica_url():
    """Cuando se implemente, este test debe pasar de verdad (sin xfail)."""
    result = triage_mod.triage("https://ejemplo.com/noticia")
    assert result["tipo"] in {"url", "texto", "imagen", "desconocido"}
    assert 0.0 <= result["confianza"] <= 1.0
    assert result["siguiente_paso"]
