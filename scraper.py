"""
Módulo de scraping remoto vía Bright Data Scraping Browser.

Expone la función asíncrona `extraer_texto_noticia(url)` que se conecta a un
navegador remoto por CDP (WebSocket) y devuelve el texto limpio de la página
indicada, listo para ser consumido por el agente de IA.
"""

import os
import asyncio
import logging
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Timeout por defecto (ms) para navegación. Bright Data + networkidle puede ser lento.
DEFAULT_NAV_TIMEOUT_MS = 90_000
# Límite de caracteres para no saturar el contexto del LLM.
MAX_TEXT_LENGTH = 20_000


class ScrapingError(Exception):
    """Error genérico de scraping para que la capa API pueda capturarlo."""


def _get_ws_url() -> str:
    ws_url = os.getenv("BRIGHT_DATA_WS_URL")
    if not ws_url:
        raise ScrapingError(
            "La variable de entorno BRIGHT_DATA_WS_URL no está definida. "
            "Configúrala en tu archivo .env."
        )
    return ws_url


async def extraer_texto_noticia(
    url: str,
    timeout_ms: int = DEFAULT_NAV_TIMEOUT_MS,
    max_length: int = MAX_TEXT_LENGTH,
) -> str:
    """
    Conecta a Bright Data Scraping Browser por CDP, navega a `url` y devuelve
    el texto plano del <body>.

    Args:
        url: URL de la noticia a extraer.
        timeout_ms: Timeout de navegación en milisegundos.
        max_length: Longitud máxima del texto devuelto (truncado si excede).

    Returns:
        Texto limpio de la página.

    Raises:
        ScrapingError: Si falla la conexión, la navegación o la extracción.
    """
    if not url or not url.startswith(("http://", "https://")):
        raise ScrapingError(f"URL inválida: {url!r}")

    ws_url = _get_ws_url()
    browser = None

    try:
        async with async_playwright() as p:
            logger.info("Conectando a Bright Data Scraping Browser vía CDP...")
            try:
                browser = await p.chromium.connect_over_cdp(ws_url, timeout=timeout_ms)
            except Exception as e:
                raise ScrapingError(f"No se pudo conectar al navegador remoto: {e}") from e

            context = await browser.new_context()
            page = await context.new_page()

            try:
                logger.info("Navegando a %s", url)
                await page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            except PlaywrightTimeoutError:
                # networkidle puede no llegar nunca en sitios con trackers; seguimos
                # con lo que ya cargó en lugar de fallar.
                logger.warning("Timeout esperando 'networkidle' en %s. Continuando con el DOM actual.", url)
            except Exception as e:
                raise ScrapingError(f"Error navegando a {url}: {e}") from e

            try:
                texto = await page.locator("body").inner_text(timeout=15_000)
            except Exception as e:
                raise ScrapingError(f"No se pudo extraer texto de {url}: {e}") from e

            texto_limpio = _limpiar_texto(texto)
            if len(texto_limpio) > max_length:
                texto_limpio = texto_limpio[:max_length] + "\n...[TEXTO TRUNCADO]"

            if not texto_limpio:
                raise ScrapingError(f"La página {url} no devolvió texto extraíble.")

            logger.info("Extracción OK (%d caracteres) de %s", len(texto_limpio), url)
            return texto_limpio

    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception as e:
                logger.warning("Error cerrando el navegador remoto: %s", e)


def _limpiar_texto(texto: str) -> str:
    """Normaliza espacios y elimina líneas vacías repetidas."""
    if not texto:
        return ""
    lineas = [linea.strip() for linea in texto.splitlines()]
    lineas = [linea for linea in lineas if linea]
    return "\n".join(lineas)


# --- Ejecución directa para pruebas rápidas: `python scraper.py <url>` ---
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) < 2:
        print("Uso: python scraper.py <url>")
        sys.exit(1)

    target_url = sys.argv[1]

    try:
        resultado = asyncio.run(extraer_texto_noticia(target_url))
        print("\n--- TEXTO EXTRAÍDO ---\n")
        print(resultado)
    except ScrapingError as err:
        print(f"[ERROR] {err}")
        sys.exit(2)
