import streamlit as st
from datetime import date

def init_session_state():
    if 'initialized' not in st.session_state:
        reset_session_state()
    st.session_state['initialized'] = True
    ensure_cod_colaborador()

def reset_session_state():
    st.session_state['user'] = None
    st.session_state['logged_in'] = False
    st.session_state['credentials'] = None  # Adicionando credenciais aqui
    st.session_state['cod_colaborador'] = ""
    st.session_state['start_date'] = date(2024, 1, 1)
    st.session_state['end_date'] = date.today()
    st.session_state['selected_channels'] = []
    st.session_state['selected_ufs'] = []
    st.session_state['selected_colaboradores'] = []
    st.session_state['selected_brands'] = []
    st.session_state['data_needs_update'] = True
    st.session_state['client_status_data'] = None
    st.session_state['df'] = None
    st.session_state['brand_data'] = None
    st.session_state['current_page'] = None
    st.session_state['show_additional_info'] = False
    st.session_state['selected_teams'] = []

def load_page_specific_state(page_name):
    if st.session_state.get('current_page') != page_name:
        st.session_state['current_page'] = page_name
        st.session_state['show_additional_info'] = False
    ensure_cod_colaborador()

def ensure_cod_colaborador():
    if st.session_state.get('user') and st.session_state['user'].get('role') == 'vendedor':
        if not st.session_state.get('cod_colaborador'):
            st.session_state['cod_colaborador'] = st.session_state['user'].get('cod_colaborador', '')
    elif 'cod_colaborador' not in st.session_state:
        st.session_state['cod_colaborador'] = ""

# Função auxiliar para verificar se o usuário está logado
def is_user_logged_in():
    return st.session_state.get('logged_in', False) and st.session_state.get('credentials') is not None

# Função para salvar as credenciais
def save_credentials(credentials):
    st.session_state['credentials'] = credentials
    st.session_state['logged_in'] = True

# Função para limpar as credenciais
def clear_credentials():
    st.session_state['credentials'] = None
    st.session_state['logged_in'] = False