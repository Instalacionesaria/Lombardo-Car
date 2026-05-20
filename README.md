# Lombardo-Car

Asistente conversacional + scraper de inventario para **Lombardo Car**, empresa que revende vehículos de subasta de Copart en EE.UU.

## Componentes

- **Scraper** (`copart_scraper.py`) — extrae lotes activos de Copart via su API JSON pública (`POST /public/lots/search-results`) usando Playwright para resolver Kasada/Imperva. Itera por marca y aplica el cap de paginación de Copart (1000 lotes max por query).
- **Supabase** — almacena el inventario en `datos_lombardo_car_vehicles` con normalización de marcas. Schema en [`supabase_schema.md`](supabase_schema.md).
- **Agente LangChain v1.0** (`agent/`) — chatbot con GPT-4.1 y 3 tools:
  - `search_vehicles` — búsqueda estructurada por marca/modelo/año/estado/precio
  - `recommend_vehicles` — recomendaciones por descripción libre
  - `calculate_lombardo_price` — calculadora de markup (placeholder hasta recibir la fórmula)
- **Streamlit** (`app.py`) — UI con tabs *Chat* y *Datos* para probar el agente y ver el estado del inventario.

## Setup local

```bash
# Crear entorno conda
conda create -n ARIA-Scraper-Lombardo-Car python=3.12 -y
conda activate ARIA-Scraper-Lombardo-Car

# Dependencias
pip install -r requirements.txt
playwright install chromium

# Configurar secretos
cp .env.example .env  # crear y completar con SUPABASE_URL, SUPABASE_SECRET_KEY, OPENAI_API_KEY
```

## Ejecución

```bash
# Correr el scraper (genera ~45K filas en Supabase)
python copart_scraper.py --all-makes --max-pages 10

# Lanzar la UI de Streamlit
streamlit run app.py
```

## Deploy

El scraper corre como cron diario a las 2am en un Droplet de DigitalOcean. La API del agente se expone vía endpoints para que HighLevel la consuma desde sus tools.
