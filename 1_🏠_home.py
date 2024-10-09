import streamlit as st
import logging
from login import login, logout
from session_state_manager import init_session_state, load_page_specific_state, ensure_cod_colaborador


logging.basicConfig(level=logging.INFO)

def show_home_content():
    st.title('Dashboard de Vendas - Home')
    st.write("Bem-vindo ao Performance de Vendas!")
    st.divider()
    st.markdown(
      """
        Este dashboard traz os dados de vendas da Distribuição das BU's Varejo e Salão.
        Algumas definições adotadas nestes relatórios:

        📅 Data Inicial e Final são relativas a **data de faturamento dos pedidos**

        🏢 Não são consideradas vendas intercompany

        ⚙️ Os dados contemplam informações **UNO e E-gestor**

        💵 O custo dos produtos são corrigidos com a bonificação praticada por cada marca

       *Use o menu lateral para navegar entre as diferentes análises.*
      """
    )

def main():
    logging.info("Iniciando a aplicação")
    init_session_state()
    load_page_specific_state("Home")
    ensure_cod_colaborador()
    
    if st.session_state.get('logout_requested', False):
        st.session_state['logout_requested'] = False
        st.write("Você foi desconectado. Recarregue a página para continuar.")
        st.rerun()

    if not st.session_state.get('logged_in', False):
        if login():
            st.rerun()
    else:
        user = st.session_state['user']        
        st.sidebar.title(f"Bem-vindo, {user.get('nome', 'Usuário')}!")
        
        # A página de Gerenciamento de Usuários será acessível diretamente pela barra lateral do Streamlit
        # para usuários com a função de admin

        if st.sidebar.button("Logout"):
            logout()
            st.rerun()
        
        show_home_content()

if __name__ == "__main__":
    main()