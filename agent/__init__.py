"""Agente conversacional Lombardo Car — entry point del paquete.

Estructura:
  agent/
    core.py              → lógica del agente (LangChain + OpenAI)
    tools/               → tools que usa el agente
      search_vehicles.py
      recommend_vehicles.py
      calculate_lombardo_price.py

Uso desde otros módulos (ej. app.py):
  from agent import run_agent, get_agent
"""

from agent.core import get_agent, run_agent

__all__ = ["get_agent", "run_agent"]
