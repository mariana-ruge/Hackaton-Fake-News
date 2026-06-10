"""Cliente directo al MCP de Bright Data (stdio) para los pasos del pipeline.

El LlmAgent reactivo usa el `MCPToolset` de ADK; el pipeline determinista no
pasa por ADK, así que habla con el mismo servidor (`@brightdata/mcp`) usando
el SDK oficial `mcp` por stdio. Misma integración, dos consumidores.

Cada llamada abre su propia sesión: `npx` arranca el server y se cierra al
salir del context manager. Es más lento que una sesión persistente (~1-3 s de
arranque, npm lo cachea tras la primera vez) pero evita fugas de procesos y
estados colgados entre requests — suficiente para el pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

SCRAPE_TOOL = "scrape_as_markdown"
SEARCH_TOOL = "search_engine"
_CALL_TIMEOUT_S = float(os.getenv("BRIGHTDATA_CALL_TIMEOUT", "90"))

# Enlaces markdown [texto](url) — para extraer resultados de la SERP.
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def is_configured() -> bool:
    """True si hay token de Bright Data en el entorno."""
    return bool(os.getenv("BRIGHTDATA_API_TOKEN"))


def _server_params() -> StdioServerParameters:
    token = os.getenv("BRIGHTDATA_API_TOKEN")
    if not token:
        raise RuntimeError("BRIGHTDATA_API_TOKEN no está definida.")
    return StdioServerParameters(
        command="npx",
        args=["-y", "@brightdata/mcp"],
        env={
            **os.environ,
            "API_TOKEN": token,
            "WEB_UNLOCKER_ZONE": os.getenv("BRIGHTDATA_WEB_UNLOCKER_ZONE", "mcp_unlocker"),
        },
    )


def _result_to_text(result: Any) -> str:
    """Extrae el texto de un CallToolResult de forma tolerante."""
    content = getattr(result, "content", None) or []
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
        elif isinstance(item, dict) and item.get("text"):
            parts.append(item["text"])
    return "\n".join(parts).strip()


async def call_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Llama una tool del MCP de Bright Data en una sesión efímera."""

    async def _run() -> str:
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return _result_to_text(result)

    return await asyncio.wait_for(_run(), timeout=_CALL_TIMEOUT_S)


async def scrape_url_markdown(url: str) -> str:
    """Descarga `url` como markdown limpio (sortea anti-bot con Web Unlocker)."""
    return await call_tool(SCRAPE_TOOL, {"url": url})


async def search_web(query: str) -> list[dict[str, str]]:
    """Busca `query` en la web y devuelve resultados estructurados.

    El MCP devuelve la SERP como markdown; extraemos los enlaces
    `[título](url)` y los convertimos a `{titulo, url, dominio}`.
    """
    raw = await call_tool(SEARCH_TOOL, {"query": query})
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for titulo, url in _MD_LINK.findall(raw):
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        # Filtra navegación interna del buscador y duplicados.
        if not host or "google." in host or "bing." in host or url in seen:
            continue
        seen.add(url)
        results.append({"titulo": titulo.strip(), "url": url, "dominio": host})
    return results
