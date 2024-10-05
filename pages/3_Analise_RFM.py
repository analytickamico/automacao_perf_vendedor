import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import traceback
import logging
import time
from session_state_manager import init_session_state, load_page_specific_state, ensure_cod_colaborador
from utils import (
    get_channels_and_ufs_cached,
    get_colaboradores_cached,
    get_rfm_summary_cached,
    get_rfm_heatmap_data,
    create_rfm_heatmap_from_aggregated,
    get_rfm_segment_clients,
    get_brand_options,
    get_team_options
)
import os

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

def load_filters():
    user = st.session_state.get('user', {})
    
    if user.get('role') in ['admin', 'gestor']:
        st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state.get('cod_colaborador', ''))
    elif user.get('role') == 'vendedor':
        st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")

    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", st.session_state.get('start_date'))
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", st.session_state.get('end_date'))

    channels, ufs = get_channels_and_ufs_cached(st.session_state.get('cod_colaborador', ''), st.session_state['start_date'], st.session_state['end_date'])
    st.session_state['selected_channels'] = st.sidebar.multiselect("Canais de Venda", options=channels, default=st.session_state.get('selected_channels', []))
    st.session_state['selected_ufs'] = st.sidebar.multiselect("UFs", options=ufs, default=st.session_state.get('selected_ufs', []))

    if user.get('role') in ['admin', 'gestor']:
        team_options = get_team_options(st.session_state['start_date'], st.session_state['end_date'])
        st.session_state['selected_teams'] = st.sidebar.multiselect("Equipes", options=team_options, default=st.session_state.get('selected_teams', []))

    brand_options = get_brand_options(st.session_state['start_date'], st.session_state['end_date'])
    st.session_state['selected_brands'] = st.sidebar.multiselect("Marcas", options=brand_options, default=st.session_state.get('selected_brands', []))

    if user.get('role') in ['admin', 'gestor']:
        colaboradores = get_colaboradores_cached(st.session_state['start_date'], st.session_state['end_date'], st.session_state['selected_channels'], st.session_state['selected_ufs'])
        colaboradores_options = colaboradores['nome_colaborador'].tolist() if not colaboradores.empty else []
        st.session_state['selected_colaboradores'] = st.sidebar.multiselect("Colaboradores", options=colaboradores_options, default=st.session_state.get('selected_colaboradores', []))

    if st.sidebar.button("Atualizar Dados"):
        st.session_state['data_needs_update'] = True

def load_data():
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
                my_bar.progress(80, text="Carregando mapa de calor RFM...")
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

def create_dashboard():
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

        #segmentos_rfm = ['Todos'] + rfm_summary_display['Segmento'].unique().tolist()
        #segmento_selecionado = st.radio("Selecione um segmento RFM para ver os clientes:", segmentos_rfm)

        st.subheader("Clientes por Segmento RFM")
        segmentos = ['Todos', 'Campeões', 'Clientes fiéis', 'Novos clientes', 'Perdidos', 'Atenção', 'Em risco', 'Potencial', 'Acompanhar']
        segmentos_selecionados = st.multiselect("Selecione os segmentos", options=segmentos, default=['Atenção','Em risco'])

        apenas_inadimplentes = st.checkbox("Mostrar apenas clientes inadimplentes")

        # Verificar se houve mudança nos segmentos selecionados
        if 'last_segmentos' not in st.session_state or st.session_state['last_segmentos'] != segmentos_selecionados:
            st.session_state['data_needs_update'] = True
            st.session_state['last_segmentos'] = segmentos_selecionados

        if st.session_state.get('data_needs_update', True):
            with st.spinner('Carregando clientes dos segmentos selecionados...'):
                clientes_segmento = get_rfm_segment_clients(
                    st.session_state['cod_colaborador'],
                    st.session_state['start_date'],
                    st.session_state['end_date'],
                    segmentos_selecionados,
                    st.session_state['selected_channels'],
                    st.session_state['selected_ufs'],
                    st.session_state['selected_colaboradores']
                )
                st.session_state['clientes_segmento'] = clientes_segmento
                st.session_state['data_needs_update'] = False
        else:
            clientes_segmento = st.session_state['clientes_segmento']

        if clientes_segmento is not None and not clientes_segmento.empty:
            # Aplicar o filtro de inadimplentes, se necessário
            if apenas_inadimplentes:
                clientes_filtrados = clientes_segmento[clientes_segmento['status_inadimplente'] == 'Inadimplente']
            else:
                clientes_filtrados = clientes_segmento

            if not clientes_filtrados.empty:
                st.write(f"Clientes dos segmentos: {', '.join(segmentos_selecionados)}")
                if apenas_inadimplentes:
                    st.write("(Apenas clientes inadimplentes)")

                # Função auxiliar para formatar valores monetários
                def format_currency(value):
                    if pd.isna(value):
                        return "-"
                    elif isinstance(value, str):
                        return value
                    else:
                        return f"R$ {value:,.2f}"

                # Formatação das colunas monetárias
                for col in ['Monetario', 'ticket_medio_posit', 'vlr_inadimplente']:
                    clientes_filtrados[col] = clientes_filtrados[col].apply(format_currency)

                # Exibição do DataFrame
                st.dataframe(clientes_filtrados[['Cod_Cliente', 'Nome_Cliente', 'Canal_Venda', 'uf_empresa', 'Recencia', 
                                                'Positivacao', 'Monetario', 'ticket_medio_posit', 'marcas', 'Mes_Ultima_Compra',
                                                'qtd_titulos', 'vlr_inadimplente', 'status_inadimplente']].set_index('Cod_Cliente'))

                st.write(f"Total de clientes exibidos: {len(clientes_filtrados)}")
            else:
                st.warning("Não há clientes que atendam aos critérios selecionados.")
        else:
            st.warning("Não há clientes nos segmentos selecionados para o período e/ou filtros selecionados.")

        logging.info("Finalizado criação do dashboard")



def main():
    init_session_state()
    load_page_specific_state("Analise_RFM")

    if not st.session_state.get('logged_in', False):
        st.warning("Por favor, faça login na página inicial para acessar esta página.")
        return

    st.set_page_config(page_title="Análise Clientes", layout="wide",page_icon=ico_path)

    try:
        st.sidebar.title('Configurações do Dashboard')
        load_filters()

        if st.session_state.get('data_needs_update', True):
            load_data()

        create_dashboard()

    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {str(e)}")
        logging.error(f"Erro ao carregar o dashboard: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()