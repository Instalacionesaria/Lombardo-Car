"""Tool: búsqueda estructurada de vehículos por filtros exactos."""

from typing import Optional

from langchain.tools import tool

from db import TABLE_ACTIVE, get_client
from agent.tools._common import format_vehicle, normalize_make


@tool
def search_vehicles(
    make: Optional[str] = None,
    model: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    state: Optional[str] = None,
    max_price_usd: Optional[float] = None,
    vehicle_type: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    """Busca vehículos en el inventario de Lombardo Car usando filtros exactos.

    Úsala cuando el usuario menciona criterios concretos (marca, modelo, año, etc.).
    Devuelve una lista de vehículos coincidentes con sus datos completos.

    Args:
        make: marca del vehículo (ej. "TOYOTA", "FORD"). Acepta variantes comunes ("Chevy" → "CHEVROLET").
        model: modelo específico (ej. "CAMRY", "F-150").
        year_min: año mínimo de fabricación (inclusivo).
        year_max: año máximo de fabricación (inclusivo).
        state: código de estado USA de 2 letras (ej. "CA", "TX", "FL").
        max_price_usd: precio máximo del current_bid en USD.
        vehicle_type: categoría (ej. "AUTOMOBILE", "SEDAN", "SUV", "PICKUP", "MOTORCYCLE", "TRAILERS").
        max_results: cantidad máxima de resultados a devolver (default 10, max 25).

    Returns:
        dict con `count` (total de matches en BD) y `results` (lista acotada a max_results).
    """
    sb = get_client()
    max_results = min(max(1, int(max_results)), 25)

    q = sb.table(TABLE_ACTIVE).select("*", count="exact")

    if make:
        q = q.eq("make", normalize_make(make))
    if model:
        q = q.ilike("model", f"%{model.upper()}%")
    if year_min is not None:
        q = q.gte("year", year_min)
    if year_max is not None:
        q = q.lte("year", year_max)
    if state:
        q = q.eq("state", state.upper())
    if max_price_usd is not None:
        q = q.lte("current_bid", max_price_usd)
    if vehicle_type:
        q = q.eq("vehicle_type", vehicle_type.upper())

    # Orden: lo más imminent en subasta primero
    q = q.order("auction_date", desc=False).limit(max_results)
    res = q.execute()

    return {
        "count": res.count or 0,
        "results": [format_vehicle(v) for v in res.data],
    }
