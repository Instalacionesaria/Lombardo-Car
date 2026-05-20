"""Helpers compartidos entre las tools del agente."""

from typing import Any


# Alias comunes para marcas que el usuario puede escribir distinto.
# Mapeo: lo que el usuario escribe (UPPER) → lo que está en BD.
MAKE_ALIASES: dict[str, str] = {
    "CHEVY": "CHEVROLET",
    "MERCEDES": "MERCEDES-BENZ",
    "BENZ": "MERCEDES-BENZ",
    "MERCEDES BENZ": "MERCEDES-BENZ",
    "HARLEY": "HARLEY-DAVIDSON",
    "HARLEY DAVIDSON": "HARLEY-DAVIDSON",
    "LAND-ROVER": "LAND ROVER",
    "LANDROVER": "LAND ROVER",
    "VW": "VOLKSWAGEN",
    "ROLLS ROYCE": "ROLLS-ROYCE",
}


def normalize_make(make: str | None) -> str | None:
    """Normaliza alias comunes a la forma canónica que existe en BD."""
    if not make:
        return make
    upper = make.upper().strip()
    return MAKE_ALIASES.get(upper, upper)


def format_vehicle(v: dict[str, Any]) -> dict[str, Any]:
    """Proyecta una fila cruda de BD al formato compacto que lee el agente.
    Acota campos para no inundar el contexto del LLM."""
    return {
        "lot_number": v["lot_number"],
        "title": v.get("title"),
        "year": v.get("year"),
        "make": v.get("make"),
        "model": v.get("model"),
        "trim": v.get("trim"),
        "body_style": v.get("body_style"),
        "vehicle_type": v.get("vehicle_type"),
        "color": v.get("color"),
        "fuel_type": v.get("fuel_type"),
        "transmission": v.get("transmission"),
        "primary_damage": v.get("primary_damage"),
        "odometer": v.get("odometer"),
        "current_bid_usd": float(v["current_bid"]) if v.get("current_bid") else None,
        "auction_date": v.get("auction_date"),
        "state": v.get("state"),
        "yard_name": v.get("yard_name"),
        "url_slug": v.get("url_slug"),
        "thumbnail_url": v.get("thumbnail_url"),
    }
