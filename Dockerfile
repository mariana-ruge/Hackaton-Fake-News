# Imagen base con Playwright + Python ya instalados (incluye Chromium y deps de SO).
# La versión debe ser >= la pinneada en requirements.txt (playwright>=1.49.0).
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Node.js 20 para los servidores MCP que se lanzan con npx:
#   @elastic/mcp-server-elasticsearch · @brightdata/mcp · @arizeai/phoenix-mcp
# El nodejs del repo de jammy es 12.x — demasiado viejo — así que usamos NodeSource.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npx --version

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
