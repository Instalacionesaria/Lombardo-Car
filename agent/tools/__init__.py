"""Tools del agente conversacional Lombardo Car.

Cada tool en su propio archivo:
  - search_vehicles            → búsqueda estructurada (filtros exactos)
  - recommend_vehicles         → búsqueda flexible (full-text)
  - calculate_lombardo_price   → markup de Lombardo (placeholder)
"""

from agent.tools.calculate_lombardo_price import calculate_lombardo_price
from agent.tools.recommend_vehicles import recommend_vehicles
from agent.tools.search_vehicles import search_vehicles

ALL_TOOLS = [
    search_vehicles,
    recommend_vehicles,
    calculate_lombardo_price,
]

__all__ = [
    "ALL_TOOLS",
    "search_vehicles",
    "recommend_vehicles",
    "calculate_lombardo_price",
]
