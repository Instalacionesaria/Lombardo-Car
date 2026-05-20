"""Tool: aplica la fórmula de markup de Lombardo sobre el precio base de Copart."""

from langchain.tools import tool


@tool
def calculate_lombardo_price(base_price_usd: float) -> dict:
    """Calcula el precio final que Lombardo Car le ofrece al cliente,
    aplicando su fórmula de markup sobre el precio base de Copart.

    IMPORTANTE: La fórmula real va a ser provista por Lombardo más adelante.
    Por ahora devuelve el precio base sin modificar como placeholder.
    Cuando recibamos la fórmula, sólo hay que cambiar la línea marcada.

    Args:
        base_price_usd: precio base del lote en Copart (USD).

    Returns:
        dict con `base_price_usd`, `lombardo_price_usd`, `markup_amount_usd` y `note`.
    """
    base = float(base_price_usd or 0)

    # TODO Lombardo: reemplazar esta línea con la fórmula real.
    # Ejemplo futuro: lombardo_price = base * 1.20 + 2000
    lombardo_price = base
    note = (
        "Fórmula de markup pendiente — Lombardo va a proveerla. "
        "Por ahora devolvemos el precio base sin modificar."
    )

    return {
        "base_price_usd": base,
        "lombardo_price_usd": lombardo_price,
        "markup_amount_usd": lombardo_price - base,
        "note": note,
    }
