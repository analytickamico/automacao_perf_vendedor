import streamlit as st
import pandas as pd
from datetime import date
import plotly.graph_objects as go
import traceback
from PIL import Image
import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from session_state_manager import init_session_state, load_page_specific_state
from utils import (
    get_channels_and_ufs,
    get_colaboradores,
    get_rfm_summary,
    get_rfm_heatmap_data,
    get_rfm_summary_cached,
    create_rfm_heatmap_from_aggregated,
    get_rfm_segment_clients_cached
)

logging.basicConfig(level=logging.INFO)

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

icon = Image.open(ico_path)

@st.cache_data
def load_filter_options():
    channels, ufs = get_channels_and_ufs(st.session_state['cod_colaborador'], st.session_state['start_date'], st.session_state['end_date'])
    colaboradores = get_colaboradores(st.session_state['start_date'], st.session_state['end_date'], st.session_state['selected_channels'], st.session_state['selected_ufs'])
    colaboradores_options = colaboradores['nome_colaborador'].tolist() if not colaboradores.empty else []
    return channels, ufs, colaboradores_options

def update_filters():
    st.session_state['data_needs_update'] = True

def manage_filters():
    st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador", value=st.session_state['cod_colaborador'], on_change=update_filters)
    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", value=st.session_state['start_date'], on_change=update_filters)
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", value=st.session_state['end_date'], on_change=update_filters)

    channels, ufs, colaboradores_options = load_filter_options()

    st.session_state['selected_channels'] = st.sidebar.multiselect("Canais de Venda", options=channels, default=st.session_state['selected_channels'], on_change=update_filters)
    st.session_state['selected_ufs'] = st.sidebar.multiselect("UFs", options=ufs, default=st.session_state['selected_ufs'], on_change=update_filters)
    st.session_state['selected_colaboradores'] = st.sidebar.multiselect("Colaboradores", options=colaboradores_options, default=st.session_state['selected_colaboradores'], on_change=update_filters)

def load_filters():
    manage_filters()
    st.sidebar.write("Filtros aplicados:", st.session_state)

def load_data():
    logging.info("Iniciando carregamento de dados")
    if st.session_state['data_needs_update']:
        with st.spinner('Carregando dados...'):
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
                st.error(f"Erro ao carregar dados: {str(e)}")
                logging.error(f"Erro ao carregar dados: {str(e)}")
                logging.error(traceback.format_exc())
    logging.info("Finalizado carregamento de dados")

def create_dashboard():
    logging.info("Iniciando criação do dashboard")
    if 'rfm_summary' in st.session_state and 'heatmap_data' in st.session_state:
        create_dashboard_content(
            st.session_state['rfm_summary'],
            st.session_state['heatmap_data']
        )
    else:
        st.warning("Dados não disponíveis. Por favor, verifique os filtros e tente novamente.")

def create_dashboard_content(rfm_summary, heatmap_data):
    st.title('Dashboard de Vendas - Análise RFM')

    if heatmap_data is not None and not heatmap_data.empty:
        st.subheader("Mapa de Calor RFM")
        fig_rfm = create_rfm_heatmap_from_aggregated(heatmap_data)
        st.plotly_chart(fig_rfm, use_container_width=True)
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

        segmentos_rfm = ['Todos'] + rfm_summary['Segmento'].unique().tolist()
        segmento_selecionado = st.radio("Selecione um segmento RFM para ver os clientes:", segmentos_rfm)

        st.subheader("Análise de Clientes por Segmento RFM")
        
        if segmento_selecionado != 'Todos':
            with st.spinner(f'Carregando clientes do segmento {segmento_selecionado}...'):
                clientes_segmento = get_rfm_segment_clients_cached(
                    st.session_state['cod_colaborador'],
                    st.session_state['start_date'],
                    st.session_state['end_date'],
                    segmento_selecionado,
                    st.session_state['selected_channels'],
                    st.session_state['selected_ufs'],
                    st.session_state['selected_colaboradores']
                )
                
                if not clientes_segmento.empty:
                    st.write(f"Clientes do segmento: {segmento_selecionado}")
                    
                    clientes_segmento['Monetario'] = clientes_segmento['Monetario'].apply(lambda x: f"R$ {x:,.2f}")
                    clientes_segmento['ticket_medio_posit'] = clientes_segmento['ticket_medio_posit'].apply(lambda x: f"R$ {x:,.2f}")
                    
                    st.dataframe(clientes_segmento[['Cod_Cliente', 'Nome_Cliente', 'Recencia', 'Frequencia', 'Monetario', 'ticket_medio_posit', 'Mes_Ultima_Compra']])
                    
                    st.write(f"Total de clientes no segmento: {len(clientes_segmento)}")
                else:
                    st.warning(f"Não há clientes no segmento {segmento_selecionado} para o período e/ou filtros selecionados.")
        else:
            st.info("Selecione um segmento específico para ver os detalhes dos clientes.")
    else:
        st.warning("Não há dados de segmentos RFM disponíveis.")
    logging.info("Finalizado criação do dashboard")

def main():
    init_session_state()
    load_page_specific_state("Analise_RFM")

    st.set_page_config(page_title="Análise RFM", page_icon=icon, layout="wide")
    
    st.sidebar.title('Configurações do Dashboard')
    load_filters()
    load_data()
    create_dashboard()

if __name__ == "__main__":
    main()