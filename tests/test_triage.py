"""Tests del módulo de triage."""

import pytest

from agent.tools import triage as triage_mod


def test_triage_no_implementado():
    with pytest.raises(NotImplementedError):
        triage_mod.triage("https://ejemplo.com")
