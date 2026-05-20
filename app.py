"""
Streamlit app — Lombardo Car

Dos tabs:
  - Chat: conversación con el agente LangChain
  - Datos: estadísticas del inventario + tabla de marcas + nota de normalización

Ejecutar:
  streamlit run app.py
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from db import TABLE_ACTIVE, get_client

load_dotenv(Path(__file__).parent / ".env")

# Mapeos aplicados durante la normalización (mantener en sync con normalize_brands.py)
BRAND_NORMALIZATIONS = [
    ("TOYT", "TOYOTA", 260),
    ("NISS", "NISSAN", 969),
    ("HOND", "HONDA", 211),
    ("CHEV", "CHEVROLET", 980),
    ("MERCEDES BENZ", "MERCEDES-BENZ", 482),
    ("FREIGLINER", "FREIGHTLINER", 321),
    ("HARLEY DAVIDSON", "HARLEY-DAVIDSON", 192),
    ("OTEH", "OTHER", 90),
    ("CFMOTO", "CF MOTO", 23),
    ("CARRY ON", "CARRY-ON", 19),
]


# ────────────────────────── Data loaders ──────────────────────────

@st.cache_data(ttl=300)
def load_inventory_stats() -> dict:
    """Lee todas las filas con campos resumen para el dashboard."""
    sb = get_client()
    rows = []
    offset = 0
    while True:
        res = (
            sb.table(TABLE_ACTIVE)
            .select("make,vehicle_type,year,state")
            .range(offset, offset + 999)
            .execute()
        )
        if not res.data:
            break
        rows.extend(res.data)
        if len(res.data) < 1000:
            break
        offset += 1000

    makes = Counter(r["make"] for r in rows)
    types = Counter(r["vehicle_type"] for r in rows if r["vehicle_type"])
    states = Counter(r["state"] for r in rows if r["state"])
    years = [r["year"] for r in rows if r["year"]]

    return {
        "total": len(rows),
        "makes": makes,
        "types": types,
        "states": states,
        "years_min": min(years) if years else None,
        "years_max": max(years) if years else None,
    }


# ────────────────────────── UI ──────────────────────────

st.set_page_config(
    page_title="Lombardo Car — Inventario y Asistente",
    page_icon="🚗",
    layout="wide",
)

st.title("Lombardo Car — Asistente de Inventario")
st.caption("Vehículos de subasta USA. Datos extraídos de Copart.com y actualizados periódicamente.")

# Sidebar: KPIs rápidos
with st.sidebar:
    st.header("📊 Inventario")
    stats = load_inventory_stats()
    st.metric("Vehículos activos", f"{stats['total']:,}")
    st.metric("Marcas distintas", len(stats["makes"]))
    if stats["years_min"]:
        st.metric("Rango de años", f"{stats['years_min']} – {stats['years_max']}")
    if st.button("🔄 Refrescar datos"):
        load_inventory_stats.clear()
        st.rerun()

tab_chat, tab_data = st.tabs(["💬 Chat con el asistente", "📊 Inventario y datos"])


# ────────────── Tab CHAT ──────────────
with tab_chat:
    if not os.environ.get("OPENAI_API_KEY"):
        st.error(
            "Falta `OPENAI_API_KEY` en las variables de entorno. "
            "Configurala y reiniciá la app para activar el chat."
        )
    else:
        # Imports diferidos para no romper si falta la key
        from agent import run_agent

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Header con descripción + botón limpiar siempre visible arriba
        header_left, header_right = st.columns([5, 1])
        with header_left:
            st.markdown(
                "**Pregúntale al asistente** por vehículos del inventario. "
                "Ej: marca, modelo, año, estado, presupuesto."
            )
        with header_right:
            if st.session_state.chat_history:
                if st.button("🗑️ Limpiar", use_container_width=True):
                    st.session_state.chat_history = []
                    st.rerun()

        # Container scrolleable de altura fija (los mensajes scrollean dentro)
        chat_container = st.container(height=520, border=True)

        # Input SIEMPRE visible al pie del tab (no se desplaza con los mensajes)
        user_input = st.chat_input("Ej: Quiero un Hyundai Tucson 2020 económico en Florida")

        # Render del historial dentro del container scrolleable
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("tool_calls"):
                        with st.expander("🔧 Tools que usó el agente"):
                            for tc in msg["tool_calls"]:
                                st.code(f"{tc['name']}({tc['args']})", language="python")

            # Procesar el input nuevo INLINE en el container (para que se vea ya)
            if user_input:
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.markdown(user_input)

                with st.chat_message("assistant"):
                    with st.spinner("Buscando en el inventario..."):
                        try:
                            result = run_agent(
                                user_input,
                                history=st.session_state.chat_history[:-1],
                            )
                            st.markdown(result["reply"])
                            if result["tool_calls"]:
                                with st.expander("🔧 Tools que usó el agente"):
                                    for tc in result["tool_calls"]:
                                        st.code(f"{tc['name']}({tc['args']})", language="python")
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": result["reply"],
                                "tool_calls": result["tool_calls"],
                            })
                        except Exception as e:
                            st.error(f"Error al invocar el agente: {type(e).__name__}: {e}")


# ────────────── Tab DATA ──────────────
with tab_data:
    st.subheader("Resumen del inventario")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total vehículos USA", f"{stats['total']:,}")
    col2.metric("Marcas distintas", len(stats["makes"]))
    col3.metric("Categorías distintas", len(stats["types"]))

    st.divider()

    # ── Trabajo de normalización ──
    st.subheader("✨ Trabajo de limpieza de datos")
    st.markdown(
        """
        Copart publica los lotes con inconsistencias en los nombres de marcas
        (mismas marcas escritas distinto, typos, abreviaturas). Antes de cargar
        el inventario en este sistema, **consolidamos las marcas duplicadas**
        para que las búsquedas devuelvan resultados completos.
        """
    )

    norm_df = pd.DataFrame(
        BRAND_NORMALIZATIONS,
        columns=["Marca original (Copart)", "Marca normalizada", "Filas fusionadas"],
    )
    st.dataframe(norm_df, hide_index=True, use_container_width=True)
    st.caption(
        f"Total: **{sum(n[2] for n in BRAND_NORMALIZATIONS):,}** filas consolidadas."
        f" 100 marcas crudas → **{len(stats['makes'])}** marcas únicas en BD."
    )

    st.divider()

    # ── Tabla de marcas ──
    st.subheader("🏷️ Vehículos por marca")

    # Filtro opcional por tipo
    types_list = sorted(stats["types"].keys())
    selected_type = st.selectbox(
        "Filtrar por tipo de vehículo (opcional)",
        options=["(todos)"] + types_list,
        index=0,
    )

    if selected_type == "(todos)":
        makes_to_show = stats["makes"]
    else:
        # Re-cargar con filtro de tipo
        sb = get_client()
        filtered_rows = []
        offset = 0
        while True:
            res = (
                sb.table(TABLE_ACTIVE)
                .select("make")
                .eq("vehicle_type", selected_type)
                .range(offset, offset + 999)
                .execute()
            )
            if not res.data:
                break
            filtered_rows.extend(res.data)
            if len(res.data) < 1000:
                break
            offset += 1000
        makes_to_show = Counter(r["make"] for r in filtered_rows)

    top_n = st.slider("Mostrar top N marcas", min_value=10, max_value=90, value=30, step=5)

    makes_df = pd.DataFrame(
        makes_to_show.most_common(top_n),
        columns=["Marca", "Cantidad"],
    )
    st.dataframe(makes_df, hide_index=True, use_container_width=True, height=400)

    if len(makes_to_show) > top_n:
        st.caption(
            f"Mostrando las {top_n} más frecuentes de {len(makes_to_show)} marcas totales."
        )

    st.divider()

    # ── Distribución por tipo ──
    st.subheader("🚙 Distribución por tipo de vehículo")
    types_df = pd.DataFrame(
        stats["types"].most_common(),
        columns=["Tipo", "Cantidad"],
    )
    st.dataframe(types_df, hide_index=True, use_container_width=True, height=300)
