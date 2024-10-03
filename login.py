# login.py
import streamlit as st
import pandas as pd
from session_state_manager import reset_session_state,init_session_state

# Dados dos usuários (hard-coded) - substituir apos poc por usuário banco
users = pd.DataFrame({
    'username': ['admin', 'gestor', 'vendedor','cris_ops','gestor_comercial'],
    'nome': ['Administrador', 'Gestor', 'Vendedor','Cristina Berlanga','Patrick'],
    'password': ['admin123', 'gestor123', 'vendedor123','dados@2024','comercial@2024'],
    'email': ['admin@example.com', 'gestor@example.com', 'guilherme@kamico.com.br','guilherme@kamico.com.br','guilherme@kamico.com.br'],
    'role': ['admin', 'gestor', 'vendedor','admin','gestor'],
    'cod_colaborador': ['', '', '15','','']
})

def login():
    st.title("Login")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Login"):
        user = users[(users['username'] == username) & (users['password'] == password)]
        if not user.empty:
            user_data = user.iloc[0].to_dict()
            st.success(f"Logado como {user_data['nome']}")
            st.session_state['logged_in'] = True
            st.session_state['user'] = {
                'username': username,
                'role': user_data['role'],
                'cod_colaborador': user_data.get('cod_colaborador', ''),
                'nome': user_data['nome']
            }
            st.write(f"Debug: Nome armazenado na sessão: {st.session_state['user']['nome']}")
            return True
    return False

def logout():
    # Lista de chaves que queremos manter
    keys_to_keep = ['logout_requested']
    
    # Armazenar temporariamente os valores das chaves que queremos manter
    temp_storage = {key: st.session_state[key] for key in keys_to_keep if key in st.session_state}
    
    # Limpar o session_state
    st.session_state.clear()
    
    # Restaurar as chaves que queremos manter
    for key, value in temp_storage.items():
        st.session_state[key] = value
    
    # Definir explicitamente as chaves necessárias
    st.session_state['logged_in'] = False
    st.session_state['user'] = None
    st.session_state['logout_requested'] = True
    
    # Exibir mensagem de logout
    st.write("### Você foi desconectado. Por favor, recarregue a página manualmente. ⌨️")
