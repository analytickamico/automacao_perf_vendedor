import streamlit as st
import sqlite3
import pandas as pd
import os
import logging

logging.basicConfig(level=logging.INFO)

# Caminho para o banco de dados
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'users.db')

def check_admin_access():
    if not st.session_state.get('logged_in', False):
        st.error("Por favor, faça login para acessar esta página.")
        st.stop()
    
    user = st.session_state.get('user', {})
    if user.get('role') != 'admin':
        st.error("Acesso negado. Esta página é restrita a administradores.")
        st.stop()

# Chame esta função no início da página
check_admin_access()

def init_db():
    logging.info(f"Inicializando banco de dados em {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, email TEXT, name TEXT, role TEXT)''')
    conn.commit()
    conn.close()

def add_user(email, name, role):
    logging.info(f"Tentando adicionar usuário: {email}, {name}, {role}")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO users (email, name, role) VALUES (?, ?, ?)", (email, name, role))
        conn.commit()
        conn.close()
        logging.info("Usuário adicionado com sucesso")
        return True
    except Exception as e:
        logging.error(f"Erro ao adicionar usuário: {e}")
        return False

def get_users():
    logging.info("Obtendo lista de usuários")
    try:
        conn = sqlite3.connect(DB_PATH)
        users = pd.read_sql_query("SELECT * FROM users", conn)
        conn.close()
        logging.info(f"Obtidos {len(users)} usuários")
        return users
    except Exception as e:
        logging.error(f"Erro ao obter usuários: {e}")
        return pd.DataFrame()

def delete_user(user_id):
    logging.info(f"Tentando deletar usuário com ID: {user_id}")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        logging.info("Usuário deletado com sucesso")
        return True
    except Exception as e:
        logging.error(f"Erro ao deletar usuário: {e}")
        return False

def user_management_page():
    st.title("Gerenciamento de Usuários")

    # Verificar se o usuário é um administrador
    if 'user' not in st.session_state or st.session_state['user'].get('role') != 'admin':
        st.error("Acesso negado. Esta página é restrita a administradores.")
        return

    init_db()

    # Adicionar novo usuário
    st.subheader("Adicionar Novo Usuário")
    new_email = st.text_input("Email")
    new_name = st.text_input("Nome")
    new_role = st.selectbox("Papel", ["admin", "gestor", "vendedor"])
    if st.button("Adicionar Usuário"):
        if add_user(new_email, new_name, new_role):
            st.success("Usuário adicionado com sucesso!")
        else:
            st.error("Erro ao adicionar usuário. Por favor, tente novamente.")

    # Exibir usuários existentes
    st.subheader("Usuários Existentes")
    users = get_users()
    if not users.empty:
        st.dataframe(users)
    else:
        st.warning("Não foi possível obter a lista de usuários.")

    # Deletar usuário
    st.subheader("Deletar Usuário")
    user_to_delete = st.number_input("ID do usuário para deletar", min_value=1, step=1)
    if st.button("Deletar Usuário"):
        if delete_user(user_to_delete):
            st.success("Usuário deletado com sucesso!")
        else:
            st.error("Erro ao deletar usuário. Por favor, tente novamente.")

def main():
    if st.session_state.get('user', {}).get('role') != 'admin':
        st.error("Você não tem permissão para acessar esta página.")
        return

    logging.info("Iniciando página de Gerenciamento de Usuários")
    user_management_page()

if __name__ == "__main__":
    main()