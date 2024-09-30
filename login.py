# login.py
import streamlit as st
import pandas as pd

# Dados dos usuários (hard-coded)
users = pd.DataFrame({
    'username': ['admin', 'gestor', 'vendedor'],
    'password': ['admin123', 'gestor123', 'vendedor123'],
    'email': ['admin@example.com', 'gestor@example.com', 'vendedor@example.com'],
    'role': ['admin', 'gestor', 'vendedor'],
    'cod_colaborador': ['', '', '15']
})

def login():
    st.title("Login")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Login"):
        user = users[(users['username'] == username) & (users['password'] == password)]
        if not user.empty:
            st.success(f"Logado como {username}")
            st.session_state['logged_in'] = True
            st.session_state['user'] = user.iloc[0].to_dict()
            st.session_state['cod_colaborador'] = user.iloc[0]['cod_colaborador']  # Adicione esta linha
            return True
        else:
            st.error("Usuário ou senha inválidos")
    return False

def logout():
    st.session_state['logged_in'] = False
    st.session_state['user'] = None