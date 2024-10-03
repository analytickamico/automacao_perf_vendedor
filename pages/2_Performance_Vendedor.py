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
from session_state_manager import init_session_state, load_page_specific_state, ensure_cod_colaborador
from utils import get_monthly_revenue
from utils import get_brand_data
from utils import get_channels_and_ufs
from utils import get_colaboradores
from utils import get_client_status
from utils import create_client_status_chart
from utils import get_brand_options
from utils import get_team_options

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

@st.cache_data
def get_monthly_revenue_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador):
    channel_filter = f"AND pedidos.canal_venda IN ('{', '.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{', '.join(selected_ufs)}')" if selected_ufs else ""
    brand_filter = f"AND item_pedidos.marca IN ('{', '.join(selected_brands)}')" if selected_brands else ""
    return get_monthly_revenue(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador)

@st.cache_data
def get_brand_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador):
    return get_brand_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador)

@st.cache_data
def get_channels_and_ufs_cached(cod_colaborador, start_date, end_date):
    return get_channels_and_ufs(cod_colaborador, start_date, end_date)

@st.cache_data
def get_colaboradores_cached(start_date, end_date, selected_channels, selected_ufs):
    return get_colaboradores(start_date, end_date, selected_channels, selected_ufs)


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
    ensure_cod_colaborador()
    user = st.session_state.get('user', {})
    
    if user.get('role') in ['admin', 'gestor']:
        st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state.get('cod_colaborador', ''), key="cod_colaborador_input")
    #elif user.get('role') == 'vendedor':
        #st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")
    else:
        st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")
        #return

    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", st.session_state.get('start_date', date.today()), key="start_date_input")
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", st.session_state.get('end_date', date.today()), key="end_date_input")

    channels, ufs = get_channels_and_ufs_cached(st.session_state.get('cod_colaborador', ''), st.session_state['start_date'], st.session_state['end_date'])
    
    st.session_state['selected_channels'] = st.sidebar.multiselect("Selecione os canais de venda", options=channels, default=st.session_state.get('selected_channels', []), key="channels_multiselect")

    if user.get('role') in ['admin', 'gestor']:
        team_options = get_team_options(st.session_state['start_date'], st.session_state['end_date'])
        st.session_state['selected_teams'] = st.sidebar.multiselect("Selecione as equipes", options=team_options, default=st.session_state.get('selected_teams', []), key="teams_multiselect")
    #else:
        #st.warning("Tipo de usuário não reconhecido.")
        #return

    st.session_state['selected_ufs'] = st.sidebar.multiselect("Selecione as UFs", options=ufs, default=st.session_state.get('selected_ufs', []), key="ufs_multiselect")

    # Adicionar carga de marcas
    brand_options = get_brand_options(st.session_state['start_date'], st.session_state['end_date'])
    st.session_state['selected_brands'] = st.sidebar.multiselect("Selecione as marcas", options=brand_options, default=st.session_state.get('selected_brands', []), key="brands_multiselect")

    if user.get('role') in ['admin', 'gestor']:
        colaboradores_df = get_colaboradores_cached(st.session_state['start_date'], st.session_state['end_date'], st.session_state['selected_channels'], st.session_state['selected_ufs'])
        available_colaboradores = colaboradores_df['nome_colaborador'].tolist() if not colaboradores_df.empty else []
        st.session_state['selected_colaboradores'] = st.sidebar.multiselect("Selecione os colaboradores (deixe vazio para todos)", options=available_colaboradores, default=st.session_state.get('selected_colaboradores', []), key="colaboradores_multiselect")



    if st.sidebar.button("Atualizar Dados", key="update_data_button"):
        st.session_state['data_needs_update'] = True

def load_data():
    if st.session_state['data_needs_update']:
        progress_text = "Operação em andamento. Aguarde..."
        my_bar = st.progress(0, text=progress_text)

        try:
            my_bar.progress(10, text="Carregando dados de receita mensal...")
            
            if st.session_state['user']['role'] == 'vendedor':
                selected_colaboradores = st.session_state['cod_colaborador']
            else:
                selected_colaboradores = st.session_state['selected_colaboradores']
            
            df = get_monthly_revenue(
                cod_colaborador=st.session_state['cod_colaborador'],
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                selected_channels=st.session_state['selected_channels'],
                selected_ufs=st.session_state['selected_ufs'],
                selected_brands=st.session_state['selected_brands'],
                selected_nome_colaborador=selected_colaboradores,
                selected_teams=st.session_state['selected_teams']
            )
            st.session_state['df'] = df

            my_bar.progress(40, text="Carregando dados de marca...")
            brand_data = get_brand_data(
                cod_colaborador=st.session_state['cod_colaborador'],
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                selected_channels=st.session_state['selected_channels'],
                selected_ufs=st.session_state['selected_ufs'],
                selected_nome_colaborador=selected_colaboradores,
                selected_teams=st.session_state['selected_teams']
            )
            
            if st.session_state['selected_brands']:
                brand_data = brand_data[brand_data['marca'].isin(st.session_state['selected_brands'])]
            
            st.session_state['brand_data'] = brand_data

            my_bar.progress(70, text="Carregando dados de status do cliente...")
            client_status_data = get_client_status(
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                cod_colaborador=st.session_state['cod_colaborador'],
                selected_channels=st.session_state['selected_channels'],
                selected_ufs=st.session_state['selected_ufs'],
                selected_nome_colaborador=selected_colaboradores,
                selected_brands=st.session_state['selected_brands'],
                selected_teams=st.session_state['selected_teams']
            )
            st.session_state['client_status_data'] = client_status_data

            my_bar.progress(90, text="Finalizando carregamento...")

            st.session_state['data_needs_update'] = False
            my_bar.progress(100, text="Carregamento concluído!")
            time.sleep(1)
            my_bar.empty()

        except Exception as e:
            my_bar.empty()
            st.error(f"Erro ao carregar dados: {str(e)}")
            logging.error(f"Erro ao carregar dados: {str(e)}", exc_info=True)

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
    show_additional_info = st.session_state.get('show_additional_info', False)

    logging.info(f"create_dashboard: cod_colaborador = {cod_colaborador}")
    logging.info(f"create_dashboard: start_date = {start_date}, end_date = {end_date}")
    logging.info(f"create_dashboard: selected_channels = {selected_channels}")
    logging.info(f"create_dashboard: selected_ufs = {selected_ufs}")
    logging.info(f"create_dashboard: selected_brands = {selected_brands}")
    logging.info(f"create_dashboard: selected_colaboradores = {selected_colaboradores}")

    if df is None:
        logging.warning("create_dashboard: df is None")
        st.warning("Nenhum dado carregado. Por favor, verifique os filtros e tente novamente.")
        return
    elif df.empty:
        logging.warning(f"create_dashboard: df is empty. Columns: {df.columns}")
        st.warning("Não há dados para o período e/ou filtros selecionados.")
        return
    else:
        logging.info(f"create_dashboard: df shape = {df.shape}")
        logging.info(f"create_dashboard: df columns = {df.columns}")
        logging.info(f"create_dashboard: df head = \n{df.head()}")

    if cod_colaborador:
        st.title(f'Performance de Vendas 📈 - Colaborador {cod_colaborador}')
    else:
        st.title('Performance de Vendas 📈')

       

    # Aplicar filtro de marcas ao DataFrame principal
    if selected_brands and 'marca' in df.columns:
        df = df[df['marca'].isin(selected_brands)]

    # Convertendo a coluna mes_ref para datetime e ordenando o DataFrame
    df['mes_ref'] = pd.to_datetime(df['mes_ref'])
    df = df.sort_values('mes_ref')

    # Criando um DataFrame com todos os meses no intervalo
    date_range = pd.date_range(start=start_date, end=end_date, freq='MS')
    all_months = pd.DataFrame({'mes_ref': date_range})

    # Agrupando os dados por mês
    monthly_data = df.groupby('mes_ref').agg({
        'faturamento_liquido': 'sum',
        'positivacao': 'sum',
        'desconto': 'sum',
        'faturamento_bruto': 'sum',
        'valor_bonificacao': 'sum',
        'qtd_pedido': 'sum' ,
        'custo_total': 'sum'
    }).reset_index()

    # Mesclando com todos os meses para garantir que todos os meses apareçam
    monthly_data = pd.merge(all_months, monthly_data, on='mes_ref', how='left').fillna(0)

    # Calculando o somatório de todos os meses, excluindo a coluna 'mes_ref'
    total_data = monthly_data.drop('mes_ref', axis=1).sum()
 

    # Adicionar a informação do período total
    start_month = df['mes_ref'].min().strftime("%m/%Y")
    end_month = df['mes_ref'].max().strftime("%m/%Y")
    st.markdown(f"<h4 style='text-align: left; color: #666666;'>Métricas de {start_month} a {end_month}</h4>", unsafe_allow_html=True)
  

    # Cálculo dos percentuais baseados no total
    desconto_percentual = (total_data['desconto'] / total_data['faturamento_bruto']) * 100 if total_data['faturamento_bruto'] != 0 else 0
    bonificacao_percentual = (total_data['valor_bonificacao'] / total_data['faturamento_liquido']) * 100 if total_data['faturamento_liquido'] != 0 else 0

    # Adicione este CSS personalizado no início do seu aplicativo
    # Adicione este CSS no início do seu script ou em um arquivo .css separado


    # Estilo CSS (coloque isso no início do seu script)
    st.markdown("""
    <style>
    /* Seus estilos existentes */
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

    /* Novos estilos para o dataframe */
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
        st.markdown(create_metric_html("Clientes Únicos", f"{total_data['positivacao']:,.0f}".replace(',', '.'), info_text="<br>",line_break=True), unsafe_allow_html=True)

    with col5:
        st.markdown(create_metric_html("Pedidos", f"{total_data['qtd_pedido']:,.0f}".replace(',', '.'), info_text="<br>",line_break=True),unsafe_allow_html=True)

    # Segunda linha de métricas
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        markup_value = ((total_data['faturamento_liquido'] - total_data['custo_total'])  / total_data['custo_total'])+1
        st.markdown(create_metric_html("Markup", f"{markup_value:.2f}".replace('.', ','), info_text="<br>",line_break=True), unsafe_allow_html=True)


    # Gráfico de Faturamento e Positivações ao longo do tempo
    fig_time = make_subplots(specs=[[{"secondary_y": True}]])

    threshold = np.percentile(monthly_data['faturamento_liquido'], 25)

    formatted_values = monthly_data['faturamento_liquido'].apply(format_currency)
    formatted_values_positivacao = monthly_data['positivacao'].map("{:,.0f}".format).str.replace(',', '.', regex=False)


    fig_time.add_trace(
        go.Bar(
            x=monthly_data['mes_ref'], 
            y=monthly_data['faturamento_liquido'], 
            name="Faturamento",
            marker_color='lightblue',
            #text=monthly_data['faturamento_liquido'].apply(lambda x: f"R${x/1000:.0f}K" if x >= 1000000 else f"R${x/1000:.1f}K"),
            textfont=dict(size=12, color='black'), 
            text=formatted_values,
            #text=monthly_data['faturamento_liquido'].apply(lambda x: f"R${x/1000:.0f}K"),
            textposition='auto', #monthly_data['faturamento_liquido']).apply(lambda x: 'outside' if x < threshold else 'inside'),
            insidetextanchor='middle',  # Centraliza o texto verticalmente dentro da barra
            textangle=0,  # Garante que o texto esteja horizontal
            hovertemplate="Mês: %{x|%B %Y}<br>Faturamento: R$ %{y:,.2f}<extra></extra>"
        ),
        secondary_y=False
    )

    fig_time.add_trace(
        go.Scatter(
            x=monthly_data['mes_ref'], 
            y=monthly_data['positivacao'], 
            name="Clientes Únicos",
            mode='lines+markers+text',
            line=dict(color='red', width=2),
            marker=dict(size=10),
            textfont=dict(size=12),
            text=formatted_values_positivacao, #monthly_data['positivacao'].apply(lambda x: f"{x:,.0f}"),
            textposition='top center',
            hovertemplate="Mês: %{x|%B %Y}<br>Clientes Únicos: %{y:,.0f}<extra></extra>"
        ),
        secondary_y=True
    )

    fig_time.update_layout(
        title_text="Evolução de Clientes Únicos e Faturamento",
        xaxis_title="Mês",
        xaxis=dict(
            tickformat="%b %Y",
            tickangle=45,
            tickmode='array',
            tickvals=monthly_data['mes_ref']
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1,font=dict(size=16)),
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
        font=dict(size=16),  # Aumenta o tamanho da fonte geral
        title=dict(font=dict(size=20))
    )

    fig_time.update_yaxes(title_text="Faturamento (R$)", secondary_y=False)
    fig_time.update_yaxes(title_text="Clientes Únicos", secondary_y=True)

    st.plotly_chart(fig_time, use_container_width=True)
    st.divider()

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
        styler.highlight_max(subset=numeric_columns, color='lightblue')
        
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

def main():
    init_session_state()  # Use init_session_state em vez de initialize_session_state
    if st.session_state.get('logout_requested', False):
        st.session_state['logout_requested'] = False
        # Adiciona checagem para evitar o rerun imediato
        if st.session_state.get('logged_in') is None: 
            st.write("Você foi desconectado. Recarregue a página para continuar.")
            return
    
    st.set_page_config(page_title="Performance de Vendas", layout="wide", page_icon=ico_path)
    load_page_specific_state("Performance_Vendedor")

    if not st.session_state.get('logged_in', False):
        st.warning("Por favor, faça login na página inicial para acessar esta página.")
        return

    try:
        st.sidebar.title('Configurações do Dashboard')
        
        user = st.session_state.get('user')
        if user and isinstance(user, dict) and 'role' in user:
            if user['role'] == 'vendedor':
                st.session_state['cod_colaborador'] = user.get('cod_colaborador', '')
                #st.sidebar.info(f"Código do Colaborador: {st.session_state['cod_colaborador']}")
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