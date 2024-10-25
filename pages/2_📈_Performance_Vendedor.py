import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from PIL import Image
import sys
import os
import logging
from datetime import datetime
import locale
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Adicione esta linha para limpar o cache
#st.cache_data.clear()


from session_state_manager import init_session_state, load_page_specific_state, ensure_cod_colaborador
from utils import (
    get_monthly_revenue, get_brand_data, get_channels_and_ufs,
    get_colaboradores, get_client_status, create_client_status_chart,
    get_unique_customers_period, get_static_data
    )

logging.basicConfig(level=logging.INFO)

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

# Configurar o locale para português do Brasil
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    locale.setlocale(locale.LC_ALL, '')  # Fallback para o locale padrão do sistema

def format_brazilian(value, is_currency=False, decimal_places=2):
    """
    Formata um número para o padrão brasileiro corretamente.
    """
    if isinstance(value, str):
        try:
            value = value #Decimal(value.replace(',', '.'))
        except:
            return value  # Retorna o valor original se não puder ser convertido

    try:
        value = Decimal(value)
        integer_part, decimal_part = f"{value:.{decimal_places}f}".split('.')
        
        # Formata a parte inteira com pontos como separadores de milhar
        formatted_integer = ""
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                formatted_integer = '.' + formatted_integer
            formatted_integer = digit + formatted_integer
        
        # Junta as partes com vírgula como separador decimal
        result = f"{formatted_integer},{decimal_part}"
        
        if is_currency:
            return f"R$ {result}"
        else:
            return result
    except:
        return str(value) 

@st.cache_data(ttl=3600)
@st.cache_data(ttl=3600)
@st.cache_data(ttl=3600)
def process_data_by_granularity(df, granularity):
    """
    Processa os dados de acordo com a granularidade temporal selecionada
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    try:
        df = df.copy()
        
        # Garantir que as datas estão no formato correto
        df['data_ref'] = pd.to_datetime(df['data_ref'])
        df['mes_ref'] = pd.to_datetime(df['mes_ref'])
        
        if granularity == 'Mensal':
            result = df.groupby('mes_ref').agg({
                'faturamento_liquido': 'sum',
                'positivacao': 'sum',
                'desconto': 'sum',
                'faturamento_bruto': 'sum',
                'valor_bonificacao': 'sum',
                'valor_devolucao': 'sum',
                'qtd_pedido': 'sum',
                'custo_total': 'sum'
            }).reset_index()
            
            result['periodo_desc'] = result['mes_ref'].dt.strftime('%m-%Y')
            
            return result.sort_values('mes_ref').fillna(0)
        
        elif granularity == 'Semanal':
            # Usar data_ref (data original) para criar as semanas
            df['semana'] = df['data_ref'].dt.to_period('W')
            df['semana_inicio'] = df['semana'].apply(lambda x: x.start_time)
            df['semana_fim'] = df['semana'].apply(lambda x: x.end_time)
            
            # Agrupar por semana
            weekly_data = df.groupby(['semana', 'semana_inicio', 'semana_fim']).agg({
                'faturamento_liquido': 'sum',
                'positivacao': 'sum',  # ou 'nunique' se precisar contar clientes únicos
                'desconto': 'sum',
                'faturamento_bruto': 'sum',
                'valor_bonificacao': 'sum',
                'valor_devolucao': 'sum',
                'qtd_pedido': 'sum',
                'custo_total': 'sum'
            }).reset_index()
            
            # Criar descrição do período
            weekly_data['periodo_desc'] = weekly_data.apply(
                lambda x: f"{x['semana_inicio'].strftime('%d/%m')} a {x['semana_fim'].strftime('%d/%m')}",
                axis=1
            )
            
            # Ordenar por data
            result = weekly_data.sort_values('semana_inicio')
            
            # Remover colunas auxiliares
            result = result.drop(['semana', 'semana_inicio', 'semana_fim'], axis=1)
            
            return result.fillna(0)
        
        return pd.DataFrame()
        
    except Exception as e:
        logging.error(f"Erro no processamento dos dados: {str(e)}", exc_info=True)
        st.error(f"Erro ao processar dados: {str(e)}")
        return pd.DataFrame()
    
@st.cache_data(ttl=3600)
def get_monthly_revenue_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams):
    channel_filter = f"AND pedidos.canal_venda IN ('{', '.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{', '.join(selected_ufs)}')" if selected_ufs else ""
    brand_filter = f"AND item_pedidos.marca IN ('{', '.join(selected_brands)}')" if selected_brands else ""
    return get_monthly_revenue(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams)

@st.cache_data(ttl=3600, max_entries=100)
def get_brand_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador,selected_teams):
    return get_brand_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador,selected_teams)

@st.cache_data(ttl=3600)
def get_channels_and_ufs_cached(cod_colaborador, start_date, end_date):
    return get_channels_and_ufs(cod_colaborador, start_date, end_date)

@st.cache_data(ttl=3600)
def get_colaboradores_cached(start_date, end_date, selected_channels, selected_ufs):
    return get_colaboradores(start_date, end_date, selected_channels, selected_ufs)
    
if 'filtros' not in st.session_state:
    st.session_state.filtros = {
        'channels': [],
        'ufs': [],
        'brands': [],
        'colaboradores': [],
        'teams': []
    }

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

def apply_filters(df):
    if df is None or df.empty:
        return df

    filters = {
        'marca': st.session_state.get('selected_brands'),
        'canal_venda': st.session_state.get('selected_channels'),
        'uf': st.session_state.get('selected_ufs'),
        'cod_colaborador': st.session_state.get('cod_colaborador'),
        'nome_colaborador': st.session_state.get('selected_colaboradores')
    }

    for column, filter_values in filters.items():
        if column in df.columns and filter_values:
            if isinstance(filter_values, list):
                df = df[df[column].isin(filter_values)]
            elif column == 'cod_colaborador' and st.session_state['user']['role'] == 'vendedor':
                df = df[df[column] == filter_values]
            elif filter_values:
                df = df[df[column] == filter_values]

    return df

def load_filters():
    logging.info("Iniciando load_filters")
    initialize_session_state()

    #user = st.session_state.get('user', {})
    user = st.session_state['user']
    user_role = user.get('role')
    logging.info(f"Papel do usuário: {user_role}")
    
    static_data = get_static_data()
    logging.info(f"Dados estáticos obtidos: {static_data.keys()}")
    
    st.session_state.filter_options['equipes'] = static_data.get('equipes', [])
    st.session_state.filter_options['colaboradores'] = static_data.get('colaboradores', [])
    logging.info(f"Equipes carregadas: {len(st.session_state.filter_options['equipes'])}")
    logging.info(f"Colaboradores carregados: {len(st.session_state.filter_options['colaboradores'])}")
    
    # Atualizar filter_options com os dados estáticos
    st.session_state.filter_options['channels'] = static_data.get('canais_venda', [])
    st.session_state.filter_options['ufs'] = static_data.get('ufs', [])
    st.session_state.filter_options['brands'] = static_data.get('marcas', [])
    st.session_state.filter_options['equipes'] = static_data.get('equipes', [])

    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", st.session_state.get('start_date'))
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", st.session_state.get('end_date'))
    
    # Usar dados estáticos para canais de venda
    st.session_state.selected_channels = st.sidebar.multiselect(
        "Canais de Venda", 
        options=st.session_state.filter_options['channels'],
        default=st.session_state.get('selected_channels', [])
    )
    
    # Usar dados estáticos para UFs
    st.session_state.selected_ufs = st.sidebar.multiselect(
        "UFs", 
        options=st.session_state.filter_options['ufs'],
        default=st.session_state.get('selected_ufs', [])
    )
    
    # Usar dados estáticos para marcas
    #st.session_state.selected_brands = st.sidebar.multiselect(
        #"Marcas", 
        #options=st.session_state.filter_options['brands'],
        #default=st.session_state.get('selected_brands', [])
    #)
    # Opção para selecionar todas as marcas
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
        
        # Filtro de colaboradores
        logging.info("Exibindo filtro de colaboradores")
        colaboradores_options = st.session_state.filter_options['colaboradores']
        if colaboradores_options:
            st.session_state.selected_colaboradores = st.sidebar.multiselect(
                "Colaboradores", 
                options=colaboradores_options,
                default=st.session_state.get('selected_colaboradores', [])
            )
            logging.info(f"Colaboradores selecionados: {st.session_state.selected_colaboradores}")
        else:
            logging.warning("Nenhuma opção de colaborador disponível para exibição")
    else:
        logging.info("Usuário não é admin ou gestor, filtros de equipes e colaboradores não serão exibidos")


      
    if user_role not in ['admin', 'gestor']:
        st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state.get('cod_colaborador', ''))
    elif user_role == 'vendedor':
        st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")

    
    # Carregar opções de filtro apenas se necessário
    if 'filter_options' not in st.session_state:
        #channels, ufs = get_channels_and_ufs_cached(st.session_state.get('cod_colaborador', ''), st.session_state['start_date'], st.session_state['end_date'])
        #brand_options = get_brand_options(st.session_state['start_date'], st.session_state['end_date'])
        #team_options = get_team_options()
        colaboradores = get_colaboradores_cached(st.session_state['start_date'], st.session_state['end_date'], None, None)
        colaboradores_options = colaboradores['nome_colaborador'].tolist() if not colaboradores.empty else []
        
        st.session_state['filter_options'] = {
            #'channels': channels,
            #'ufs': ufs,
            #'brands': brand_options,
            #'teams': team_options,
            'colaboradores': colaboradores_options
        }

    if st.sidebar.button("Atualizar Dados"):
        load_data()
        st.rerun()  # Isso fará com que a página seja recarregada com os novos dados

def load_data():
    progress_text = "Operação em andamento. Aguarde..."
    my_bar = st.progress(0, text=progress_text)

    try:
        logging.info("Iniciando carregamento de dados")

        my_bar.progress(10, text="Carregando dados de receita mensal...")
        st.session_state['df'] = get_monthly_revenue_cached(
            cod_colaborador=st.session_state['cod_colaborador'],
            start_date=st.session_state['start_date'],
            end_date=st.session_state['end_date'],
            selected_channels=st.session_state['selected_channels'],
            selected_ufs=st.session_state['selected_ufs'],
            selected_brands=st.session_state['selected_brands'],
            selected_nome_colaborador=st.session_state['selected_colaboradores'],
            selected_teams=st.session_state['selected_teams']
        )
        logging.info("Dados de receita mensal carregados com sucesso")

        my_bar.progress(40, text="Carregando dados de marca...")
        st.session_state['brand_data'] = get_brand_data_cached(
            cod_colaborador=st.session_state['cod_colaborador'],
            start_date=st.session_state['start_date'],
            end_date=st.session_state['end_date'],
            selected_channels=st.session_state['selected_channels'],
            selected_ufs=st.session_state['selected_ufs'],
            selected_nome_colaborador=st.session_state['selected_colaboradores'],
            selected_teams=st.session_state['selected_teams']
        )
        logging.info("Dados de marca carregados com sucesso")
        
        my_bar.progress(70, text="Carregando dados de status do cliente...")
        st.session_state['client_status_data'] = get_client_status(
            start_date=st.session_state['start_date'],
            end_date=st.session_state['end_date'],
            cod_colaborador=st.session_state['cod_colaborador'],
            selected_channels=st.session_state['selected_channels'],
            selected_ufs=st.session_state['selected_ufs'],
            selected_nome_colaborador=st.session_state['selected_colaboradores'],
            selected_brands=st.session_state['selected_brands'],
            selected_teams=st.session_state['selected_teams']
        )
        logging.info("Dados de status do cliente carregados com sucesso")

        my_bar.progress(100, text="Carregamento concluído!")
        time.sleep(1)
        my_bar.empty()
        logging.info("Carregamento de dados concluído com sucesso")

    except Exception as e:
        my_bar.empty()
        error_msg = f"Erro ao carregar dados: {str(e)}"
        st.error(error_msg)
        logging.error(error_msg, exc_info=True)
    finally:
        # Garantir que todas as chaves esperadas existam, mesmo em caso de erro
        for key in ['df', 'brand_data', 'client_status_data']:
            if key not in st.session_state:
                st.session_state[key] = None

def create_metric_html(label, value, info_text=None, info_color="green", line_break=False, is_currency=False):
    formatted_value = format_currency(value) if is_currency else value
    line_break_html = "<br>" if line_break else ""
    html = f"""
    <div class="metric-container {'metric-container-large' if line_break else ''}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{formatted_value}{line_break_html}</div>
        {f'<div class="info-text {info_color}">{info_text}</div>' if info_text else ''}
    </div>
    """
    return html

def format_currency(value):
    if isinstance(value, str):
        # Se já for uma string formatada, retorna ela mesma
        if value.startswith("R$"):
            return value
        try:
            value = float(value.replace(".", "").replace(",", ".").strip())
        except ValueError:
            return value  # Retorna o valor original se não puder ser convertido
    
    if isinstance(value, (int, float)):
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    return str(value) 

def format_percentage(value):
    if isinstance(value, (int, float)):
        return f"{value:.2%}"
    return value

def format_number(value):
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return value

def create_dashboard():
    try:
        df = st.session_state.get('df')
        brand_data = st.session_state.get('brand_data')
        client_status_data = st.session_state.get('client_status_data')
        cod_colaborador = st.session_state.get('cod_colaborador')
        start_date = st.session_state.get('start_date')
        end_date = st.session_state.get('end_date')
        selected_channels = st.session_state.get('selected_channels')
        selected_ufs = st.session_state.get('selected_ufs')
        selected_brands = st.session_state.get('selected_brands')
        selected_colaboradores = st.session_state.get('selected_colaboradores')
        selected_teams = st.session_state.get('selected_teams')
        show_additional_info = st.session_state.get('show_additional_info', False)

        # Verificações iniciais
        if df is None:
            st.warning("Nenhum dado carregado. Por favor, escolha os filtros e acione Atualizar Dados.")
            return
        elif df.empty:
            st.warning("Não há dados para o período e/ou filtros selecionados.")
            return

        # Título da página
        if cod_colaborador:
            st.title(f'Performance de Vendas 📈 - Colaborador {cod_colaborador}')
        else:
            st.title('Performance de Vendas 📈')

        # Processamento dos dados
        # Aplicar filtro de marcas se necessário
        if selected_brands and 'marca' in df.columns:
            df = df[df['marca'].isin(selected_brands)]

        # Converter datas
        df['mes_ref'] = pd.to_datetime(df['mes_ref'])
        df = df.sort_values('mes_ref')
        
        # Criar range de datas adequado ao período
        if start_date and end_date:
            # Se as datas são do mesmo mês, usar o próprio mês
            if start_date.replace(day=1) == end_date.replace(day=1):
                date_range = pd.DatetimeIndex([start_date.replace(day=1)])
            else:
                # Caso contrário, criar range mensal
                date_range = pd.date_range(
                    start=start_date.replace(day=1),
                    end=end_date.replace(day=1),
                    freq='MS'
                )
        else:
            date_range = pd.DatetimeIndex([df['mes_ref'].min()])

        # Criar DataFrame base com as datas
        all_months = pd.DataFrame({'mes_ref': date_range})

        # Agregar dados
        monthly_data = df.groupby(df['mes_ref'].dt.to_period('M')).agg({
            'faturamento_liquido': 'sum',
            'positivacao': 'sum',
            'desconto': 'sum',
            'faturamento_bruto': 'sum',
            'valor_bonificacao': 'sum',
            'valor_devolucao': 'sum',
            'qtd_pedido': 'sum',
            'custo_total': 'sum'
        }).reset_index()
        
        # Converter período para timestamp para o merge
        monthly_data['mes_ref'] = monthly_data['mes_ref'].dt.to_timestamp()

        # Merge e preenchimento de valores nulos
        monthly_data = pd.merge(
            all_months,
            monthly_data,
            on='mes_ref',
            how='left'
        ).fillna(0)

        # Calcular totais
        total_data = monthly_data.drop('mes_ref', axis=1).sum()

        # Display do período usando as datas originais da session
        st.markdown(
            f"<h4 style='text-align: left; color: #666666;'>"
            f"Métricas de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}</h4>",
            unsafe_allow_html=True
        )

        # Cálculos
        markup_value = ((total_data['faturamento_liquido'] - total_data['custo_total']) / total_data['custo_total'] + 1) if total_data['custo_total'] > 0 else 0
        desconto_percentual = (total_data['desconto'] / total_data['faturamento_bruto'] * 100) if total_data['faturamento_bruto'] != 0 else 0
        bonificacao_percentual = (total_data['valor_bonificacao'] / total_data['faturamento_liquido'] * 100) if total_data['faturamento_liquido'] != 0 else 0
        devolucao_percentual = (total_data['valor_devolucao'] / total_data['faturamento_liquido'] * 100) if total_data['faturamento_liquido'] != 0 else 0

        # Estilo CSS
        st.markdown("""
        <style>
        .metric-container {
            background-color: #f0f2f6;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 10px;
        }
        .metric-container:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
            transition: all 0.3s ease;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .metric-label {
            font-size: 16px;
            color: #555;
        }
        .info-text {
            font-size: 14px;
            margin-top: 5px;
        }
        .info-text.green {
            color: green;
        }
        .info-text.red {
            color: red;
        }
        .dataframe-container {
            width: 1000%;
            margin: auto;
            overflow-x: auto;
        }
        .dataframe {
            font-size: 24px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Calcula o número de clientes únicos para todo o período
        clientes_unicos_periodo = get_unique_customers_period(
            cod_colaborador, start_date, end_date, selected_channels, 
            selected_ufs, selected_brands, selected_colaboradores, selected_teams
        )

        # Métricas
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.markdown(create_metric_html(
                "Faturamento Líquido", 
                total_data['faturamento_liquido'],
                info_text="<br>",
                is_currency=True,
                line_break=True
            ), unsafe_allow_html=True)

        with col2:
            st.markdown(create_metric_html(
                "Desconto", 
                total_data['desconto'],
                f"({(desconto_percentual):,.2f}% do faturamento bruto)", 
                "red",
                is_currency=True,
                line_break=True
            ), unsafe_allow_html=True)

        with col3:
            st.markdown(create_metric_html(
                "Bonificação", 
                total_data['valor_bonificacao'],
                f"({(bonificacao_percentual):,.2f}% do faturamento líquido)", 
                "green",
                is_currency=True,
                line_break=True
            ), unsafe_allow_html=True)

        with col4:
            st.markdown(create_metric_html(
                "Devolucao", 
                total_data['valor_devolucao'],
                f"({(devolucao_percentual):,.2f}% do faturamento líquido)", 
                "green",
                is_currency=True,
                line_break=True
            ), unsafe_allow_html=True)


        # Segunda linha de métricas
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            #markup_value = ((total_data['faturamento_liquido'] - total_data['custo_total'])  / total_data['custo_total'])+1
            st.markdown(create_metric_html("Markup", f"{markup_value:.2f}".replace('.', ','), info_text="<br>",line_break=True), unsafe_allow_html=True)

        with col2:
            st.markdown(create_metric_html(
                "Clientes Únicos", 
                f"{clientes_unicos_periodo:,.0f}".replace(',', '.'), 
                info_text="no período selecionado",
                line_break=True
            ), unsafe_allow_html=True)

        with col3:
            st.markdown(create_metric_html("Pedidos", f"{total_data['qtd_pedido']:,.0f}".replace(',', '.'), info_text="<br>",line_break=True),unsafe_allow_html=True)        


        # Gráfico de Faturamento e Positivações ao longo do tempo
        fig_time = make_subplots(specs=[[{"secondary_y": True}]])

        threshold = np.percentile(monthly_data['faturamento_liquido'], 25)

        formatted_values = monthly_data['faturamento_liquido'].apply(format_currency)
        formatted_values_positivacao = monthly_data['positivacao'].map("{:,.0f}".format).str.replace(',', '.', regex=False)

        try:
            # Seletor de granularidade
            granularity = st.selectbox(
                "Selecione a granularidade temporal:",
                options=['Mensal', 'Semanal'],
                index=0
            )
            
            # Processe os dados de acordo com a granularidade selecionada
            processed_data = process_data_by_granularity(df, granularity)
            
            if processed_data is not None and not processed_data.empty:
                fig_time = make_subplots(specs=[[{"secondary_y": True}]])
                
                # Configurar valores do eixo x e dados para o gráfico
                x_values = processed_data['periodo_desc']
                
                if granularity == 'Semanal':
                    hover_template = "Período: %{x}<br>%{text}"
                else:
                    hover_template = "Mês: %{x}<br>%{text}"
                
                # Formatar valores para exibição
                formatted_values = processed_data['faturamento_liquido'].fillna(0).apply(format_currency)
                formatted_positivacao = processed_data['positivacao'].fillna(0).map("{:,.0f}".format).str.replace(',', '.', regex=False)
                
                # Barra de Faturamento
                fig_time.add_trace(
                    go.Bar(
                        x=x_values,
                        y=processed_data['faturamento_liquido'],
                        name="Faturamento",
                        marker_color='lightblue',
                        textfont=dict(size=12, color='black'),
                        text=formatted_values,
                        textposition='auto',
                        insidetextanchor='middle',
                        textangle=0,
                        hovertemplate=hover_template.replace("%{text}", "Faturamento: %{text}")
                    ),
                    secondary_y=False
                )
                
                # Linha de Positivação
                fig_time.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=processed_data['positivacao'],
                        name="Clientes Únicos",
                        mode='lines+markers+text',
                        line=dict(color='red', width=2),
                        marker=dict(size=10),
                        textfont=dict(size=12),
                        text=formatted_positivacao,
                        textposition='top center',
                        hovertemplate=hover_template.replace("%{text}", "Clientes Únicos: %{text}")
                    ),
                    secondary_y=True
                )
                
                # Layout do gráfico
                fig_time.update_layout(
                    title_text=f"Evolução de Clientes Únicos e Faturamento ({granularity})",
                    xaxis_title="Período",
                    xaxis=dict(
                        type='category',
                        tickangle=45,
                        tickmode='array',
                        ticktext=x_values,
                        tickvals=x_values,
                    ),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1, font=dict(size=16)),
                    margin=dict(l=20, r=20, t=60, b=20),
                    hovermode="x unified",
                    font=dict(size=16),
                    title=dict(font=dict(size=20))
                )
                
                fig_time.update_yaxes(title_text="Faturamento (R$)", secondary_y=False)
                fig_time.update_yaxes(title_text="Clientes Únicos", secondary_y=True)
                
                st.plotly_chart(fig_time, use_container_width=True)
                st.divider()
            else:
                st.warning("Não há dados suficientes para gerar o gráfico para o período selecionado.")
                
        except Exception as e:
            st.error(f"Erro ao gerar o gráfico: {str(e)}")
            logging.error(f"Erro na geração do gráfico: {str(e)}", exc_info=True)

    # Dados por marca

        if brand_data is not None and not brand_data.empty and 'marca' in brand_data.columns:
            st.markdown("<h3 style='font-size:20px;'><b>Dados por marca:</b></h3>", unsafe_allow_html=True)
            
            # Filtro de marcas (se aplicável)
            if st.session_state['user']['role'] != 'vendedor' and st.session_state['selected_brands']:
                brand_data = brand_data[brand_data['marca'].isin(st.session_state['selected_brands'])]
            
            # Preparação dos dados
            total_faturamento = brand_data['faturamento'].sum()
            brand_data['share'] = brand_data['faturamento'] / total_faturamento
            brand_data['markup'] = brand_data['markup_percentual'].apply(lambda x: x/100 + 1 if isinstance(x, (int, float)) else x)
            brand_data = brand_data.sort_values('faturamento', ascending=False)
            
            # Seleção das colunas
            display_data = brand_data[['marca', 'faturamento', 'share', 'clientes_unicos', 'qtd_pedido', 'qtd_sku', 'Ticket_Medio_Positivacao', 'markup']].copy()
            
            # Aplicando estilos
            styler = display_data.style.format({
                'faturamento': format_currency,
                'share': format_number, #format_percentage,
                'Ticket_Medio_Positivacao': format_currency,
                'markup': format_number
            })
            
            # Destacando o maior valor em cada coluna numérica
            numeric_columns = ['faturamento', 'share', 'clientes_unicos', 'qtd_pedido', 'qtd_sku', 'Ticket_Medio_Positivacao', 'markup']
        
            
            # Adicionando barras de progresso para o share
            styler.bar(subset=['share'], color='#5fba7d', vmin=0, vmax=1)

            st.markdown("""
            <style>
                .dataframe-container {
                    width: 100%;
                    margin: auto;
                    overflow-x: auto;
                }
                .dataframe {
                    font-size: 14px;
                    width: 100%;
                }
                .stDataFrame {
                    width: 100%;
                }
            </style>
            """, unsafe_allow_html=True)

            # Crie uma coluna central para o dataframe
            col1, col2, col3 = st.columns([1, 6, 1])  # Ajuste esses valores para alterar a largura

            with col2:  # Coluna central
                st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
                
                # Configuração do dataframe interativo
                st.dataframe(
                    styler,
                    column_config={
                        "marca": "Marca",
                        "faturamento": st.column_config.TextColumn("Faturamento"),
                        "share": st.column_config.ProgressColumn("Share", min_value=0, max_value=1),
                        "clientes_unicos": st.column_config.NumberColumn("Clientes Únicos", format="%d"),
                        "qtd_pedido": st.column_config.NumberColumn("Qtd. Pedidos", format="%d"),
                        "qtd_sku": st.column_config.NumberColumn("Qtd. SKUs", format="%d"),
                        "Ticket_Medio_Positivacao": st.column_config.TextColumn("Ticket Médio"),
                        "markup": st.column_config.TextColumn("Markup")
                    },
                    height=350,
                    use_container_width=True,  # Alterado para True
                    hide_index=True
                )

                st.markdown('</div>', unsafe_allow_html=True)

            # Fora da coluna central
            st.write(f"Total de Faturamento: {format_currency(total_faturamento)}")
            st.write(f"Total de Marcas: {len(display_data)}")
        else:
            st.warning("Não há dados por marca disponíveis para o período e/ou filtros selecionados.")

        # Adicionar o gráfico de status do cliente
        st.subheader("Status dos Clientes")
        if client_status_data is not None and not client_status_data.empty:
            fig_percentages, fig_base, status_averages = create_client_status_chart(client_status_data)
            
            if fig_base is not None:
                st.plotly_chart(fig_base, use_container_width=True)
            else:
                st.warning("Gráfico da base total de clientes não disponível.")

            if fig_percentages is not None:
                st.plotly_chart(fig_percentages, use_container_width=True)
            else:
                st.warning("Gráfico de percentuais não disponível.")            
            
            # Apresentar os percentuais de cada status
            if status_averages is not None and not status_averages.empty:
                # Remover a 'Base' das médias, se existir
                if 'Base' in status_averages.index:
                    total = status_averages['Base']
                    status_averages = status_averages.drop('Base')
                else:
                    total = status_averages.sum()

                # Calcular percentuais
                percentages = (status_averages / total * 100).sort_values(ascending=False)

                # Criar a string de status e percentuais
                status_string = ", ".join([f"{status}: {percentage:.2f}%" for status, percentage in percentages.items()])

                # Exibir a string usando st.write
                st.write(f"Média dos Status:")
                st.write(f"{status_string}")
            else:
                st.warning("Não há dados de status disponíveis.")
        else:
            st.warning("Não há dados disponíveis para os gráficos de status do cliente.")

        if show_additional_info:
            with st.expander("Informações Adicionais"):
                st.dataframe(df)

    except Exception as e:
        st.error(f"Erro ao processar os dados do dashboard: {str(e)}")
        logging.error(f"Erro no dashboard: {str(e)}", exc_info=True)

def main():
    try:
        init_session_state()
        load_page_specific_state("Performance_Vendedor")

        if not st.session_state.get('logged_in', False):
            st.warning("Por favor, faça login na página inicial para acessar esta página.")
            return

        st.set_page_config(page_title="Performance de Vendas", layout="wide", page_icon=ico_path)
        st.sidebar.title('Filtros')
        load_filters()
        create_dashboard()

    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {str(e)}")
        logging.error(f"Erro ao carregar o dashboard: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()