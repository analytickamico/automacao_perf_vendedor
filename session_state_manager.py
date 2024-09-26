import streamlit as st
from datetime import date

def init_session_state():
    if 'initialized' not in st.session_state:
        st.session_state['initialized'] = True
        reset_session_state()

def reset_session_state():
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

def load_page_specific_state(page_name):
    if st.session_state.get('current_page') != page_name:
        reset_session_state()
        st.session_state['current_page'] = page_name
        st.session_state['show_additional_info'] = False  # Reinicializa esta variável