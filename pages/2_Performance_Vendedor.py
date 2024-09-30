import streamlit as st
import pandas as pd
from datetime import date
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from PIL import Image
import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from session_state_manager import init_session_state, load_page_specific_state
from utils import (
    get_monthly_revenue, 
    get_brand_data, 
    get_channels_and_ufs, 
    get_colaboradores, 
    get_client_status,
    create_client_status_chart
)

logging.basicConfig(level=logging.INFO)

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

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
    if st.session_state['user']['role'] in ['admin', 'gestor']:
        st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state['cod_colaborador'])
        show_all_filters = True
    else:
        st.sidebar.info(f"Vendedor: {st.session_state['user']['username']}")
        st.sidebar.info(f"Código do Colaborador: {st.session_state['user']['cod_colaborador']}")
        show_all_filters = False
        st.session_state['cod_colaborador'] = st.session_state['user']['cod_colaborador']

    st.session_state['start_date'] = st.sidebar.date_input("Data Inicial", st.session_state['start_date'])
    st.session_state['end_date'] = st.sidebar.date_input("Data Final", st.session_state['end_date'])

    if show_all_filters:
        channels, ufs = get_channels_and_ufs_cached(st.session_state['cod_colaborador'], st.session_state['start_date'], st.session_state['end_date'])
        
        st.session_state['selected_channels'] = st.sidebar.multiselect("Selecione os canais de venda", options=channels, default=st.session_state['selected_channels'])
        st.session_state['selected_ufs'] = st.sidebar.multiselect("Selecione as UFs", options=ufs, default=st.session_state['selected_ufs'])

        brand_data = st.session_state.get('brand_data', pd.DataFrame())
        available_brands = brand_data['marca'].unique().tolist() if brand_data is not None and 'marca' in brand_data.columns and not brand_data.empty else []
        
        previous_selected_brands = st.session_state.get('selected_brands', [])
        st.session_state['selected_brands'] = st.sidebar.multiselect(
            "Selecione as marcas (deixe vazio para todas)", 
            options=available_brands, 
            default=previous_selected_brands
        )
        if st.session_state['selected_brands'] != previous_selected_brands:
            st.session_state['data_needs_update'] = True

        colaboradores_df = get_colaboradores_cached(st.session_state['start_date'], st.session_state['end_date'], st.session_state['selected_channels'], st.session_state['selected_ufs'])
        available_colaboradores = colaboradores_df['nome_colaborador'].tolist()
        st.session_state['selected_colaboradores'] = st.sidebar.multiselect("Selecione os colaboradores (deixe vazio para todos)", options=available_colaboradores, default=st.session_state['selected_colaboradores'])
    else:
        st.session_state['selected_channels'] = []
        st.session_state['selected_ufs'] = []
        st.session_state['selected_brands'] = []
        st.session_state['selected_colaboradores'] = [st.session_state['user']['username']]

    st.session_state['show_additional_info'] = st.sidebar.checkbox("Mostrar informações adicionais", False, key="show_additional_info_checkbox")

    if st.sidebar.button("Atualizar Dados"):
        st.session_state['data_needs_update'] = True

    # Sempre atualize os dados se as datas mudarem
    if st.session_state['start_date'] != st.session_state.get('previous_start_date') or \
       st.session_state['end_date'] != st.session_state.get('previous_end_date'):
        st.session_state['data_needs_update'] = True
        st.session_state['previous_start_date'] = st.session_state['start_date']
        st.session_state['previous_end_date'] = st.session_state['end_date']


def load_data():
    if st.session_state['data_needs_update']:
        progress_text = "Operação em andamento. Aguarde..."
        my_bar = st.progress(0, text=progress_text)

        try:
            logging.info("load_data: Iniciando carregamento de dados")
            logging.info(f"load_data: cod_colaborador = {st.session_state['cod_colaborador']}")
            
            my_bar.progress(10, text="Carregando dados de receita mensal...")
            df = get_monthly_revenue_cached(
                cod_colaborador=st.session_state['cod_colaborador'],
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                selected_channels=st.session_state['selected_channels'],
                selected_ufs=st.session_state['selected_ufs'],
                selected_brands=st.session_state['selected_brands'],
                selected_nome_colaborador=st.session_state['selected_colaboradores']
            )
            logging.info(f"load_data: Dados de receita mensal carregados. Shape: {df.shape}")
            
            st.session_state['df'] = apply_filters(df)
            logging.info(f"load_data: Dados filtrados. Shape após filtro: {st.session_state['df'].shape}")

            logging.info("load_data: Carregando dados de marca")
            logging.info(f"load_data: cod_colaborador = {st.session_state['cod_colaborador']}")

            my_bar.progress(40, text="Carregando dados de marca...")
            brand_data = get_brand_data_cached(
                cod_colaborador=st.session_state['cod_colaborador'],
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                selected_channels=st.session_state['selected_channels'],
                selected_ufs=st.session_state['selected_ufs'],
                selected_nome_colaborador=st.session_state['selected_nome_colaborador']
            )
            st.session_state['brand_data'] = apply_filters(brand_data)

            logging.info("load_data: Iniciando carregamento de dados")
            logging.info(f"load_data: cod_colaborador = {st.session_state['cod_colaborador']}")
            logging.info(f"load_data: brand_data = {st.session_state['brand_data']}")
            my_bar.progress(70, text="Carregando dados de status do cliente...")
            client_status_data = get_client_status(
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                cod_colaborador=st.session_state['cod_colaborador'],
                selected_channels=st.session_state['selected_channels'],
                selected_ufs=st.session_state['selected_ufs'],
                selected_nome_colaborador=st.session_state['selected_nome_colaborador'],
                selected_brands=st.session_state['selected_brands']
            )
            st.session_state['client_status_data'] = apply_filters(client_status_data)

            logging.info("load_data: Iniciando carregamento de dados")
            logging.info(f"load_data: cod_colaborador = {st.session_state['cod_colaborador']}")
            logging.info(f"load_data: cliente_status = {st.session_state['client_status_data']}")
            my_bar.progress(100, text="Carregamento concluído!")
            time.sleep(1)
            my_bar.empty()

            st.session_state['data_needs_update'] = False
            logging.info("load_data: Carregamento de dados concluído")

        except Exception as e:
            my_bar.empty()
            st.error(f"Erro ao carregar dados: {str(e)}")
            logging.error(f"Erro ao carregar dados: {str(e)}", exc_info=True)

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
        st.title(f'Dashboard de Vendas - Colaborador {cod_colaborador}')
    else:
        st.title('Dashboard de Vendas 📈')

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
        'positivacao': 'sum'
    }).reset_index()

    # Mesclando com todos os meses para garantir que todos os meses apareçam
    monthly_data = pd.merge(all_months, monthly_data, on='mes_ref', how='left').fillna(0)

    # Obtendo o mês mais recente
    latest_month = df['mes_ref'].max()
    latest_data = df[df['mes_ref'] == latest_month].groupby('mes_ref').sum().iloc[0]

    # Cálculo dos percentuais
    desconto_percentual = (latest_data['desconto'] / latest_data['faturamento_bruto']) * 100 if latest_data['faturamento_bruto'] != 0 else 0
    bonificacao_percentual = (latest_data['valor_bonificacao'] / latest_data['faturamento_liquido']) * 100 if latest_data['faturamento_liquido'] != 0 else 0

    # Métricas
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:        
        st.metric("Faturamento", f"R$ {latest_data['faturamento_liquido']:,.2f}")
    with col2:
        st.metric("Desconto", f"R$ {latest_data['desconto']:,.2f}")
        st.markdown(f"<p style='font-size: medium; color: green;'>({desconto_percentual:.2f}% do faturamento bruto)</p>", unsafe_allow_html=True)
    with col3:
        st.metric("Bonificação", f"R$ {latest_data['valor_bonificacao']:,.2f}")
        st.markdown(f"<p style='font-size: medium; color: green;'>({bonificacao_percentual:.2f}% do faturamento líquido)</p>", unsafe_allow_html=True)
    with col4:
        st.metric("Clientes Únicos", f"{latest_data['positivacao']:,.0f}")
    with col5:
        st.metric("Pedidos", f"{latest_data['qtd_pedido']:,.0f}")
     
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:        
        # Ajustando o formato do markup para ser igual ao da tabela
        markup_value = latest_data['markup_percentual'] / 100 + 1
        st.metric("Markup", f"{markup_value:.2f}")

    # Gráfico de Faturamento e Positivações ao longo do tempo
    fig_time = make_subplots(specs=[[{"secondary_y": True}]])

    fig_time.add_trace(
        go.Bar(
            x=monthly_data['mes_ref'], 
            y=monthly_data['faturamento_liquido'], 
            name="Faturamento",
            marker_color='lightblue',
            text=monthly_data['faturamento_liquido'].apply(lambda x: f"R$ {x:,.0f}"),
            textposition='outside',
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
            marker=dict(size=8),
            text=monthly_data['positivacao'].apply(lambda x: f"{x:,.0f}"),
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified"
    )

    fig_time.update_yaxes(title_text="Faturamento (R$)", secondary_y=False)
    fig_time.update_yaxes(title_text="Clientes Únicos", secondary_y=True)

    st.plotly_chart(fig_time, use_container_width=True)
    st.divider()

    # Dados por marca
    if brand_data is not None and not brand_data.empty and 'marca' in brand_data.columns:
        st.write("Dados por marca:")
        
        # Aplicar filtro de marcas selecionadas
        if selected_brands:
            brand_data = brand_data[brand_data['marca'].isin(selected_brands)]
        
        # Calculando o total de faturamento para o share
        total_faturamento = brand_data['faturamento'].sum()
        
        # Calculando o share e formatando o markup
        brand_data['share'] = brand_data['faturamento'] / total_faturamento
        brand_data['markup'] = brand_data['markup_percentual'].apply(lambda x: f"{(x/100 + 1):.2f}")
        
        # Ordenando por faturamento
        brand_data = brand_data.sort_values('faturamento', ascending=False)
        
        # Definindo as colunas que queremos exibir
        desired_columns = ['marca', 'faturamento', 'share', 'clientes_unicos', 'qtd_pedido', 'qtd_sku', 'Ticket_Medio_Positivacao', 'markup']
        
        # Criando um novo DataFrame com as colunas desejadas
        display_data = brand_data[desired_columns].copy().set_index('marca')
        
        # Formatando as colunas numéricas
        display_data['faturamento'] = display_data['faturamento'].apply(lambda x: f"R$ {x:,.2f}")
        display_data['Ticket_Medio_Positivacao'] = display_data['Ticket_Medio_Positivacao'].apply(lambda x: f"R$ {x:,.2f}")
        display_data['share'] = display_data['share'].apply(lambda x: f"{x:.2%}")
        
        st.dataframe(display_data,
                     column_config={
                         "share": st.column_config.ProgressColumn(
                             "share"
                         )
                     })
    else:
        st.warning("Não há dados por marca disponíveis para o período e/ou filtros selecionados.")

    # Adicionar o gráfico de status do cliente
    st.subheader("Status dos Clientes")
    if client_status_data is not None and not client_status_data.empty:
        fig_percentages, fig_base = create_client_status_chart(client_status_data)
        
        if fig_percentages is not None:
            st.plotly_chart(fig_percentages, use_container_width=True)
        else:
            st.warning("Gráfico de percentuais não disponível.")
        
        if fig_base is not None:
            st.plotly_chart(fig_base, use_container_width=True)
        else:
            st.warning("Gráfico da base total de clientes não disponível.")
    else:
        st.warning("Não há dados disponíveis para os gráficos de status do cliente.")

    if show_additional_info:
        with st.expander("Informações Adicionais"):
            st.dataframe(df)

def update_filter_options():
    brand_data = st.session_state.get('brand_data', pd.DataFrame())
    df = st.session_state.get('df', pd.DataFrame())

    filter_options = {
        'marca': brand_data['marca'].unique().tolist() if 'marca' in brand_data.columns else [],
        'canal_venda': df['canal_venda'].unique().tolist() if 'canal_venda' in df.columns else [],
        'uf': df['uf'].unique().tolist() if 'uf' in df.columns else [],
    }

    for filter_name, options in filter_options.items():
        if options:
            st.session_state[f'selected_{filter_name}s'] = st.sidebar.multiselect(
                f"Selecione {filter_name.replace('_', ' ')}s",
                options=options,
                default=st.session_state.get(f'selected_{filter_name}s', [])
            )
    
    st.session_state['data_needs_update'] = True

def load_data_for_vendedor(cod_colaborador):
    with st.spinner('Carregando dados...'):
        try:
            st.session_state['df'] = get_monthly_revenue_cached(
                cod_colaborador=cod_colaborador,
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                selected_channels=None,
                selected_ufs=None,
                selected_brands=None,
                selected_nome_colaborador=None
            )
            
            st.session_state['brand_data'] = get_brand_data_cached(
                cod_colaborador=cod_colaborador,
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                selected_channels=None,
                selected_ufs=None,
                selected_nome_colaborador=None
            )
            
            st.session_state['client_status_data'] = get_client_status(
                start_date=st.session_state['start_date'],
                end_date=st.session_state['end_date'],
                cod_colaborador=cod_colaborador,
                selected_channels=None,
                selected_ufs=None,
                selected_nome_colaborador=None,
                selected_brands=None
            )
            
            logging.info(f"Dados carregados para o vendedor {cod_colaborador}")
            logging.info(f"Shape de df: {st.session_state['df'].shape}")
            logging.info(f"Shape de brand_data: {st.session_state['brand_data'].shape}")
            logging.info(f"Shape de client_status_data: {st.session_state['client_status_data'].shape}")
            
        except Exception as e:
            st.error(f"Erro ao carregar dados para o vendedor: {str(e)}")
            logging.error(f"Erro ao carregar dados para o vendedor: {str(e)}", exc_info=True)

def main():
    st.set_page_config(page_title="Dashboard de Vendas", layout="wide", page_icon=ico_path)
    init_session_state()
    load_page_specific_state("Performance_Vendedor")

    try:
        st.sidebar.title('Configurações do Dashboard')
        
        if st.session_state['user']['role'] == 'vendedor':
            # Para vendedor, carregue os dados imediatamente com o cod_colaborador
            load_data_for_vendedor(st.session_state['user']['cod_colaborador'])
        else:
            # Para admin/gestor, carregue os filtros primeiro
            load_filters()
            
            if st.session_state['data_needs_update']:
                load_data()

        create_dashboard()

    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {str(e)}")
        logging.error(f"Erro ao carregar o dashboard: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()