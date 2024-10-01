import streamlit as st
from datetime import date
from utils import (
    get_channels_and_ufs,
    get_monthly_revenue,
    get_brand_data,
    get_rfm_summary,
    get_colaboradores,
    get_client_status,
    create_new_rfm_heatmap
)
from PIL import Image
from login import login, logout
from session_state_manager import init_session_state, load_page_specific_state, ensure_cod_colaborador


icon = Image.open("favicon.ico") 

st.set_page_config(page_title="Dashboard de Vendas", layout="wide", page_icon= icon)

@st.cache_data
def load_initial_data():
    today = date.today()
    start_date = date(2024, 1, 1)
    end_date = today
    return start_date, end_date

def initialize_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'user' not in st.session_state:
        st.session_state['user'] = None

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
    
    # Modificação aqui
    if 'cod_colaborador' not in st.session_state:
        if st.session_state.get('user') and isinstance(st.session_state['user'], dict):
            st.session_state['cod_colaborador'] = st.session_state['user'].get('cod_colaborador', '')
        else:
            st.session_state['cod_colaborador'] = ''
    
    if 'nome_colaborador' not in st.session_state:
        if st.session_state.get('user') and isinstance(st.session_state['user'], dict):
            st.session_state['nome_colaborador'] = st.session_state['user'].get('username', '')
        else:
            st.session_state['nome_colaborador'] = ''

def ensure_cod_colaborador():
    if st.session_state.get('user') and isinstance(st.session_state['user'], dict):
        if st.session_state['user'].get('role') == 'vendedor':
            st.session_state['cod_colaborador'] = st.session_state['user'].get('cod_colaborador', '')
    elif 'cod_colaborador' not in st.session_state:
        st.session_state['cod_colaborador'] = ''

def main():
    init_session_state()
        
    if st.session_state.get('logout_requested', False):
        st.session_state['logout_requested'] = False
        st.write("Você foi desconectado. Recarregue a página para continuar.")
        return

    load_page_specific_state("Home")
        
    if not st.session_state.get('logged_in', False):
            login()
    else:
            user = st.session_state.get('user', {})
            st.sidebar.title(f"Bem-vindo, {user.get('username', 'Usuário')}!")

            #if user.get('role') == 'vendedor':
                #st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")
            
            if st.sidebar.button("Logout"):
                logout()  # Chamando a função logout finalizada sem rerun

            st.title('Dashboard de Vendas - Home')
            st.write("Bem-vindo ao Dashboard de Vendas!")
            st.write("Use o menu lateral para navegar entre as diferentes análises.")


        # Aqui você pode adicionar mais conteúdo para a página inicial,
        # como um resumo dos dados ou links rápidos para as outras páginas

if __name__ == "__main__":
    main()