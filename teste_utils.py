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

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT")

# Seleciona o URI de redirecionamento apropriado
if ENVIRONMENT == "development":
    OAUTH_REDIRECT_URI = os.getenv("DEV_REDIRECT_URI")
else:
    OAUTH_REDIRECT_URI = os.getenv("PROD_REDIRECT_URI")




print(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID')}")
print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
print(f"DEV_REDIRECT_URI: {os.getenv('DEV_REDIRECT_URI')}")
print(f"PROD_REDIRECT_URI: {os.getenv('PROD_REDIRECT_URI')}")
print(OAUTH_REDIRECT_URI)






