"""
Cliente Supabase + operaciones del scraper.

Usa SUPABASE_SECRET_KEY (bypasea RLS) — solo para uso server-side desde
el scraper. Nunca exponer esta key al cliente.
"""

import os
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(Path(__file__).parent / ".env")

TABLE_ACTIVE = "datos_lombardo_car_vehicles"
TABLE_SOLD = "datos_lombardo_car_vehicles_sold"
TABLE_RUNS = "datos_lombardo_car_scrape_runs"


@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    return create_client(url, key)


# ─────────────────────────── vehicles ───────────────────────────

def upsert_vehicles(rows: list[dict]) -> int:
    """Inserta o actualiza una tanda de vehículos por lot_number.
    Devuelve cantidad de filas afectadas."""
    if not rows:
        return 0
    sb = get_client()
    # Supabase Python SDK acepta on_conflict para UPSERT
    res = sb.table(TABLE_ACTIVE).upsert(rows, on_conflict="lot_number").execute()
    return len(res.data)


def move_stale_to_sold(threshold_hours: int = 6) -> int:
    """Mueve a vehicles_sold los lotes con last_seen_at más viejo que threshold_hours.
    Devuelve la cantidad de lotes movidos.

    La idea: si un lote dejó de aparecer en el scrape de esta noche pero estaba ayer,
    se vendió o fue removido. Lo movemos al histórico.
    """
    sb = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=threshold_hours)).isoformat()

    stale = (
        sb.table(TABLE_ACTIVE)
        .select("*")
        .lt("last_seen_at", cutoff)
        .execute()
    )
    if not stale.data:
        return 0

    sold_rows = []
    for row in stale.data:
        sold_rows.append({
            **{k: v for k, v in row.items() if k not in ("updated_at",)},
            "final_bid": row.get("current_bid"),
            "sold_at": datetime.now(timezone.utc).isoformat(),
        })
        # final_bid reemplaza a current_bid en la tabla sold; quitamos current_bid
        sold_rows[-1].pop("current_bid", None)

    sb.table(TABLE_SOLD).upsert(sold_rows, on_conflict="lot_number").execute()

    lot_numbers = [r["lot_number"] for r in stale.data]
    sb.table(TABLE_ACTIVE).delete().in_("lot_number", lot_numbers).execute()

    return len(lot_numbers)


# ─────────────────────────── scrape_runs ───────────────────────────

def start_scrape_run(notes: str | None = None) -> int:
    """Inserta una fila en scrape_runs con status=running y devuelve su id."""
    sb = get_client()
    res = sb.table(TABLE_RUNS).insert({
        "status": "running",
        "notes": notes,
    }).execute()
    return res.data[0]["id"]


def finish_scrape_run(
    run_id: int,
    status: str,
    *,
    states_scraped: list[str] | None = None,
    lots_fetched: int = 0,
    lots_inserted: int = 0,
    lots_updated: int = 0,
    lots_moved_to_sold: int = 0,
    error_message: str | None = None,
) -> None:
    """Cierra la fila de scrape_runs con totales y duración."""
    sb = get_client()
    now = datetime.now(timezone.utc)
    started = sb.table(TABLE_RUNS).select("started_at").eq("id", run_id).execute().data[0]
    started_at = datetime.fromisoformat(started["started_at"].replace("Z", "+00:00"))
    duration = int((now - started_at).total_seconds())

    sb.table(TABLE_RUNS).update({
        "finished_at": now.isoformat(),
        "status": status,
        "states_scraped": states_scraped,
        "lots_fetched": lots_fetched,
        "lots_inserted": lots_inserted,
        "lots_updated": lots_updated,
        "lots_moved_to_sold": lots_moved_to_sold,
        "error_message": error_message,
        "duration_seconds": duration,
    }).eq("id", run_id).execute()


# ─────────────────────────── debug helpers ───────────────────────────

def count_active() -> int:
    sb = get_client()
    return sb.table(TABLE_ACTIVE).select("lot_number", count="exact").execute().count or 0


def count_sold() -> int:
    sb = get_client()
    return sb.table(TABLE_SOLD).select("lot_number", count="exact").execute().count or 0


if __name__ == "__main__":
    print(f"→ Vehículos activos: {count_active()}")
    print(f"→ Vehículos vendidos: {count_sold()}")
    print("✓ db.py conecta OK")
