import streamlit as st
from datetime import date

def init_session_state():
    """Inicializa ou reinicializa o estado da sessão com valores padrão."""
    default_values = {
        'initialized': True,
        'df': None,
        'brand_data': None,
        'client_status_data': None,
        'rfm_summary': None,
        'heatmap_data': None,
        'data_needs_update': True,
        'selected_brands': [],
        'cod_colaborador': '',
        'start_date': date(2024, 1, 1),
        'end_date': date.today(),
        'selected_channels': [],
        'selected_ufs': [],
        'selected_colaboradores': []
    }
    
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def update_filters():
    """Marca os dados para atualização quando os filtros são alterados."""
    st.session_state['data_needs_update'] = True

def reset_data():
    """Reseta os dados armazenados no estado da sessão."""
    st.session_state['df'] = None
    st.session_state['brand_data'] = None
    st.session_state['client_status_data'] = None
    st.session_state['rfm_summary'] = None
    st.session_state['heatmap_data'] = None
    st.session_state['data_needs_update'] = True