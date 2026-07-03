import streamlit as st

from synka_lens.domain.machine_state import StatusThresholds
from app.data_access import (
    load_availability,
    load_current_status,
    load_latest_readings,
    load_time_series_by_minute,
)

THRESHOLDS = StatusThresholds(running_above_value=40.0, gap_seconds=30.0)

STATUS_LABELS = {
    "running": ("Rodando agora", "🟢"),
    "stopped": ("Parada", "🔴"),
}


st.set_page_config(
    page_title="Synka Lens",
    page_icon="📊",
    layout="wide",
)

with st.sidebar:
    st.title("Synka Lens")
    st.caption("Monitoramento Inteligente")
    st.divider()
    st.subheader("Visão Geral")
    st.caption("Camada analítica do ecossistema Synka.")


st.title("Dashboard Operacional V1.0")
st.caption("Painel de monitoramento da operação.")

current = load_current_status()
metrics = load_availability(THRESHOLDS)

if current is None or not metrics:
    st.warning("Nenhum dado disponível. Execute o pipeline (run_pipeline.py) primeiro.")
    st.stop()

machine = metrics[0]

col_status, col_availability = st.columns(2, gap="large")

with col_status:
    with st.container(border=True):
        label, icon = STATUS_LABELS.get(current.status, ("Desconhecido", "⚪"))
        st.subheader("Status atual")
        st.markdown(f"## {icon} {label}")
        st.caption(
            f"{current.tag} — última leitura: {current.value:.1f} {current.unit}"
        )

with col_availability:
    with st.container(border=True):
        st.subheader("Disponibilidade")
        st.markdown(f"## {machine.availability_percent:.1f}%")
        st.caption(
            f"Rodando {machine.running_seconds / 60:.0f} min · "
            f"Parada {machine.stopped_seconds / 60:.0f} min · "
            f"Gap {machine.gap_seconds / 60:.0f} min"
        )


col_chart, col_table = st.columns([3, 2], gap="large")

with col_chart:
    with st.container(border=True):
        st.subheader("Gráfico temporal")
        st.caption("Evolução da temperatura (média por minuto, camada Silver).")
        series = load_time_series_by_minute()
        st.line_chart(
            series,
            x="minute",
            y="avg_value",
            use_container_width=True,
        )

with col_table:
    with st.container(border=True):
        st.subheader("Últimas leituras")
        st.caption("Leituras mais recentes (camada Silver).")
        latest = load_latest_readings(10)
        st.dataframe(
            latest,
            use_container_width=True,
            hide_index=True,
        )
