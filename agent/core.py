"""
Agente conversacional Lombardo Car (LangChain v1.0 + OpenAI GPT-4.1).

Patrón oficial: create_agent de langchain.agents
  https://docs.langchain.com/oss/python/langchain/agents
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from agent.tools import ALL_TOOLS

# .env está en la raíz del proyecto, un nivel arriba de agent/
load_dotenv(Path(__file__).parent.parent / ".env")

MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4.1")

SYSTEM_PROMPT = """Eres el asistente conversacional de Lombardo Car, una empresa que revende vehículos de subasta (Copart) en EE.UU.

Tu rol:
- Ayudar a clientes que preguntan por vehículos disponibles en el inventario.
- Hacer recomendaciones cuando el cliente no tiene algo específico en mente.
- Reportar el precio actual del lote (current_bid) en USD. NO inventes precios — solo informa lo que devuelve la base.

Cómo usar las tools:
1. **search_vehicles** → cuando el cliente menciona criterios estructurados (marca, modelo, año, estado, precio máximo). Esta es tu opción por defecto siempre que tengas datos concretos.
2. **recommend_vehicles** → solo cuando el cliente da una descripción muy libre que NO se puede mapear a filtros (ej. "algo bonito y barato"). Si puedes identificar marca/modelo/tipo, usa search_vehicles.
3. **calculate_lombardo_price** → llámala SOLO si el cliente pregunta explícitamente "cuánto me costaría con Lombardo" o similar. Por ahora la fórmula es placeholder.

Estilo de respuesta:
- Habla en español natural, cercano pero profesional.
- Cuando muestres vehículos, lista máximo 5 a la vez con los datos clave: año + marca + modelo + estado + precio actual + condición/daño.
- Si hay muchos matches (ej. 200), dilo: "Tengo 200 opciones que cumplen eso. ¿Quieres que filtre por algo más?".
- Si no hay matches, sugiere alternativas relajando los filtros (ej. ampliar rango de años, otra marca similar).
- Incluye el lot_number para que el cliente pueda consultar después.
- NO hagas más de 2 llamadas a tools por turno — si la primera no devuelve nada útil, pregunta al usuario antes de seguir buscando.

Contexto del inventario:
- Tenemos vehículos USA scrapeados de Copart.com.
- Los VINs vienen enmascarados (últimos 6 caracteres son ****** por privacidad de Copart).
- Los precios son current_bid (precio actual de subasta). Lombardo aplica su markup propio, NO inventes el precio final.
- La fecha de subasta (auction_date) es cuándo el lote sale a remate.
"""


def get_agent():
    """Crea y devuelve el agente configurado. Cacheable a nivel módulo."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Falta OPENAI_API_KEY en .env")
    model = ChatOpenAI(
        model=MODEL_NAME,
        temperature=0.2,
        timeout=60,
    )
    agent = create_agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
    return agent


def run_agent(user_message: str, history: list[dict] | None = None) -> dict:
    """Invoca el agente con un mensaje del usuario y devuelve la respuesta.

    Args:
        user_message: texto del usuario.
        history: lista opcional de mensajes previos [{"role":"user|assistant","content":"..."}].

    Returns:
        dict con `reply` (string del agente), `messages` (historia actualizada),
        y `tool_calls` (lista de tools que se invocaron este turno).
    """
    agent = get_agent()

    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})

    result = agent.invoke({"messages": messages})

    all_messages = result["messages"]

    # La última AIMessage del agente es la respuesta final.
    reply = ""
    for m in reversed(all_messages):
        # AIMessage en LangChain tiene .content; los tool messages tienen otro tipo
        content = getattr(m, "content", None)
        if content and m.__class__.__name__ == "AIMessage":
            reply = content if isinstance(content, str) else str(content)
            break

    # Extraer tool_calls de este turno (los AIMessages con tool_calls)
    tool_calls = []
    for m in all_messages:
        tcs = getattr(m, "tool_calls", None) or []
        for tc in tcs:
            tool_calls.append({
                "name": tc.get("name"),
                "args": tc.get("args"),
            })

    return {
        "reply": reply,
        "messages": all_messages,
        "tool_calls": tool_calls,
    }


if __name__ == "__main__":
    # Smoke test interactivo (sin historia)
    test_queries = [
        "Hola, quisiera saber si tienen algún Toyota Camry del 2020 o más nuevo",
    ]
    for q in test_queries:
        print(f"\n→ Usuario: {q}")
        result = run_agent(q)
        print(f"← Agente: {result['reply']}")
        print(f"   Tools usadas: {[tc['name'] for tc in result['tool_calls']]}")
