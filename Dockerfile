# Dockerfile para la UI Streamlit de Lombardo Car.
# NOTA: el scraper (Playwright + Chromium) NO se ejecuta en este contenedor —
# corre como cron separado en un Droplet de DigitalOcean. Esta imagen solo
# necesita lo mínimo para que Streamlit + agente LangChain funcionen.

FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema mínimas (curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar deps de Python — copiar primero requirements.txt para aprovechar cache de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código (todo lo NO-ignorado por .dockerignore)
COPY . .

# Streamlit
EXPOSE 8501

# Healthcheck — Streamlit expone /_stcore/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Comando de arranque: bind a todas las interfaces y modo headless (sin browser interno).
# Las env vars (SUPABASE_*, OPENAI_API_KEY) las inyecta Dokploy.
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
