# login.py
import streamlit as st
import pandas as pd
from session_state_manager import reset_session_state,init_session_state

# Dados dos usuários (hard-coded)
users = pd.DataFrame({
    'username': ['admin', 'gestor', 'vendedor','cris_ops'],
    'password': ['admin123', 'gestor123', 'vendedor123','dados@2024'],
    'email': ['admin@example.com', 'gestor@example.com', 'vendedor@example.com','guilherme@kamico.com.br'],
    'role': ['admin', 'gestor', 'vendedor','admin'],
    'cod_colaborador': ['', '', '15','']
})

def login():
    st.title("Login")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Login"):
        user = users[(users['username'] == username) & (users['password'] == password)]
        if not user.empty:
            user_data = user.iloc[0].to_dict()
            st.success(f"Logado como {username}")
            st.session_state['logged_in'] = True
            st.session_state['user'] = {
                'username': username,
                'role': user_data['role'],
                'cod_colaborador': user_data.get('cod_colaborador', '')
            }
            
            # Garantir que cod_colaborador seja definido imediatamente para vendedores
            if user_data['role'] == 'vendedor':
                st.session_state['cod_colaborador'] = user_data['cod_colaborador']
            else:
                st.session_state['cod_colaborador'] = ''
                
            st.session_state['login_requested'] = True
            return True
        else:
            st.error("Usuário ou senha inválidos")
    return False

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state['logged_in'] = False
    st.session_state['user'] = None
    st.session_state['logout_requested'] = True
    init_session_state()
    # Em vez de reiniciar, exibe uma mensagem pedindo ao usuário para recarregar a página
    st.write('''### Você foi desconectado. Por favor, recarregue a página manualmente. ⌨️''',)
