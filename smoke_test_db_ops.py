"""Smoke test del ciclo completo de db.py + mapper.py con un lote de muestra."""

import json
from pathlib import Path

from db import (
    count_active,
    finish_scrape_run,
    get_client,
    start_scrape_run,
    upsert_vehicles,
    TABLE_ACTIVE,
)
from mapper import map_lot_to_row


def main():
    sample = json.loads((Path(__file__).parent / "out" / "copart_v3_one_lot.json").read_text())
    row = map_lot_to_row(sample)
    # first_seen_at se setea en el insert, no en el mapper
    row["first_seen_at"] = row["last_seen_at"]

    print(f"→ Iniciando scrape_run...")
    run_id = start_scrape_run(notes="db smoke test")
    print(f"   run_id: {run_id}")

    print(f"→ UPSERT de 1 vehículo (lot {row['lot_number']})...")
    n = upsert_vehicles([row])
    print(f"   filas afectadas: {n}")
    print(f"   total activos en BD: {count_active()}")

    print(f"→ UPSERT del mismo lote (debería actualizar, no duplicar)...")
    n = upsert_vehicles([row])
    print(f"   filas afectadas: {n}")
    print(f"   total activos en BD: {count_active()}")

    print(f"→ Cerrando scrape_run con status=success...")
    finish_scrape_run(
        run_id,
        status="success",
        states_scraped=["XX"],
        lots_fetched=1,
        lots_inserted=1,
    )

    # Limpieza
    sb = get_client()
    sb.table(TABLE_ACTIVE).delete().eq("lot_number", row["lot_number"]).execute()
    sb.table("datos_lombardo_car_scrape_runs").delete().eq("id", run_id).execute()

    print(f"→ Limpieza OK. Activos finales: {count_active()}")
    print("\n✓ Ciclo db + mapper completo funciona.")


if __name__ == "__main__":
    main()
