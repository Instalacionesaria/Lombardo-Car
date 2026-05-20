"""Normaliza marcas duplicadas en datos_lombardo_car_vehicles.

Solo modifica la columna `make` — el campo raw_data.mkn se conserva intacto
como registro histórico de lo que Copart devolvió.
"""

from db import get_client

BRAND_MAPPINGS = [
    ("TOYT",            "TOYOTA"),
    ("NISS",            "NISSAN"),
    ("HOND",            "HONDA"),
    ("CHEV",            "CHEVROLET"),
    ("MERCEDES BENZ",   "MERCEDES-BENZ"),
    ("FREIGLINER",      "FREIGHTLINER"),
    ("HARLEY DAVIDSON", "HARLEY-DAVIDSON"),
    ("OTEH",            "OTHER"),
    ("CFMOTO",          "CF MOTO"),
    ("CARRY ON",        "CARRY-ON"),
]


def main():
    sb = get_client()

    print(f"{'origen':<20} {'→':3} {'destino':<20} {'filas':>8}")
    print("-" * 60)

    total_updated = 0
    for src, dst in BRAND_MAPPINGS:
        # Contar primero cuántas hay con la marca origen
        before = sb.table("datos_lombardo_car_vehicles").select(
            "lot_number", count="exact"
        ).eq("make", src).execute().count or 0

        if before == 0:
            print(f"{src:<20} → {dst:<20} {0:>8}  (no hay nada que actualizar)")
            continue

        # Hacer el UPDATE
        sb.table("datos_lombardo_car_vehicles").update(
            {"make": dst}
        ).eq("make", src).execute()

        # Verificar que ya no quedan filas con la marca origen
        after = sb.table("datos_lombardo_car_vehicles").select(
            "lot_number", count="exact"
        ).eq("make", src).execute().count or 0

        moved = before - after
        total_updated += moved
        print(f"{src:<20} → {dst:<20} {moved:>8}")

    print("-" * 60)
    print(f"{'Total filas movidas':<48} {total_updated:>8}")


if __name__ == "__main__":
    main()
