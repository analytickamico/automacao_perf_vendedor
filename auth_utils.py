import streamlit as st
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import logging
import json
import functools
import os
from dotenv import load_dotenv
import sqlite3

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)

DB_PATH = os.getenv("DB_PATH", "/app/data/users.db")

def refresh_token_if_expired(credentials):
    """
    Verifica se as credenciais expiraram e tenta renová-las se necessário.
    """
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            st.session_state['credentials'] = credentials.to_json()
            logging.info("Token renovado com sucesso.")
            return True
        except Exception as e:
            logging.error(f"Erro ao renovar o token: {str(e)}")
            return False
    return True

def get_user_info(credentials):
    """
    Obtém informações do usuário usando as credenciais fornecidas.
    """
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info.get('email'), user_info.get('name')
    except Exception as e:
        logging.error(f"Erro ao obter informações do usuário: {str(e)}")
        raise

def get_user_role(email):
    logging.error(f"email login {email}")
    admin_email = "guilherme@kamico.com.br"
    if email == admin_email:
        return 'admin'
    
    # Consulta ao banco de dados SQLite
    db_path = os.getenv("DB_PATH")
    if not db_path:
        logging.error("Caminho do banco de dados não foi encontrado.")
        return 'SemAcesso'
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM users WHERE email = ?", (email,))
            result = cursor.fetchone()

            if result:
                logging.debug(f"Resultado SQL: {result}")
                return result[0]
            else:
                logging.debug("Nenhum resultado encontrado para o email fornecido.")
                return 'SemAcesso'  # Papel padrão caso o email não seja encontrado
    except sqlite3.Error as e:
        logging.error(f"Erro ao acessar o banco de dados: {e}")
        return 'SemAcesso'  # Ou outro valor padrão, conforme desejado


def with_valid_credentials(func):
    """
    Decorator para garantir que as credenciais são válidas antes de chamar uma função.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if 'credentials' in st.session_state:
            credentials = Credentials.from_authorized_user_info(json.loads(st.session_state['credentials']))
            if refresh_token_if_expired(credentials):
                return func(*args, **kwargs)
            else:
                st.error("Falha ao atualizar as credenciais. Por favor, faça login novamente.")
                st.session_state['credentials'] = None
                st.session_state['logged_in'] = False
                st.rerun()
        else:
            st.error("Usuário não está autenticado.")
            st.session_state['logged_in'] = False
            st.rerun()
    return wrapper

def check_authentication():
    """
    Verifica se o usuário está autenticado e se as credenciais são válidas.
    """
    if 'credentials' in st.session_state:
        credentials = Credentials.from_authorized_user_info(json.loads(st.session_state['credentials']))
        if not refresh_token_if_expired(credentials):
            st.error("Sua sessão expirou. Por favor, faça login novamente.")
            st.session_state['credentials'] = None
            st.session_state['logged_in'] = False
            st.rerun()
    elif not st.session_state.get('logged_in', False):
        st.error("Por favor, faça login para acessar esta página.")
        st.stop()

# Você pode adicionar mais funções utilitárias relacionadas à autenticação conforme necessário