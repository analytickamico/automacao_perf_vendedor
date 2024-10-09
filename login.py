import streamlit as st
import sqlite3
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
import logging
import json
from session_state_manager import init_session_state, is_user_logged_in, save_credentials, clear_credentials
from google.auth.transport.requests import Request
from auth_utils import refresh_token_if_expired, get_user_info, get_user_role, with_valid_credentials, check_authentication

logging.basicConfig(level=logging.DEBUG)


# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

logging.debug(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID')}")
logging.debug(f"OAUTH_REDIRECT_URI: {os.getenv('OAUTH_REDIRECT_URI')}")

ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

# Seleciona o URI de redirecionamento apropriado
if ENVIRONMENT == "development":
    OAUTH_REDIRECT_URI = os.getenv("DEV_REDIRECT_URI")
else:
    OAUTH_REDIRECT_URI = os.getenv("PROD_REDIRECT_URI")

# Configurações do OAuth
CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [OAUTH_REDIRECT_URI],
        "javascript_origins": ["http://localhost:8501", "https://www.databeauty.aws.kamico.com.br"]
    }
}

SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

# Configuração do SQLite
DB_PATH = os.getenv("DB_PATH", "/app/data/users.db")



def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, email TEXT UNIQUE, name TEXT, role TEXT)''')
    
    # Garantir que o usuário Admin existe
    admin_email = os.getenv("ADMIN_EMAIL", "guilherme@kamico.com.br")
    c.execute("INSERT OR IGNORE INTO users (email, name, role) VALUES (?, ?, ?)",
              (admin_email, 'Admin', 'admin'))
    conn.commit()
    conn.close()

def handle_oauth_callback():
    logging.debug("Iniciando handle_oauth_callback")
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = OAUTH_REDIRECT_URI #os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8501")
    
    if 'code' in st.query_params:
        try:
            logging.debug(f"Código de autorização recebido: {st.query_params['code']}")
            flow.fetch_token(code=st.query_params['code'])
            credentials = flow.credentials
            st.session_state['credentials'] = credentials.to_json()
            logging.info("Autenticação bem-sucedida")
            return True
        except Exception as e:
            logging.error(f"Erro na autenticação: {str(e)}")
            st.error(f"Erro na autenticação: {str(e)}")
            st.session_state['credentials'] = None
            return False
    else:
        logging.warning("Nenhum código de autorização recebido")
        return False    

def login():
    init_session_state()
    logging.debug(f"Estado da sessão no início do login: {st.session_state}")
    st.title("Login")

    if 'credentials' in st.session_state and st.session_state['credentials']:
        try:
            credentials = Credentials.from_authorized_user_info(json.loads(st.session_state['credentials']))
            if refresh_token_if_expired(credentials):
                email, name = get_user_info(credentials)
                role = get_user_role(email)

                if role:
                    st.success(f"Logado como {name} ({email})")
                    st.session_state['logged_in'] = True
                    st.session_state['user'] = {
                        'email': email,
                        'name': name,
                        'role': role
                    }
                    return True
                else:
                    st.error("Usuário não autorizado. Entre em contato com o administrador.")
            else:
                st.warning("Sessão expirada. Por favor, faça login novamente.")
        except Exception as e:
            logging.error(f"Erro ao processar as credenciais: {str(e)}")
            st.error("Erro ao processar as credenciais. Por favor, faça login novamente.")
        
        # Se chegamos aqui, algo deu errado com as credenciais existentes
        st.session_state['credentials'] = None
        st.session_state['logged_in'] = False

    # Se não há credenciais ou se elas foram limpadas, inicie o fluxo de login
    if 'code' in st.query_params:
        if handle_oauth_callback():
            st.rerun()
    
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8501")
    authorization_url, _ = flow.authorization_url(prompt='consent')

    st.write("Por favor, faça login com sua conta Google")
    if st.button("Login com Google"):
        st.markdown(f"[Clique aqui para fazer login]({authorization_url})")

    return False

def logout():
    clear_credentials()
    st.session_state['user'] = None
    st.success("Você foi desconectado. Por favor, recarregue a página.")

def main():
    init_session_state()
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        if login():
            st.rerun()
    else:
        st.write(f"Bem-vindo, {st.session_state['user']['name']}!")
        if st.button("Logout"):
            logout()
            st.rerun()

if __name__ == "__main__":
    main()