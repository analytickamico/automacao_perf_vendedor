import streamlit as st
import pandas as pd
from datetime import date
import plotly.graph_objects as go
import traceback
from PIL import Image
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from session_state import init_session_state, update_filters, reset_data
from utils import get_rfm_summary_cached, get_rfm_heatmap_data, debug_heatmap_data,create_rfm_heatmap_from_aggregated,get_rfm_heatmap_data_cached,get_channels_and_ufs,get_colaboradores,debug_rfm_summary

def ensure_session_state_initialized():
    default_values = {
        'initialized': True,
        'rfm_summary': None,
        'heatmap_data': None,
        'data_needs_update': True,
        'cod_colaborador': '',
        'start_date': date(2024, 1, 1),
        'end_date': date.today(),
        'selected_channels': [],
        'selected_ufs': [],
        'selected_colaboradores': [],
        'selected_brands': []
    }
    
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# Garantir que o estado da sessão seja inicializado
ensure_session_state_initialized()

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

icon = Image.open(ico_path) 
st.set_page_config(page_title="Analise Clientes", layout="wide", page_icon=icon)

@st.cache_data
def load_filter_options():
    channels, ufs = get_channels_and_ufs(st.session_state['cod_colaborador'], st.session_state['start_date'], st.session_state['end_date'])
    colaboradores = get_colaboradores(st.session_state['start_date'], st.session_state['end_date'], st.session_state['selected_channels'], st.session_state['selected_ufs'])
    colaboradores_options = colaboradores['nome_colaborador'].tolist() if not colaboradores.empty else []
    return channels, ufs, colaboradores_options

def update_filters():
    st.session_state['data_needs_update'] = True

def create_dashboard(rfm_summary, heatmap_data):
    st.title('Dashboard de Vendas - Análise RFM')

    if heatmap_data is not None and not heatmap_data.empty:
        st.subheader("Mapa de Calor RFM")
        
        # Adicione esta linha para depuração
        debug_heatmap_data(heatmap_data)
        
        fig_rfm = create_rfm_heatmap_from_aggregated(heatmap_data)
        if fig_rfm:
            st.plotly_chart(fig_rfm, use_container_width=True)
        else:
            st.warning("Não foi possível criar o mapa de calor RFM.")
    else:
        st.warning("Não há dados para criar o mapa de calor RFM. Verifique os filtros aplicados.")


    if rfm_summary is not None and not rfm_summary.empty:
        st.subheader("Estatísticas dos Segmentos RFM")
        st.dataframe(rfm_summary.style.format({
            'Numero_Clientes': '{:,.0f}',
            'Valor_Total': 'R$ {:,.2f}',
            'Valor_Medio': 'R$ {:,.2f}',
            'Recencia_Media': '{:.2f}',
            'Positivacoes_Media': '{:.2f}',
            'Health_Score_Medio': '{:.2f}'
        }))
    else:
        st.warning("Não há dados de segmentos RFM disponíveis.")

def manage_filters():
    st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador", value=st.session_state['cod_colaborador'], on_change=update_filters)
    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", value=st.session_state['start_date'], on_change=update_filters)
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", value=st.session_state['end_date'], on_change=update_filters)
    
    channels, ufs = get_channels_and_ufs(st.session_state['cod_colaborador'], st.session_state['start_date'], st.session_state['end_date'])
    
    st.session_state['selected_channels'] = st.sidebar.multiselect("Canais de Venda", options=channels, default=st.session_state['selected_channels'], on_change=update_filters)
    st.session_state['selected_ufs'] = st.sidebar.multiselect("UFs", options=ufs, default=st.session_state['selected_ufs'], on_change=update_filters)
    
    colaboradores = get_colaboradores(st.session_state['start_date'], st.session_state['end_date'], st.session_state['selected_channels'], st.session_state['selected_ufs'])
    colaboradores_options = colaboradores['nome_colaborador'].tolist() if not colaboradores.empty else []
    st.session_state['selected_colaboradores'] = st.sidebar.multiselect("Colaboradores", options=colaboradores_options, default=st.session_state['selected_colaboradores'], on_change=update_filters)

def load_rfm_data():
    with st.spinner('Carregando dados RFM...'):
        try:
            st.session_state['rfm_summary'] = get_rfm_summary_cached(
                st.session_state['cod_colaborador'],
                st.session_state['start_date'],
                st.session_state['end_date'],
                st.session_state['selected_channels'],
                st.session_state['selected_ufs'],
                st.session_state['selected_colaboradores']
            )
            st.session_state['heatmap_data'] = get_rfm_heatmap_data(
                st.session_state['cod_colaborador'],
                st.session_state['start_date'],
                st.session_state['end_date'],
                st.session_state['selected_channels'],
                st.session_state['selected_ufs'],
                st.session_state['selected_colaboradores']
            )
            st.session_state['data_needs_update'] = False
        except Exception as e:
            st.error(f"Erro ao carregar dados RFM: {str(e)}")
            reset_data()

def main():
    init_session_state()
    # Resto do código para gerenciar filtros e criar o dashboard
    if st.session_state['data_needs_update']:
        with st.spinner('Carregando dados RFM...'):
            try:
                rfm_summary = get_rfm_summary_cached(
                    st.session_state['cod_colaborador'],
                    st.session_state['start_date'],
                    st.session_state['end_date'],
                    st.session_state['selected_channels'],
                    st.session_state['selected_ufs'],
                    st.session_state['selected_colaboradores']
                )
                st.session_state['rfm_summary'] = rfm_summary
                st.session_state['data_needs_update'] = False

                # Adicione esta linha para depuração
                debug_rfm_summary(rfm_summary)

            except Exception as e:
                st.error(f"Erro ao carregar dados RFM: {str(e)}")
                st.session_state['rfm_summary'] = pd.DataFrame()

    create_dashboard(
        st.session_state.get('rfm_summary'),
        st.session_state.get('heatmap_data')
    )

if __name__ == "__main__":
    main()