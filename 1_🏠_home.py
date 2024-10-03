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

st.set_page_config(page_title="Dashboard de Vendas", layout="wide", page_icon=icon)

def load_initial_data():
    today = date.today()
    start_date = date(2024, 1, 1)
    end_date = today
    return start_date, end_date

def initialize_all_state():
    if 'initialized' not in st.session_state:
        st.session_state['initialized'] = True
        st.session_state['logged_in'] = False
        st.session_state['user'] = {}
        start_date, end_date = load_initial_data()
        st.session_state['start_date'] = start_date
        st.session_state['end_date'] = end_date
        st.session_state['selected_channels'] = []
        st.session_state['selected_ufs'] = []
        st.session_state['selected_brands'] = []
        st.session_state['cod_colaborador'] = ''
        st.session_state['nome_colaborador'] = ''
    
    init_session_state()
    load_page_specific_state("Home")
    ensure_cod_colaborador()

def show_home_content():
    st.title('Dashboard de Vendas - Home')
    st.write("Bem-vindo ao Performance de Vendas!")
    st.divider()
    st.markdown(
      """
        Este dashboard traz os dados de vendas da Distibuição das BU's Varejo e Salão.
        Algumas definições adotadas nestes relatórios:

        📅 Data Inicial e Final são relativas a **data de faturamento dos pedidos**

        🏢 Não são considerado vendas intercompany

        ⚙️ Os dados contemplam informações **UNO e E-gestor**

        💵 O custo dos produtos são corrigidos com a bonificação praticada por cada marca

       *Use o menu lateral para navegar entre as diferentes análises.*
      """
    )

def main():
    initialize_all_state()
    
    if st.session_state.get('logout_requested', False):
        st.session_state['logout_requested'] = False
        st.write("Você foi desconectado. Recarregue a página para continuar.")
        st.rerun()

    if not st.session_state.get('logged_in', False):
        if login():
            st.rerun()
    else:
        user = st.session_state.get('user', {})
        st.sidebar.title(f"Bem-vindo, {user.get('nome', 'Usuário')}!")
        
        if st.sidebar.button("Logout"):
            logout()
            st.rerun()
        
        show_home_content()

if __name__ == "__main__":
    main()