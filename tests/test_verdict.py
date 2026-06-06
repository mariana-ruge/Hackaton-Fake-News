"""Tests del módulo de verdict.

El verdict es parte del flujo multi-paso planificado. Mientras la tool sea
un stub, marcamos los tests como xfail para no romper CI.
"""

import pytest

from agent.tools import verdict as verdict_mod


@pytest.mark.xfail(reason="verdict aún no implementado (stub: NotImplementedError)", strict=True)
def test_verdict_estructura_basica():
    """Cuando se implemente, este test debe pasar de verdad (sin xfail)."""
    result = verdict_mod.emitir_veredicto([], [], {}, {})
    assert result["etiqueta"] in {"verdadero", "engañoso", "falso", "no_verificable"}
    assert 0.0 <= result["confianza"] <= 1.0
    assert isinstance(result["resumen"], str)
    assert isinstance(result["evidencias_clave"], list)
