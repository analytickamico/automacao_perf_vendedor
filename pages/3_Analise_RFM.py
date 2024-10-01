import streamlit as st
import pandas as pd
from datetime import date
import plotly.graph_objects as go
import traceback
from PIL import Image
import sys
import os
import logging
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from session_state_manager import init_session_state, load_page_specific_state,ensure_cod_colaborador
from utils import (
    get_channels_and_ufs,
    get_colaboradores,
    get_rfm_summary,
    get_rfm_heatmap_data,
    get_rfm_summary_cached,
    create_rfm_heatmap_from_aggregated,
    get_rfm_segment_clients,
    get_colaboradores_cached,
    get_channels_and_ufs_cached,
    load_filter_options,
    get_brand_options
)

logging.basicConfig(level=logging.INFO)

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

icon = Image.open(ico_path)

def update_filters():
    st.session_state['data_needs_update'] = True

def manage_filters():
    st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador", value=st.session_state['cod_colaborador'], on_change=update_filters)
    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", value=st.session_state['start_date'], on_change=update_filters)
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", value=st.session_state['end_date'], on_change=update_filters)

    channels, ufs, colaboradores_options = load_filter_options()

    st.session_state['selected_channels'] = st.sidebar.multiselect("Canais de Venda", options=channels, default=st.session_state['selected_channels'], on_change=update_filters)
    st.session_state['selected_ufs'] = st.sidebar.multiselect("UFs", options=ufs, default=st.session_state['selected_ufs'], on_change=update_filters)
    st.session_state['selected_colaboradores'] = st.sidebar.multiselect("Colaboradores", options=colaboradores_options, default=st.session_state['selected_colaboradores'], on_change=update_filters)

def load_filters():
    user = st.session_state.get('user', {})
    
    if user.get('role') in ['admin', 'gestor']:
        st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state.get('cod_colaborador', ''))
    elif user.get('role') == 'vendedor':
        st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")
    else:
        st.warning("Tipo de usuário não reconhecido.")
        return

    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", value=st.session_state['start_date'])
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", value=st.session_state['end_date'])

    channels, ufs = get_channels_and_ufs_cached(st.session_state['cod_colaborador'], st.session_state['start_date'], st.session_state['end_date'])
    
    st.session_state['selected_channels'] = st.sidebar.multiselect("Canais de Venda", options=channels, default=st.session_state['selected_channels'])
    st.session_state['selected_ufs'] = st.sidebar.multiselect("UFs", options=ufs, default=st.session_state['selected_ufs'])

    if st.session_state['user']['role'] in ['admin', 'gestor']:
        colaboradores = get_colaboradores_cached(st.session_state['start_date'], st.session_state['end_date'], st.session_state['selected_channels'], st.session_state['selected_ufs'])
        colaboradores_options = colaboradores['nome_colaborador'].tolist() if not colaboradores.empty else []
        st.session_state['selected_colaboradores'] = st.sidebar.multiselect("Colaboradores", options=colaboradores_options, default=st.session_state['selected_colaboradores'])
    else:
        st.session_state['selected_colaboradores'] = [st.session_state['user']['username']]

    if st.sidebar.button("Atualizar Dados"):
        st.session_state['data_needs_update'] = True

def load_data():
    logging.info("Iniciando carregamento de dados")
    if st.session_state['data_needs_update']:
        progress_text = "Operação em andamento. Aguarde..."
        my_bar = st.progress(0, text=progress_text)
        with st.spinner('Carregando dados...'):
            try:
                my_bar.progress(50, text="Carregando dados dos clientes...")
                st.session_state['rfm_summary'] = get_rfm_summary_cached(
                    st.session_state['cod_colaborador'],
                    st.session_state['start_date'],
                    st.session_state['end_date'],
                    st.session_state['selected_channels'],
                    st.session_state['selected_ufs'],
                    st.session_state['selected_colaboradores']
                )
                my_bar.progress(40, text="Carregando mapa de calor RFM...")
                st.session_state['heatmap_data'] = get_rfm_heatmap_data(
                    st.session_state['cod_colaborador'],
                    st.session_state['start_date'],
                    st.session_state['end_date'],
                    st.session_state['selected_channels'],
                    st.session_state['selected_ufs'],
                    st.session_state['selected_colaboradores']
                )
                st.session_state['data_needs_update'] = False
                my_bar.progress(100, text="Carregamento concluído!")
                time.sleep(1)
                my_bar.empty()
            except Exception as e:
                my_bar.empty()
                st.error(f"Erro ao carregar dados: {str(e)}")
                logging.error(f"Erro ao carregar dados: {str(e)}")
                logging.error(traceback.format_exc())
    logging.info("Finalizado carregamento de dados")

def create_dashboard():
    logging.info("Iniciando criação do dashboard")

    # Verificar se já carregamos os dados anteriormente
    if 'rfm_summary' not in st.session_state or 'heatmap_data' not in st.session_state:
        with st.spinner("Carregando dados..."):
            st.session_state['rfm_summary'] = get_rfm_summary_cached(
                st.session_state['cod_colaborador'],
                st.session_state['start_date'],
                st.session_state['end_date'],
                st.session_state['selected_channels'],
                st.session_state['selected_ufs'],
                st.session_state['selected_colaboradores']
            )
            st.session_state['heatmap_data'] = get_rfm_heatmap_data(
                st.session_state['cod_colaborador'],
                st.session_state['start_date'],
                st.session_state['end_date'],
                st.session_state['selected_channels'],
                st.session_state['selected_ufs'],
                st.session_state['selected_colaboradores']
            )
            # Marcar que os dados foram carregados
            st.session_state['data_loaded'] = True
    else:
        # Se os dados já foram carregados, marcar como True
        st.session_state['data_loaded'] = True

    # Após carregar os dados, verificar novamente
    if 'rfm_summary' in st.session_state and 'heatmap_data' in st.session_state:
        create_dashboard_content(
            st.session_state['rfm_summary'],
            st.session_state['heatmap_data']
        )
    else:
        st.warning("Dados não disponíveis. Por favor, verifique os filtros e tente novamente.")

def create_dashboard_content(rfm_summary, heatmap_data):
    st.title('Análise de Clientes RFM')

    if heatmap_data is not None and not heatmap_data.empty:
        st.subheader("Mapa de Calor - Clientes")
        fig_rfm = create_rfm_heatmap_from_aggregated(heatmap_data)
        st.plotly_chart(fig_rfm)
    else:
        st.warning("Não há dados para criar o mapa de calor RFM. Verifique os filtros aplicados.")

    if rfm_summary is not None and not rfm_summary.empty:
        # Calcular o Ticket Médio
        rfm_summary['Ticket_Medio'] = rfm_summary['Valor_Medio'] / rfm_summary['Positivacoes_Media']

        # Selecionar apenas as colunas desejadas
        columns_to_display = ['Segmento','Canal_Venda','Regiao','Numero_Clientes', 'Valor_Total', 'Valor_Medio', 'Recencia_Media', 'Positivacoes_Media', 'Ticket_Medio']
        rfm_summary_display = rfm_summary[columns_to_display]

        st.subheader("Segmentação dos Clientes RFM")
        st.dataframe(rfm_summary_display.style.format({
            'Numero_Clientes': '{:,.0f}',
            'Valor_Total': 'R$ {:,.2f}',
            'Valor_Medio': 'R$ {:,.2f}',
            'Recencia_Media': '{:.2f}',
            'Positivacoes_Media': '{:.2f}',
            'Ticket_Medio': 'R$ {:,.2f}'  # Formatação para o novo Ticket Médio
        }))

        segmentos_rfm = ['Todos'] + rfm_summary_display['Segmento'].unique().tolist()
        segmento_selecionado = st.radio("Selecione um segmento RFM para ver os clientes:", segmentos_rfm)

        st.subheader("Clientes por Segmento RFM")

        if segmento_selecionado != 'Todos':
            with st.spinner(f'Carregando clientes do segmento {segmento_selecionado}...'):
                clientes_segmento = get_rfm_segment_clients(
                    st.session_state['cod_colaborador'],
                    st.session_state['start_date'],
                    st.session_state['end_date'],
                    segmento_selecionado,
                    st.session_state['selected_channels'],
                    st.session_state['selected_ufs'],
                    st.session_state['selected_colaboradores']
                )

                if not clientes_segmento.empty:
                    st.write(f"Clientes do segmento: {segmento_selecionado}")

                    clientes_segmento['Monetario'] = clientes_segmento['Monetario'].apply(lambda x: f"R$ {x:,.2f}")
                    clientes_segmento['ticket_medio_posit'] = clientes_segmento['ticket_medio_posit'].apply(lambda x: f"R$ {x:,.2f}")

                    st.dataframe(clientes_segmento[['Cod_Cliente', 'Nome_Cliente', 'Canal_Venda','uf_empresa','Recencia', 'Positivacao', 'Monetario', 'ticket_medio_posit','marcas','Mes_Ultima_Compra']].set_index('Cod_Cliente'))

                    st.write(f"Total de clientes no segmento: {len(clientes_segmento)}")
                else:
                    st.warning(f"Não há clientes no segmento {segmento_selecionado} para o período e/ou filtros selecionados.")
        else:
            st.info("Selecione um segmento específico para ver os detalhes dos clientes.")
    else:
        st.warning("Não há dados de segmentos RFM disponíveis.")
    logging.info("Finalizado criação do dashboard")



def main():
    init_session_state()  # Use init_session_state em vez de initialize_session_state
    if st.session_state.get('logout_requested', False):
        st.session_state['logout_requested'] = False
        # Adiciona checagem para evitar o rerun imediato
        if st.session_state.get('logged_in') is None: 
            st.write("Você foi desconectado. Recarregue a página para continuar.")
            return
        
    st.set_page_config(page_title="Análise Clientes", page_icon=icon, layout="wide")
    load_page_specific_state("Analise_RFM")

    if not st.session_state.get('logged_in', False):
        st.warning("Por favor, faça login na página inicial para acessar esta página.")
        return

    try:
        st.sidebar.title('Configurações do Dashboard')
        
        user = st.session_state.get('user')
        if user and isinstance(user, dict) and 'role' in user:
            if user['role'] == 'vendedor':
                st.session_state['cod_colaborador'] = user.get('cod_colaborador', '')
                st.sidebar.info(f"Código do Colaborador: {st.session_state['cod_colaborador']}")
            load_filters()
        else:
            st.warning("Informações de usuário não disponíveis. Por favor, faça login novamente.")
            return

        if st.session_state.get('data_needs_update', True):
            load_data()

        create_dashboard()

    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {str(e)}")
        logging.error(f"Erro ao carregar o dashboard: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()

   