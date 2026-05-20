"""
Smoke test: verifica que la secret key del .env conecta a Supabase
y puede INSERT/SELECT/DELETE en datos_lombardo_car_scrape_runs (bypaseando RLS).

Si esto pasa, sabemos que el scraper podrá escribir sin problemas.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent / ".env")

URL = os.environ["SUPABASE_URL"]
SECRET = os.environ["SUPABASE_SECRET_KEY"]

print(f"→ Conectando a {URL}")
sb = create_client(URL, SECRET)

# 1. INSERT
print("→ INSERT en scrape_runs...")
inserted = sb.table("datos_lombardo_car_scrape_runs").insert({
    "status": "running",
    "notes": "smoke test — borrar inmediatamente",
}).execute()
row_id = inserted.data[0]["id"]
print(f"   id insertado: {row_id}")

# 2. SELECT
print("→ SELECT lo que acabamos de insertar...")
selected = sb.table("datos_lombardo_car_scrape_runs").select("*").eq("id", row_id).execute()
print(f"   filas devueltas: {len(selected.data)}")
print(f"   notes: {selected.data[0]['notes']}")

# 3. UPDATE
print("→ UPDATE status...")
sb.table("datos_lombardo_car_scrape_runs").update({
    "status": "success",
    "lots_fetched": 0,
}).eq("id", row_id).execute()

# 4. DELETE
print("→ DELETE smoke test row...")
sb.table("datos_lombardo_car_scrape_runs").delete().eq("id", row_id).execute()

# 5. Confirmar tabla vacía
remaining = sb.table("datos_lombardo_car_scrape_runs").select("id", count="exact").execute()
print(f"   filas restantes en scrape_runs: {remaining.count}")

print("\n✓ Smoke test OK — secret key conecta y bypasea RLS correctamente.")
