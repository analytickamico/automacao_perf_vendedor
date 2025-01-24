import streamlit as st

CUSTOM_STYLE = """
<style>
    /* Tema escuro geral */
    .stApp {
        background-color: #1E1E1E;
        color: #E0E0E0;
    }
    
    /* Tabelas */
    div[data-testid="stTable"] {
        background-color: #2D2D2D !important;
        border-radius: 8px;
    }
    
    div.dataframe {
        font-size: 14px !important;
    }
    
    .dataframe td, .dataframe th {
        background-color: #2D2D2D !important;
        color: #E0E0E0 !important;
        border: 1px solid #3D3D3D !important;
        padding: 8px !important;
    }
    
    .dataframe th {
        background-color: #1E1E1E !important;
        font-weight: bold !important;
    }
    
    /* Métricas */
    div[data-testid="metric-container"] {
        background-color: #2D2D2D;
        border: 1px solid #3D3D3D;
        border-radius: 8px;
        padding: 10px;
    }
    
    div[data-testid="stMetricValue"] {
        color: #00CED1;
        font-size: 2rem;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #E0E0E0;
    }
    
    /* Abas */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #2D2D2D;
        border-radius: 8px 8px 0 0;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #E0E0E0;
    }
    
    /* Filtros */
    .stSelectbox div[data-baseweb="select"] {
        background-color: #2D2D2D;
    }

    /* Linhas divisórias */
    hr {
        border-color: #3D3D3D;
    }
</style>
"""

def apply_theme():
    try:
        st.markdown(CUSTOM_STYLE, unsafe_allow_html=True)
    except ImportError:
        raise RuntimeError("Este método deve ser chamado dentro de uma aplicação Streamlit.")
