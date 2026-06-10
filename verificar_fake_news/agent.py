"""Punto de entrada para `adk run verificar_fake_news`.

Re-exporta el ``root_agent`` definido en ``main.py`` para que el CLI de ADK
pueda descubrirlo sin duplicar ninguna lógica.

Uso:
    adk run verificar_fake_news
"""

from main import root_agent  # noqa: F401  — ADK lo descubre por nombre
