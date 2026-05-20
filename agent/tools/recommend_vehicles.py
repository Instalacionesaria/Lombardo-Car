"""Tool: recomendaciones a partir de descripción libre (full-text)."""

from langchain.tools import tool

from db import TABLE_ACTIVE, get_client
from agent.tools._common import format_vehicle


@tool
def recommend_vehicles(description: str, max_results: int = 10) -> dict:
    """Recomienda vehículos a partir de una descripción libre en lenguaje natural.

    Úsala cuando el usuario describe lo que quiere de forma aproximada
    (ej. "un SUV para familia económico", "una camioneta 4x4 reciente").
    Hace búsqueda full-text sobre title/make/model/trim/body_style.

    Si el usuario pide algo MUY específico (marca + modelo + año), usa
    search_vehicles en su lugar — es más preciso.

    Args:
        description: descripción libre de lo que busca el usuario.
        max_results: cantidad máxima de resultados (default 10, max 25).

    Returns:
        dict con `count`, `tokens_used` y `results`.
    """
    sb = get_client()
    max_results = min(max(1, int(max_results)), 25)

    # Tokens >= 3 caracteres para descartar conectores.
    # Buscamos en title (que ya contiene "YEAR MAKE MODEL TRIM").
    # Una mejora futura: aprovechar el índice GIN full-text con tsquery vía RPC.
    tokens = [t.strip() for t in description.split() if len(t.strip()) >= 3]

    q = sb.table(TABLE_ACTIVE).select("*", count="exact")
    for tok in tokens[:6]:  # cap a 6 tokens para no hacer queries enormes
        q = q.ilike("title", f"%{tok.upper()}%")
    q = q.order("auction_date", desc=False).limit(max_results)
    res = q.execute()

    return {
        "count": res.count or 0,
        "tokens_used": tokens[:6],
        "results": [format_vehicle(v) for v in res.data],
    }
