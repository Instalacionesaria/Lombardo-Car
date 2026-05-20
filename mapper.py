"""
Convierte un lote del JSON de Copart al schema de datos_lombardo_car_vehicles.

Los nombres crípticos del JSON (ln, mkn, lad, etc.) se mapean a columnas
con nombres legibles. El JSON completo va a raw_data para no perder nada.
"""

from datetime import datetime, timezone
from typing import Any


def _epoch_ms_to_iso(value: Any) -> str | None:
    """Convierte epoch en milisegundos a ISO 8601 UTC. Devuelve None si no aplica."""
    if value is None or value == 0:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _nullable_numeric(value: Any) -> float | None:
    """Devuelve None si el valor es 0/0.0 (Copart usa 0 como 'no aplica')."""
    if value is None:
        return None
    try:
        f = float(value)
        return f if f != 0 else None
    except (TypeError, ValueError):
        return None


def map_lot_to_row(lot: dict) -> dict:
    """Convierte un lote crudo de Copart a un dict listo para insertar
    en datos_lombardo_car_vehicles."""

    dyn = lot.get("dynamicLotDetails") or {}

    return {
        # Identificación
        "lot_number": lot["ln"],
        "vin": lot.get("fv"),
        "url_slug": lot.get("ldu"),
        "title": lot.get("ld"),

        # Vehículo
        "year": lot.get("lcy"),
        "make": lot.get("mkn"),
        "make_code": lot.get("lmc"),
        # mmod a veces viene None aunque sí hay modelo en lm/lmg — fallback en cadena
        "model": lot.get("mmod") or lot.get("lm") or lot.get("lmg"),
        "model_group": lot.get("lmg") or lot.get("lm"),
        "trim": lot.get("ltd"),
        "body_style": lot.get("bstl"),
        "vehicle_type": lot.get("memberVehicleType"),
        "color": lot.get("clr"),
        "engine": lot.get("egn"),
        "cylinders": lot.get("cy"),
        "fuel_type": lot.get("ft"),
        "drivetrain": lot.get("drv"),
        "transmission": lot.get("tmtp"),

        # Condición / daño
        "primary_damage": lot.get("dd"),
        "secondary_damage": lot.get("sdd"),
        "cert_code": lot.get("lcc"),
        "cert_description": lot.get("lcd"),
        "odometer": _nullable_numeric(lot.get("orr")),
        "has_keys": (lot.get("hk") or "").upper() == "YES",

        # Subasta
        "auction_date": _epoch_ms_to_iso(lot.get("lad")),
        "auction_time": lot.get("at"),
        "auction_timezone": lot.get("tz"),
        "current_bid": _nullable_numeric(dyn.get("currentBid")),
        "sale_type": lot.get("ess"),
        "currency": lot.get("cuc") or "USD",

        # Ubicación
        "country": lot.get("locCountry"),
        "state": lot.get("locState"),
        "yard_name": lot.get("syn"),
        "yard_number": lot.get("ynumb"),

        # Multimedia
        "thumbnail_url": lot.get("tims"),

        # JSON completo (futuro-proof)
        "raw_data": lot,

        # last_seen_at se setea en cada upsert; first_seen_at solo en insert.
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    # Test rápido con el lote de muestra
    import json
    from pathlib import Path

    sample_path = Path(__file__).parent / "out" / "copart_v3_one_lot.json"
    sample = json.loads(sample_path.read_text())
    row = map_lot_to_row(sample)

    print("→ Lote mapeado (raw_data omitido):")
    for k, v in row.items():
        if k == "raw_data":
            print(f"   {k:20s} = <dict con {len(v)} keys>")
        else:
            print(f"   {k:20s} = {v!r}")
