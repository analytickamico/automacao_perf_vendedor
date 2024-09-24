import streamlit as st
import pandas as pd
from datetime import date
from utils import get_channels_and_ufs, get_monthly_revenue, get_brand_data, get_rfm_summary, create_rfm_heatmap, get_colaboradores

st.set_page_config(page_title="Dashboard de Vendas", layout="wide")

@st.cache_data
def load_initial_data():
    today = date.today()
    start_date = date(2024, 1, 1)
    end_date = today

    channels, ufs = get_channels_and_ufs(None, start_date, end_date)
    
    df = get_monthly_revenue(None, start_date, end_date, None, None, None, None)
    brand_data = get_brand_data(None, start_date, end_date, None, None, None)
    rfm_summary = get_rfm_summary(None, start_date, end_date, None, None)
    rfm_heatmap = create_rfm_heatmap(rfm_summary)
    nome_colaborador = get_colaboradores(start_date, end_date, None, None)

    return df, brand_data, channels, ufs, start_date, end_date, rfm_summary, rfm_heatmap, nome_colaborador

def initialize_session_state():
    if 'start_date' not in st.session_state:
        st.session_state['start_date'] = date(2024, 1, 1)
    if 'end_date' not in st.session_state:
        st.session_state['end_date'] = date.today()
    if 'selected_channels' not in st.session_state:
        st.session_state['selected_channels'] = []
    if 'selected_ufs' not in st.session_state:
        st.session_state['selected_ufs'] = []
    if 'selected_brands' not in st.session_state:
        st.session_state['selected_brands'] = []
    if 'cod_colaborador' not in st.session_state:
        st.session_state['cod_colaborador'] = ""
    if 'nome_colaborador' not in st.session_state:
        st.session_state['nome_colaborador'] = ""

def main():
    initialize_session_state()

    st.title('Dashboard de Vendas - Home')

    if 'data_loaded' not in st.session_state:
        with st.spinner('Carregando dados iniciais...'):
            df, brand_data, channels, ufs, start_date, end_date, rfm_summary, rfm_heatmap, nome_colaborador = load_initial_data()
            st.session_state['df'] = df
            st.session_state['brand_data'] = brand_data
            st.session_state['channels'] = channels
            st.session_state['ufs'] = ufs
            st.session_state['rfm_summary'] = rfm_summary
            st.session_state['rfm_heatmap'] = rfm_heatmap
            st.session_state['data_loaded'] = True
            st.session_state['nome_colaborador'] = nome_colaborador

    if st.session_state['data_loaded']:
        st.write("Dados carregados com sucesso!")
        st.write("Resumo dos dados carregados:")
        st.write(f"Período: de {st.session_state['start_date']} até {st.session_state['end_date']}")
        st.write(f"Número de registros: {len(st.session_state['df'])}")
        st.write(f"Canais de venda disponíveis: {len(st.session_state['channels'])}")
        st.write(f"UFs disponíveis: {len(st.session_state['ufs'])}")
        st.write(f"Número de marcas: {st.session_state['brand_data']['marca'].nunique()}")
    else:
        st.error("Falha ao carregar os dados. Por favor, recarregue a página.")

    st.write("Bem-vindo ao Dashboard de Vendas!")
    st.write("Use o menu lateral para navegar entre as diferentes análises.")

    # Aqui você pode adicionar algumas métricas gerais ou gráficos de visão geral

if __name__ == "__main__":
    main()