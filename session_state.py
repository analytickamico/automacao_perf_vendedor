import streamlit as st
from datetime import date

def init_session_state():
    default_values = {
        'cod_colaborador': "",
        'start_date': date(2024, 1, 1),
        'end_date': date.today(),
        'selected_channels': [],
        'selected_ufs': [],
        'selected_colaboradores': [],
        'data_needs_update': True
    }
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def update_filters():
    st.session_state['data_needs_update'] = True