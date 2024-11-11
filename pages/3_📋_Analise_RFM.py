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
    get_static_data,
    get_recency_clients
)
import os

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

#def format_currency_br(value):
    #return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_currency_br(value):
    """
    Formata valor monetário com tratamento robusto para valores nulos
    """
    try:
        if pd.isna(value) or value is None:
            return "R$ 0,00"
        
        # Converter string para float se necessário
        if isinstance(value, str):
            value = value.replace('R$', '').replace('.', '').replace(',', '.').strip()
            value = float(value) if value else 0
            
        value = float(value)
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def format_numeric(value, decimal_places=0):
    """
    Formata valor numérico com tratamento robusto para valores nulos
    """
    try:
        if pd.isna(value) or value is None:
            return "0"
            
        # Converter para float e depois para o formato desejado
        value = float(value)
        if decimal_places == 0:
            return f"{int(value):,}".replace(",", ".")
        else:
            return f"{value:,.{decimal_places}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0"

def convert_to_number(value):
    """Converte valores para número, tratando tanto strings quanto números"""
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        # Se for string, remove R$, pontos e troca vírgula por ponto
        return float(value.replace('R$ ', '').replace('.', '').replace(',', '.'))
    # Se já for número, retorna o próprio valor
    return float(value)

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

    #user = st.session_state.get('user', {})
    user = st.session_state['user']
    user_role = user.get('role')
    logging.info(f"Papel do usuário: {user_role}")

    
    static_data = get_static_data()
    logging.info(f"Dados estáticos obtidos: {static_data.keys()}")
    
    st.session_state.filter_options['channels'] = static_data.get('canais_venda', [])
    st.session_state.filter_options['ufs'] = static_data.get('ufs', [])
    st.session_state.filter_options['brands'] = static_data.get('marcas', [])
    st.session_state.filter_options['equipes'] = static_data.get('equipes', [])
    st.session_state.filter_options['colaboradores'] = static_data.get('colaboradores', [])

    #st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", st.session_state.get('start_date'))
    #st.session_state['end_date'] = st.sidebar.date_input("Data Final", st.session_state.get('end_date'))
    
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
    
    all_brands_selected = st.sidebar.checkbox("Selecionar Todas as Marcas", value=False)

    with st.sidebar.expander("Selecionar/Excluir Marcas Específicas", expanded=False):
        if all_brands_selected:
            default_brands = st.session_state.filter_options['brands']
        else:
            default_brands = st.session_state.get('selected_brands', [])

        # Multiselect para marcas com opção de exclusão
        selected_brands = st.multiselect(
            "Marcas (desmarque para excluir)",
            options=st.session_state.filter_options['brands'],
            default=default_brands
        )

    # Atualizar as marcas selecionadas
    if all_brands_selected:
        st.session_state.selected_brands = [brand for brand in selected_brands if brand is not None]
        excluded_brands = [brand for brand in st.session_state.filter_options['brands'] if brand not in selected_brands and brand is not None]
    else:
        st.session_state.selected_brands = [brand for brand in selected_brands if brand is not None]
        excluded_brands = []

    # Exibir marcas selecionadas ou excluídas
    if all_brands_selected:
        if excluded_brands:
            st.sidebar.write(f"Marcas excluídas: {', '.join(excluded_brands)}")
        else:
            st.sidebar.write("Todas as marcas estão selecionadas")

    logging.info(f"Papel do usuário: {user_role}")
    if user_role in ['admin', 'gestor']:
        logging.info("Usuário é admin ou gestor, exibindo filtro de equipes")
        equipes_options = st.session_state.filter_options['equipes']
        if equipes_options:
            st.session_state.selected_teams = st.sidebar.multiselect(
                "Equipes", 
                options=equipes_options,
                default=st.session_state.get('selected_teams', [])
            )
            logging.info(f"Equipes selecionadas: {st.session_state.selected_teams}")
        else:
            logging.warning("Nenhuma opção de equipe disponível para exibição")
        
        st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state.get('cod_colaborador', ''))
        
        st.session_state.selected_colaboradores = st.sidebar.multiselect(
            "Colaboradores", 
            options=st.session_state.filter_options['colaboradores'],
            default=st.session_state.get('selected_colaboradores', [])
        )
    elif user_role == 'vendedor':
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
        rfm_summary['Ticket_Medio'] = rfm_summary['Valor_Medio'] / rfm_summary['Positivacoes_Media']
    

        # Selecionar apenas as colunas desejadas
        columns_to_display = ['Segmento','Canal_Venda','Regiao','Numero_Clientes', 'Valor_Total', 'Valor_Medio', 'Recencia_Media', 'Positivacoes_Media', 'Ticket_Medio']
        rfm_summary_display = rfm_summary[columns_to_display].set_index('Segmento')

        st.subheader("Segmentação dos Clientes RFM")
        st.dataframe(rfm_summary_display.style.format({
            'Numero_Clientes': '{:,.0f}',  # Formatação padrão para número inteiro
            'Valor_Total': format_currency_br,  # Usa a função formatadora
            'Valor_Medio': format_currency_br,  # Usa a função formatadora
            'Recencia_Media': '{:.2f}',  # Formatação padrão para número com duas casas decimais
            'Positivacoes_Media': '{:.2f}',  # Formatação padrão para número com duas casas decimais
            'Ticket_Medio': format_currency_br  # Usa a função formatadora
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
    # Seleção do tipo de filtro
    filtro_tipo = st.radio(
        "Selecione o tipo de filtro:",
        ["Por Segmento", "Por Recência"],
        horizontal=True
    )

    # Inicializar variáveis
    modo_selecao = None
    selecao = None
    recencias_selecionadas = []  # Inicializar aqui

    if filtro_tipo == "Por Segmento":
        segmentos = ['Todos', 'Campeões', 'Clientes fiéis', 'Novos clientes', 'Perdidos', 'Atenção', 'Em risco', 'Potencial', 'Acompanhar']
        segmentos_selecionados = st.multiselect("Selecione os segmentos", options=segmentos, default=['Atenção','Em risco'])
        modo_selecao = "segmento"
        selecao = segmentos_selecionados
    else:  # Por Recência
        recencias = [0, 1, 2, 3, 4, 5, 6, 'Maior que 6']
        recencias_selecionadas = st.multiselect(
            "Selecione os meses de recência",
            options=recencias,
            default=[3,4,5],
            help="0 = Mês atual, 1 = Mês anterior, etc."
        )
        modo_selecao = "recencia"
        selecao = recencias_selecionadas

    apenas_inadimplentes = st.checkbox("Mostrar apenas clientes inadimplentes")

        # Verifica se houve mudança na seleção
    if ('last_selecao' not in st.session_state or 
            st.session_state.get('last_selecao') != selecao or 
            st.session_state.get('last_modo') != modo_selecao):
        
        st.session_state['data_needs_update'] = True
        st.session_state['last_selecao'] = selecao
        st.session_state['last_modo'] = modo_selecao

    # Carrega os dados se necessário
    if st.session_state.get('data_needs_update', True):
        with st.spinner('Carregando clientes...'):
            try:
                if modo_selecao == "segmento":
                    clientes = get_rfm_segment_clients(
                        st.session_state['cod_colaborador'],
                        st.session_state['start_date'],
                        st.session_state['end_date'],
                        selecao,
                        st.session_state['selected_channels'],
                        st.session_state['selected_ufs'],
                        st.session_state['selected_colaboradores'],
                        st.session_state['selected_teams']
                    )
                else:  # modo_selecao == "recencia"
                    clientes = get_recency_clients(
                        st.session_state['cod_colaborador'],
                        st.session_state['start_date'],
                        st.session_state['end_date'],
                        selecao,
                        st.session_state['selected_channels'],
                        st.session_state['selected_ufs'],
                        st.session_state['selected_colaboradores'],
                        st.session_state['selected_teams']
                    )
                st.session_state['clientes_filtrados'] = clientes
                st.session_state['data_needs_update'] = False
            except Exception as e:
                logging.error(f"Erro ao carregar clientes: {str(e)}")
                st.error("Erro ao carregar dados dos clientes")
                return
    else:
        clientes = st.session_state.get('clientes_filtrados')

    # Processar e exibir os dados (movido para fora do else)
    if clientes is not None and not clientes.empty:
        # Aplicar o filtro de inadimplentes, se necessário
        if apenas_inadimplentes:
            clientes_filtrados = clientes[clientes['status_inadimplente'] == 'Inadimplente']
        else:
            clientes_filtrados = clientes

        if not clientes_filtrados.empty:
            # Garantir que não há valores None antes da formatação
            for col in ['Recencia', 'Positivacao', 'qtd_titulos']:
                clientes_filtrados[col] = pd.to_numeric(clientes_filtrados[col], errors='coerce').fillna(0)

            for col in ['Monetario', 'ticket_medio_posit', 'vlr_inadimplente']:
                clientes_filtrados[col] = clientes_filtrados[col].apply(lambda x: convert_to_number(x) if x is not None else 0)

            # Configurar o DataFrame
            formatted_df = clientes_filtrados[[
                'Cod_Cliente', 'Nome_Cliente', 'Vendedor', 'Canal_Venda', 
                'uf_empresa', 'Recencia', 'Positivacao', 'Monetario', 
                'ticket_medio_posit', 'marcas', 'Mes_Ultima_Compra',
                'qtd_titulos', 'vlr_inadimplente', 'status_inadimplente'
            ]].copy()

            # Aplicar formatação com funções mais robustas
            try:
                styled_df = formatted_df.style.format({
                    'Monetario': lambda x: format_currency_br(x),
                    'ticket_medio_posit': lambda x: format_currency_br(x),
                    'vlr_inadimplente': lambda x: format_currency_br(x),
                    'Recencia': lambda x: format_numeric(x),
                    'Positivacao': lambda x: format_numeric(x),
                    'qtd_titulos': lambda x: format_numeric(x)
                })

                # Exibir o DataFrame
                st.dataframe(
                    styled_df,
                    use_container_width=True
                )
                
            except Exception as e:
                logging.error(f"Erro na formatação do DataFrame: {str(e)}")
                # Fallback para exibição sem formatação
                st.write("Exibindo dados sem formatação devido a erro:")
                st.dataframe(formatted_df)

            st.write(f"Total de clientes exibidos: {len(clientes_filtrados)}")
        else:
            st.warning("Não há clientes que atendam aos critérios selecionados.")
    else:
        st.warning("Não há clientes para os filtros selecionados.")



def main():
    init_session_state()
    load_page_specific_state("Analise_RFM")

    if not st.session_state.get('logged_in', False):
        st.warning("Por favor, faça login na página inicial para acessar esta página.")
        return

    st.set_page_config(page_title="Análise Clientes", layout="wide", page_icon=ico_path)

    try:
        st.sidebar.title('Filtros')
        load_filters()
        create_dashboard()
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {str(e)}")
        logging.error(f"Erro ao carregar o dashboard: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()

