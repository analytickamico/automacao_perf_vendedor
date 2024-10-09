import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import traceback
import logging
import time
from session_state_manager import init_session_state, load_page_specific_state, ensure_cod_colaborador
from utils import (
    get_rfm_summary_cached,
    get_rfm_heatmap_data,
    create_rfm_heatmap_from_aggregated,
    get_rfm_segment_clients,
    get_static_data
)
import os

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")


def initialize_session_state():
    if 'filter_options' not in st.session_state:
        st.session_state.filter_options = {
            'channels': [],
            'ufs': [],
            'brands': [],
            'equipes': [],
            'colaboradores': []
        }
    if 'selected_channels' not in st.session_state:
        st.session_state.selected_channels = []
    if 'selected_ufs' not in st.session_state:
        st.session_state.selected_ufs = []
    if 'selected_brands' not in st.session_state:
        st.session_state.selected_brands = []
    if 'selected_teams' not in st.session_state:
        st.session_state.selected_teams = []
    if 'selected_colaboradores' not in st.session_state:
        st.session_state.selected_colaboradores = []    

def load_filters():
    logging.info("Iniciando load_filters")
    initialize_session_state()

    user = st.session_state.get('user', {})
    logging.info(f"Papel do usuário: {user.get('role')}")
    
    static_data = get_static_data()
    logging.info(f"Dados estáticos obtidos: {static_data.keys()}")
    
    st.session_state.filter_options['channels'] = static_data.get('canais_venda', [])
    st.session_state.filter_options['ufs'] = static_data.get('ufs', [])
    st.session_state.filter_options['brands'] = static_data.get('marcas', [])
    st.session_state.filter_options['equipes'] = static_data.get('equipes', [])
    st.session_state.filter_options['colaboradores'] = static_data.get('colaboradores', [])

    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", st.session_state.get('start_date'))
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", st.session_state.get('end_date'))
    
    st.session_state.selected_channels = st.sidebar.multiselect(
        "Canais de Venda", 
        options=st.session_state.filter_options['channels'],
        default=st.session_state.get('selected_channels', [])
    )
    
    st.session_state.selected_ufs = st.sidebar.multiselect(
        "UFs", 
        options=st.session_state.filter_options['ufs'],
        default=st.session_state.get('selected_ufs', [])
    )
    
    st.session_state.selected_brands = st.sidebar.multiselect(
        "Marcas", 
        options=st.session_state.filter_options['brands'],
        default=st.session_state.get('selected_brands', [])
    )

    if user.get('role') in ['admin', 'gestor']:
        st.session_state.selected_teams = st.sidebar.multiselect(
            "Equipes", 
            options=st.session_state.filter_options['equipes'],
            default=st.session_state.get('selected_teams', [])
        )
        
        st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state.get('cod_colaborador', ''))
        
        st.session_state.selected_colaboradores = st.sidebar.multiselect(
            "Colaboradores", 
            options=st.session_state.filter_options['colaboradores'],
            default=st.session_state.get('selected_colaboradores', [])
        )
    elif user.get('role') == 'vendedor':
        st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")

    if st.sidebar.button("Atualizar Dados"):
        load_data()
        st.rerun()

def load_data():
    progress_text = "Operação em andamento. Aguarde..."
    my_bar = st.progress(0, text=progress_text)
    with st.spinner('Carregando dados...'):
        try:
            my_bar.progress(50, text="Carregando dados dos clientes...")
            st.session_state['rfm_summary'] = get_rfm_summary_cached(
                st.session_state['cod_colaborador'],
                st.session_state['start_date'],
                st.session_state['end_date'],
                st.session_state.selected_channels,
                st.session_state.selected_ufs,
                st.session_state.selected_colaboradores,
                st.session_state.selected_teams
            )
            my_bar.progress(80, text="Carregando mapa de calor RFM...")
            st.session_state['heatmap_data'] = get_rfm_heatmap_data(
                st.session_state['cod_colaborador'],
                st.session_state['start_date'],
                st.session_state['end_date'],
                st.session_state.selected_channels,
                st.session_state.selected_ufs,
                st.session_state.selected_colaboradores,
                st.session_state.selected_teams
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

        st.session_state['last_segmentos'] = []

def create_dashboard():
    if 'rfm_summary' in st.session_state and 'heatmap_data' in st.session_state:
        create_dashboard_content(
            st.session_state['rfm_summary'],
            st.session_state['heatmap_data']
        )
    else:
        st.warning("Nenhum dado carregado. Por favor, escolha os filtros e acione Atualizar Dados.")          

def create_dashboard():
    if 'rfm_summary' in st.session_state and 'heatmap_data' in st.session_state:
        create_dashboard_content(
            st.session_state['rfm_summary'],
            st.session_state['heatmap_data']
        )
    else:
        st.warning("Nenhum dado carregado. Por favor, escolha os filtros e acione Atualizar Dados.")

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
        rfm_summary_display = rfm_summary[columns_to_display].set_index('Segmento')

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
        # Texto explicativo
        with st.expander("Clique aqui para ver como interpretar o gráfico"):
             st.markdown("""
### Cálculo dos Scores RFM:

Recência (R_Score): Baseado em quão recentemente o cliente fez uma compra.

    5 pontos: 0-1 meses atrás
    4 pontos: 2 meses atrás
    3 pontos: 3 meses atrás
    2 pontos: 4-6 meses atrás
    1 ponto: 7 ou mais meses atrás

Frequência (F_Score): Baseado no número de compras (Positivação).

    5 pontos: 10 ou mais compras
    4 pontos: 7-9 compras
    3 pontos: 3-6 compras
    2 pontos: 2 compras
    1 ponto: 1 compra

Monetário (M_Score): Divide os clientes em 5 grupos iguais baseado no valor total gasto, com 5 sendo o grupo que mais gasta e 1 o que menos gasta.

Segmentação dos Clientes:

    . "Campeões" --> são clientes que compraram nos últimos 1-2 meses, fazem compras frequentes e gastam muito. Esses são realmente os melhores clientes atuais.

    . "Clientes fiéis" --> compraram nos últimos 4 meses ou menos e fazem compras frequentes. Eles são consistentes, mas podem não ser tão recentes quanto os "Campeões".

    . "Novos clientes" --> compraram muito recentemente (último mês), mas com baixa recompra.
                                
    . "Perdidos" --> não compram há pelo menos 7 meses, é um cliente como potencialmente perdido (churn).

    . "Atenção" e "Em risco" --> são clientes que não compram há alguns meses e têm frequência baixa (1 positivação) ou média-baixa (2 a 6 positivações). Esses grupos podem precisar de estratégias de reativação.

    . "Potencial" --> são clientes que compraram nos últimos 3 meses ou mais recentemente, com boa frequência e valor médio-alto de compras. Eles podem ser alvos para estratégias de upselling.
                """)

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
                    st.session_state['selected_colaboradores'],
                    st.session_state['selected_teams']
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

    st.set_page_config(page_title="Análise Clientes", layout="wide", page_icon=ico_path)

    try:
        st.sidebar.title('Configurações do Dashboard')
        load_filters()
        create_dashboard()
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {str(e)}")
        logging.error(f"Erro ao carregar o dashboard: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()

