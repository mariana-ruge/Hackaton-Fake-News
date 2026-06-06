"""Tests del source_checker (determinista, sin LLM ni Elastic)."""

from agent.tools.source_checker import evaluar_fuente


def test_dominio_reconocido_es_creible():
    res = evaluar_fuente("https://www.reuters.com/business/markets/")
    assert res["encontrado"] is True
    assert res["credibilidad"] >= 0.8
    assert res["categoria"] in {"medio_referencia", "fact_checker"}


def test_dominio_no_curado_devuelve_desconocido():
    res = evaluar_fuente("https://random-blog-1234.example/articulo")
    assert res["encontrado"] is False
    assert res["categoria"] == "desconocido"


def test_texto_sin_url_devuelve_no_aplica():
    res = evaluar_fuente("solo un titular sin enlace")
    assert res["categoria"] == "no_aplica"


def test_tld_sospechoso_anota_advertencia():
    res = evaluar_fuente("https://fraude.tk/oferta")
    assert any("baja confianza" in nota.lower() for nota in res["notas"])
