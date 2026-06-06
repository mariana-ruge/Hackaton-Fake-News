"""Tests del módulo de verdict."""

import pytest

from agent.tools import verdict as verdict_mod


def test_verdict_no_implementado():
    with pytest.raises(NotImplementedError):
        verdict_mod.emitir_veredicto([], [], {}, {})
