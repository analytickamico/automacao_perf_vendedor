import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils import get_stock_data, get_abc_curve_data_with_stock, get_static_data, create_metric_html
from session_state_manager import init_session_state, load_page_specific_state
import traceback
import logging
import numpy as np
from datetime import datetime, timedelta
import time
from io import BytesIO

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Análise de Estoque", page_icon="📦", layout="wide")

end_date_est = datetime.now() - timedelta(days=1)
start_date_est = (end_date_est - timedelta(days=90)).strftime('%Y-%m-%d')

def highlight_max(s, props=''):
    return np.where(s == np.max(s.values), props, '')

def format_brazilian(value, decimal_places=2):
    return f"{value:,.{decimal_places}f}".replace(",", "X").replace(".", ",").replace("X", ".")

@st.cache_data(ttl=3600)
def get_stock_data_cached(start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_empresas):
    return get_stock_data(start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_empresas)

def initialize_session_state():
    if 'filter_options' not in st.session_state:
        st.session_state.filter_options = {
            'channels': [],
            'ufs': [],
            'brands': [],
            'empresas': []
        }
    if 'static_data' not in st.session_state:
        st.session_state.static_data = get_static_data()
    
    # Garantir que não haja valores None nas marcas
    st.session_state.filter_options['brands'] = [brand for brand in st.session_state.static_data.get('marcas', []) if brand is not None]

    # Inicializar selected_brands se não existir
    if 'selected_brands' not in st.session_state:
        st.session_state.selected_brands = st.session_state.filter_options['brands'].copy()
    if 'selected_channels' not in st.session_state:
        st.session_state.selected_channels = []
    if 'selected_ufs' not in st.session_state:
        st.session_state.selected_ufs = []
    if 'selected_brands' not in st.session_state:
        st.session_state.selected_brands = []
    if 'selected_empresas' not in st.session_state:  # Mudando para selected_empresas
        st.session_state.selected_empresas = []
    if 'static_data' not in st.session_state:
        st.session_state.static_data = get_static_data()

def load_filters():
    logging.info("Iniciando load_filters")
    initialize_session_state()

    user = st.session_state['user']
    user_role = user.get('role')
    logging.info(f"Papel do usuário: {user_role}")
    
    static_data = st.session_state.static_data
    logging.info(f"Dados estáticos obtidos: {static_data.keys()}")
    
    st.session_state.filter_options['channels'] = static_data.get('canais_venda', [])
    st.session_state.filter_options['ufs'] = static_data.get('ufs', [])
    st.session_state.filter_options['brands'] = static_data.get('marcas', [])
    st.session_state.filter_options['empresas'] = static_data.get('empresas', [])

    st.sidebar.header("Filtros")

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
    
    # Filtro de marcas
    # Checkbox para selecionar todas as marcas
    # Checkbox para selecionar todas as marcas
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

    # Filtro de empresas
    all_empresas_selected = st.sidebar.checkbox("Selecionar Todas as Empresas", value=False)

    # Expander para empresas específicas
    with st.sidebar.expander("Selecionar/Excluir Empresas Específicas", expanded=False):
        if all_empresas_selected:
            default_empresas = st.session_state.filter_options['empresas']
        else:
            default_empresas = st.session_state.get('selected_empresas', [])

        selected_empresas = st.multiselect(
            "Empresas (desmarque para excluir)",
            options=st.session_state.filter_options['empresas'],
            default=default_empresas
        )

    # Atualização do estado com as empresas selecionadas ou todas
    if all_empresas_selected:
        st.session_state.selected_empresas = st.session_state.filter_options['empresas']
    else:
        st.session_state.selected_empresas = selected_empresas


    # Botões de atualização e limpeza de cache
    if st.sidebar.button("Atualizar Dados"):
        st.session_state.data_needs_update = True
        st.rerun()

    #if st.sidebar.button("Forçar Atualização dos Dados"):
        #st.session_state.data_needs_update = True
        #st.rerun()        

    #if st.sidebar.button("Limpar Cache"):
        #for key in list(st.session_state.keys()):
            #del st.session_state[key]
        #st.rerun()

def classify_giro(giro):
    if giro > 4:  # Mais de 4 giros por ano (menos de 90 dias de cobertura)
        return 'Alto'
    elif giro > 2:  # Entre 2 e 4 giros por ano (entre 90 e 180 dias de cobertura)
        return 'Médio'
    else:  # Menos de 2 giros por ano (mais de 180 dias de cobertura)
        return 'Baixo'

def calculate_giro_and_coverage(df, dias_periodo):
    # Evitar divisão por zero e valores muito pequenos
    df['giro_anual'] = np.where(
        df['saldo_estoque'] > 0,
        ((df['quantidade_vendida']+df['quantidade_bonificada'])/ df['saldo_estoque']) * (365 / dias_periodo),
        0
    )
    # Limitar giro anual a um máximo razoável (por exemplo, 52, que seria um giro semanal)
    df['giro_anual'] = df['giro_anual'].clip(upper=52)
    
    # Calcular cobertura com um limite superior
    df['cobertura_dias'] = np.where(
        df['giro_anual'] > 0,
        np.minimum(365 / df['giro_anual'], 365 * 5),  # Limitando a 5 anos
        365 * 5  # Para itens sem giro, assumimos 5 anos de cobertura
    )
    
    return df

def identify_outliers(df, column, factor=1.5):
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - (factor * IQR)
    upper_bound = Q3 + (factor * IQR)
    return df[(df[column] < lower_bound) | (df[column] > upper_bound)]


def main():
    init_session_state()
    load_page_specific_state("Estoque_Analise")

    if 'produtos_criticos_state' not in st.session_state:
        st.session_state.produtos_criticos_state = {
            'df_display': None,
            'output': None
        }

    if not st.session_state.get('logged_in', False):
        st.warning("Por favor, faça login na página inicial para acessar esta página.")
        return

    st.title("Análise de Estoque 📦")

    # Texto explicativo
    with st.expander("Clique aqui para ver as premissas da análise"):
        st.markdown("""
                ### Regras de negócio utilizadas na análise de etoque:  
                      
                - A base de venda de referência é dos últimos 90 dias.
                - Os nops considerados em bonificação são :  
                        .BONIFICADO,  
                        .BONIFICADO STORE,  
                        .BONIFICADO FORA DO ESTADO,  
                        .REMESSA EM BONIFICAÇÃO,  
                        .BRINDE OU DOAÇÃO,  
                        .BRINDE,  
                        .CAMPANHA,  
                        .PROMOCAO   
                (*Todos estes nop tem cfop de bonificação 5.910 e 6.910*)                
                - Todos os produtos são considerados no estoque, incluive material de apoio, 
                    desde que tenham saldo maior que zero.
                """)

    try:
        progress_text = "Carregando filtros. Aguarde..."
        my_bar = st.progress(0, text=progress_text)

        load_filters()

        current_filters = (
            tuple(st.session_state.selected_channels),
            tuple(st.session_state.selected_ufs),
            tuple(st.session_state.selected_brands),
            tuple(st.session_state.selected_empresas)
        )
        
        if 'previous_filters' not in st.session_state or current_filters != st.session_state.previous_filters:
            st.session_state.data_needs_update = True
            st.session_state.previous_filters = current_filters

        if st.session_state.get('data_needs_update', True):
            my_bar.progress(50, text="Carregando dados de estoque e venda...")
        
            # Carregar dados de estoque
            with st.spinner("Carregando dados do estoque..."):
                stock_data = get_stock_data(
                    start_date_est,
                    end_date_est.strftime('%Y-%m-%d'),
                    selected_channels=st.session_state.selected_channels,
                    selected_ufs=st.session_state.selected_ufs,
                    selected_brands=st.session_state.selected_brands,
                    selected_empresas=st.session_state.selected_empresas
                )

            if stock_data.empty:
                st.warning("Não há dados de estoque disponíveis para o período e filtros selecionados.")
                return         
                       
            # Carregar dados ABC
            my_bar.progress(80, text="Carregando dados curva ABC...")
            with st.spinner("Carregando dados para análise ABC..."):
                abc_data = get_abc_curve_data_with_stock(
                    st.session_state.get('cod_colaborador'),
                    start_date_est,
                    end_date_est.strftime('%Y-%m-%d'),
                    st.session_state.get('selected_channels'),
                    st.session_state.get('selected_ufs'),
                    st.session_state.selected_brands,
                    st.session_state.get('selected_colaboradores'),
                    st.session_state.get('selected_teams'),
                    st.session_state.selected_empresas
                )

            if abc_data.empty:
                st.warning("Não há dados ABC disponíveis para o período e filtros selecionados.")
                return
            
            # Verificar se as colunas de quantidade vendida e bonificada existem
            venda_col = 'quantidade_vendida' if 'quantidade_vendida' in stock_data.columns else None
            bonificacao_col = 'quantidade_bonificada' if 'quantidade_bonificada' in stock_data.columns else None
            
            total_vendidos = abc_data[venda_col].sum() if venda_col else 0
            total_bonificados = abc_data[bonificacao_col].sum() if bonificacao_col else 0
             
            stock_data = stock_data[
                                ((stock_data['quantidade_vendida'] > 0) | (stock_data['quantidade_bonificada'] > 0)) | 
                                (stock_data['saldo_estoque'] > 0)
                                ]
            dias_periodo = 90  # Assumindo um período de 90 dias para o cálculo
            stock_data = calculate_giro_and_coverage(stock_data, dias_periodo)

            # Calcular métricas iniciais com stock_data
            total_itens_estoque = stock_data['saldo_estoque'].sum()
            valor_total_estoque = stock_data['valor_total_estoque'].sum()
            giro_medio = stock_data['giro_anual'].mean()
            total_skus = stock_data['cod_produto'].nunique()
            cobertura_media = stock_data['cobertura_dias'].median()         

            # Calcular cobertura média usando uma abordagem mais robusta
            cobertura_media = np.percentile(stock_data['cobertura_dias'], 50)  # Mediana
            
            logging.info(f"Giro médio calculado: {giro_medio}")
            logging.info(f"Cobertura média calculada: {cobertura_media}")
                        
            # Filtrar produtos com saldo_estoque > 0
            abc_data = abc_data[
                    ((abc_data['quantidade_vendida'] > 0) | (abc_data['quantidade_bonificada'] > 0)) | 
                    (abc_data['saldo_estoque'] > 0)
                    ]

            # Calcular métricas adicionais para abc_data
            abc_data = calculate_giro_and_coverage(abc_data, dias_periodo)
            
            # Classificar giro
            abc_data['classificacao_giro'] = abc_data['giro_anual'].apply(classify_giro)
           
            # Identificar outliers
            #outliers_cobertura = identify_outliers(abc_data, 'cobertura_dias')
            #outliers_giro = identify_outliers(abc_data, 'giro_anual')

            my_bar.progress(100, text="Carregamento concluído!")
            time.sleep(1)
            my_bar.empty()

            
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

            # Exibindo métricas iniciais
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(create_metric_html(
                "Total de Itens em Estoque", 
                f"{total_itens_estoque:,.0f}".replace(',', '.'),
                is_currency=False,
                line_break=False
                ), unsafe_allow_html=True)

            with col2:
                st.markdown(create_metric_html(
                "Valor Total do Estoque", 
                valor_total_estoque,
                is_currency=True,
                line_break=False
                ), unsafe_allow_html=True)    

            with col3:
                st.markdown(create_metric_html(
                "Giro Médio de Estoque (Anual)", 
                f"{giro_medio:,.2f}".replace('.', ','),    
                is_currency=False,
                line_break=False
                ), unsafe_allow_html=True) 

            with col4:
                st.markdown(create_metric_html(
                "Cobertura Média de Estoque", 
                f"{cobertura_media:,.0f}".replace(',', '.'),
                is_currency=False,
                line_break=False
                ), unsafe_allow_html=True)  

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(create_metric_html(
                "Total de SKUs", 
                f"{total_skus:,.0f}".replace(',', '.'),
                is_currency=False,
                line_break=False
                ), unsafe_allow_html=True)

            with col2:
                st.markdown(create_metric_html(
                "Total de Itens Vendidos", 
                f"{total_vendidos:,.0f}".replace(',', '.'),
                is_currency=False,
                line_break=False
                ), unsafe_allow_html=True)  

            with col3:
                st.markdown(create_metric_html(
                "Total de Itens Bonificados", 
                f"{total_bonificados:,.0f}".replace(',', '.'),
                is_currency=False,
                line_break=False
                ), unsafe_allow_html=True)    

            with col4:
                st.markdown(create_metric_html(
                "Proporção Bonificados/Vendidos", 
                f"{(total_bonificados / total_vendidos * 100):.2f}%".replace('.', ','),
                is_currency=False,
                line_break=False
                ), unsafe_allow_html=True)                                                                                    

                # Agregação dos dados por produto
                aggregated_data_aux = stock_data.groupby(['cod_produto','desc_produto','empresa','marca']).agg({
                    venda_col: 'max',
                    bonificacao_col: 'max',
                    'saldo_estoque': 'sum',
                    'valor_total_estoque': 'sum'
                }).reset_index()

                aggregated_data = aggregated_data_aux.groupby(['cod_produto','desc_produto','marca']).agg({
                    venda_col: 'sum',
                    bonificacao_col: 'sum',
                    'saldo_estoque': 'sum',
                    'valor_total_estoque': 'sum'
                }).reset_index()

                # Top 10 produtos mais vendidos e bonificados
            top_10_vendidos = aggregated_data.nlargest(20, venda_col)
            top_10_bonificados = aggregated_data.nlargest(20, bonificacao_col)
            
            # Gráfico comparativo de barras para os top 10 produtos vendidos e bonificados
            # Concatenando e eliminando duplicatas
            top_10_combined = pd.concat([top_10_vendidos, top_10_bonificados]).drop_duplicates(subset=['cod_produto'])

            # Transformando os dados para o formato 'longo' (long format)
            melted_data = pd.melt(
                top_10_combined,
                id_vars=['desc_produto', 'cod_produto', 'marca'],  # Incluindo cod_produto e marca nos identificadores
                value_vars=[venda_col, bonificacao_col],
                var_name='Tipo',
                value_name='Quantidade'
            )

            # Mapeando os tipos para 'Vendidos' e 'Bonificados'
            melted_data['Tipo'] = melted_data['Tipo'].map({venda_col: 'Vendidos', bonificacao_col: 'Bonificados'})

            # Pivotando os dados de volta para ter colunas separadas para 'Vendidos' e 'Bonificados'
            pivoted_data = melted_data.pivot_table(
                index=['cod_produto', 'desc_produto', 'marca'], 
                columns='Tipo', 
                values='Quantidade',
                fill_value=0
            ).reset_index()

            # Calculando o percentual de bonificado em relação ao vendido
            pivoted_data['Percentual Bonificado'] = (pivoted_data['Bonificados'] / pivoted_data['Vendidos']).fillna(0) * 100

            # Organizando as colunas
            pivoted_data = pivoted_data[['cod_produto', 'desc_produto', 'marca', 'Vendidos', 'Bonificados', 'Percentual Bonificado']]

            # Ordenando pela maior proporção de bonificado em relação ao vendido
            pivoted_data = pivoted_data.sort_values(by='Percentual Bonificado', ascending=False)

            # Aplicando o layout customizado no Streamlit apenas ao dataframe
            st.markdown("""
                <style>
                    .custom-dataframe-container {
                        width: 100%;
                        margin: auto;
                        overflow-x: auto;
                    }
                    .custom-dataframe {
                        font-size: 14px;
                        width: 100%;
                    }
                    .stDataFrame {
                        width: 100%;
                    }
                </style>
                """, unsafe_allow_html=True)

            # Criando a coluna central para exibir o dataframe
            st.subheader("Top 10 de proporção entre vendidos e bonificados")
            col1, col2, col3 = st.columns([1, 5, 1])  # Ajuste de largura das colunas

            with col2:  # Centralizando o dataframe
                st.markdown('<div class="custom-dataframe-container">', unsafe_allow_html=True)
                
                # Configuração do dataframe interativo
                st.dataframe(
                    pivoted_data.style.format({
                        'Vendidos': '{:,.0f}',
                        'Bonificados': '{:,.0f}',
                        'Percentual Bonificado': '{:.2f}%'
                    }),
                    hide_index=True,  # Oculta o índice do dataframe
                    use_container_width=True
                )

                st.markdown('</div>', unsafe_allow_html=True)

            # Matriz de Análise
            # Colocando a matriz de análise em um layout separado
             # CSS para alinhar à direita e controlar a largura
            st.markdown("""
                <style>
                    .right-aligned-df {
                        margin-left: auto;
                        margin-right: 0;
                        width: 80%;  /* Ajuste este valor conforme necessário */
                    }
                    .right-aligned-df .dataframe {
                        width: 100%;
                    }
                </style>
                """, unsafe_allow_html=True)
            
            st.subheader("Matriz de Análise de Estoque")
            col1, col2, col3 = st.columns([1, 3, 1])  # Ajuste de largura das colunas

            with col2:  # Centralizando o dataframe
                matriz_analise = pd.crosstab(abc_data['curva'], abc_data['classificacao_giro'])

                # Função para destacar a célula específica
                def highlight_cell(data):
                    return pd.DataFrame(
                        [
                            [
                                # Condição 1: Linha 'A' e coluna 'Baixo'
                                'background-color: yellow' if (index == 'A' and col == 'Baixo')
                                # Condição 2: Linha 'B' e coluna 'Alto'
                                else 'background-color: lightred' if (index == 'D' and col == 'Baixo')
                                else ''  # Sem destaque para outras células
                                for col in data.columns
                            ]
                            for index in data.index
                        ],
                        index=data.index,
                        columns=data.columns
                    )


                # Aplicando o estilo à matriz
                styled_matrix = matriz_analise.style.apply(highlight_cell, axis=None) \
                                                    .format(lambda x: format_brazilian(x, 0)) \
                                                    .set_table_styles([
                                                            {'selector': 'th', 'props': [('font-weight', 'bold'), ('text-align', 'center')]},
                                                            {'selector': 'td', 'props': [('text-align', 'center')]},
                                                            {'selector': 'caption', 'props': [('caption-side', 'top')]}
                                                    ]) \
                                                    .set_caption("Distribuição de produtos por Curva ABC e Classificação de Giro")

                    # Exibindo a matriz estilizada
                st.markdown("<div class='right-aligned-df'>", unsafe_allow_html=True)
                st.dataframe(styled_matrix, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # Adicionar explicação
            st.markdown("""
            **Legenda:**
            - **Curva A, B, C**: Classificação dos produtos por importância no valor estoque.
            - **Alto, Médio, Baixo**: Classificação do giro de estoque.
            - A célula destacada (A, Baixo) indica produtos com alto valor estoque, mas com baixo giro.
            """)


            # Gráfico de dispersão: Valor de Estoque vs Giro
            st.subheader("Análise de Valor de Estoque vs Giro")
            fig = px.scatter(abc_data, x='valor_estoque', y='giro_anual', color='curva',
                            hover_name='nome_produto', log_x=True, log_y=True,
                            labels={'valor_estoque': 'Valor de Estoque (log)', 'giro_anual': 'Giro Anual (log)'},
                            title='Valor de Estoque vs Giro Anual')
            st.plotly_chart(fig)


            # Produtos Críticos (Alto valor, Baixo giro)
            st.subheader("Produtos Críticos (Alto valor, Baixo giro)")
            col1, col2, col3 = st.columns([1, 7, 1])  # Ajuste de largura das colunas

            with col2:  # Centralizando o dataframe
                st.markdown('<div class="custom-dataframe-container">', unsafe_allow_html=True)
                produtos_criticos = abc_data[(abc_data['curva'] == 'A') & (abc_data['classificacao_giro'] == 'Baixo')]
                numeric_columns = ['valor_estoque', 'saldo_estoque', 'giro_anual', 'cobertura_dias', 'quantidade_vendida', 'quantidade_bonificada']
                
                # Criar o DataFrame formatado para exibição
            df_display = produtos_criticos[['sku', 'nome_produto', 'marca'] + numeric_columns].sort_values('valor_estoque', ascending=False)
            st.session_state.produtos_criticos_state['df_display'] = df_display

                # Exibir o DataFrame
            st.dataframe(
                    df_display.style.format({
                        'valor_estoque': lambda x: f"R$ {format_brazilian(x, 2)}",
                        'saldo_estoque': lambda x: format_brazilian(x, 0),
                        'giro_anual': lambda x: format_brazilian(x, 2),
                        'cobertura_dias': lambda x: format_brazilian(x, 0),
                        'quantidade_vendida': lambda x: format_brazilian(x, 0),
                        'quantidade_bonificada': lambda x: format_brazilian(x, 0)
                    })
                    .apply(lambda x: highlight_max(x, props='background-color: #FFCCCB;'), subset=numeric_columns)
                    .set_table_styles([
                        {'selector': 'th', 'props': [('font-weight', 'bold'), ('text-align', 'center')]},
                        {'selector': 'td', 'props': [('text-align', 'center')]}
                    ]),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "saldo_estoque": st.column_config.NumberColumn("Saldo Estoque", format="%d"),
                        "valor_estoque": st.column_config.NumberColumn("Valor Estoque", format="R$ %s"),
                        "giro_anual": st.column_config.NumberColumn("Giro Anual", format="%s"),
                        "cobertura_dias": st.column_config.NumberColumn("Cobertura (dias)", format="%d"),
                        "quantidade_vendida": st.column_config.NumberColumn("Qtd. Vendida", format="%d"),
                        "quantidade_bonificada": st.column_config.NumberColumn("Qtd. Bonificada", format="%d")
                    }
                )
            st.markdown('</div>', unsafe_allow_html=True)

                # Preparar o Excel para download
            def generate_excel_report(df_display):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    # Aba principal com todos os produtos críticos
                    df_display.to_excel(writer, sheet_name='Todos Produtos Críticos', index=False)
                    
                    # Configurando a primeira aba
                    worksheet = writer.sheets['Todos Produtos Críticos']
                    workbook = writer.book
                    
                    # Criando formatos diferentes para valores monetários e quantidades
                    formato_monetario = workbook.add_format({'num_format': '#.##0,00'})  # Duas casas decimais
                    formato_inteiro = workbook.add_format({'num_format': '#.##0'})       # Zero casas decimais
                    formato_giro = workbook.add_format({'num_format': '#.##0,00'})       # Duas casas decimais para giro
                    
                    # Ajustando larguras e formatação
                    for idx, col in enumerate(df_display.columns):
                        max_length = max(df_display[col].astype(str).apply(len).max(), len(col))
                        worksheet.set_column(idx, idx, max_length + 2)
                        
                        if col == 'valor_estoque':
                            worksheet.set_column(idx, idx, None, formato_monetario)
                        elif col in ['saldo_estoque', 'cobertura_dias', 'quantidade_vendida', 'quantidade_bonificada']:
                            worksheet.set_column(idx, idx, None, formato_inteiro)
                        elif col == 'giro_anual':
                            worksheet.set_column(idx, idx, None, formato_giro)
                    
                    # Criando abas por marca
                    marcas = df_display['marca'].unique()
                    for marca in marcas:
                        df_marca = df_display[df_display['marca'] == marca]
                        sheet_name = f'Produtos {marca}'
                        df_marca.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        worksheet_marca = writer.sheets[sheet_name]
                        
                        for idx, col in enumerate(df_marca.columns):
                            max_length = max(df_marca[col].astype(str).apply(len).max(), len(col))
                            worksheet_marca.set_column(idx, idx, max_length + 2)
                            
                            if col == 'valor_estoque':
                                worksheet_marca.set_column(idx, idx, None, formato_monetario)
                            elif col in ['saldo_estoque', 'cobertura_dias', 'quantidade_vendida', 'quantidade_bonificada']:
                                worksheet_marca.set_column(idx, idx, None, formato_inteiro)
                            elif col == 'giro_anual':
                                worksheet_marca.set_column(idx, idx, None, formato_giro)

                return output.getvalue()

            # E então no seu código principal:
            #if st.button('Gerar Relatório Excel'):
                #excel_data = generate_excel_report(df_display)
                #st.download_button(
                    #label="📥 Baixar tabela em Excel",
                    #data=excel_data,
                    #file_name="produtos_criticos.xlsx",
                    #mime="application/vnd.ms-excel"
               # )



            st.markdown("Resumo dos Produtos Críticos")

            # Cálculo das métricas
            total_produtos_criticos = len(produtos_criticos)
            total_valor_estoque_criticos = produtos_criticos['valor_estoque'].sum()
            cobertura_media_criticos = produtos_criticos['cobertura_dias'].mean()

            # Criando colunas para as métricas
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    label="Total de Produtos Críticos",
                    value=f"{total_produtos_criticos}",
                    delta=f"{total_produtos_criticos/len(abc_data)*100:.1f}% do total",
                    delta_color="off"
                )

            with col2:
                st.metric(
                    label="Valor Total de Estoque Crítico",
                    value=f"R$ {format_brazilian(total_valor_estoque_criticos, 2)}",
                    delta=f"{total_valor_estoque_criticos/abc_data['valor_estoque'].sum()*100:.1f}% do estoque total",
                    delta_color="off"
                )

            with col3:
                st.metric(
                    label="Cobertura Média dos Críticos",
                    value=f"{cobertura_media_criticos:.0f} dias",
                    #delta=f"{cobertura_media_criticos - abc_data['cobertura_dias'].median():.0f} dias vs média geral",
                    delta_color="inverse"
                )

            # Adicionar uma explicação ou dica
            st.info("""
            💡 **Dica:** Produtos críticos são itens de alto valor no estoque (Curva A) com baixo giro. 
            Eles representam uma oportunidade significativa para otimização do estoque e melhoria do fluxo de caixa.
            """)

            # Exibir outliers
            st.subheader("Produtos com baixo Estoque (Cobertura < 90 dias)")
            col1, col2, col3 = st.columns([1, 5, 1])  # Ajuste de largura das colunas
            with col2:
                    st.markdown('<div class="custom-dataframe-container">', unsafe_allow_html=True)
                    excess_stock_menor = abc_data[abc_data['cobertura_dias'] < 90].sort_values('cobertura_dias', ascending=False)
                    st.dataframe(
                        excess_stock_menor[['sku', 'nome_produto', 'marca', 'saldo_estoque', 'valor_estoque', 'giro_anual', 'cobertura_dias','quantidade_vendida']]
                        .style.format({
                            'saldo_estoque': '{:,.0f}',
                            'valor_estoque': 'R$ {:,.2f}',
                            'giro_anual': '{:.2f}',
                            'cobertura_dias': '{:.0f}',
                            'quantidade_vendida': '{:.0f}'
                        }),
                        hide_index=True,
                        use_container_width=True
                    )    
                    st.markdown('</div>', unsafe_allow_html=True)       



            # Produtos com Excesso de Estoque
            st.subheader("Produtos com Excesso de Estoque (Cobertura > 90 dias)")
            col1, col2, col3 = st.columns([1, 5, 1])  # Ajuste de largura das colunas
            with col2:
                    st.markdown('<div class="custom-dataframe-container">', unsafe_allow_html=True)
                    excess_stock_maior = abc_data[abc_data['cobertura_dias'] > 90].sort_values('cobertura_dias', ascending=False)
                    st.dataframe(
                        excess_stock_maior[['sku', 'nome_produto', 'marca', 'saldo_estoque', 'valor_estoque', 'giro_anual', 'cobertura_dias','quantidade_vendida']]
                        .style.format({
                            'saldo_estoque': '{:,.0f}',
                            'valor_estoque': 'R$ {:,.2f}',
                            'giro_anual': '{:.2f}',
                            'cobertura_dias': '{:.0f}',
                            'quantidade_vendida': '{:.0f}'
                        }),
                        hide_index=True,
                        use_container_width=True
                    )
                    st.markdown('</div>', unsafe_allow_html=True) 

            # Identificar produtos sem vendas
            # Passo 1: Agrupamento e agregação dos dados
            produtos_agrupados_aux = stock_data.groupby(['cod_produto','empresa']).agg({
                'desc_produto': 'first',
                'marca': 'first',
                'saldo_estoque': 'sum',
                'valor_total_estoque': 'sum',
                'quantidade_vendida': 'max',
                'quantidade_bonificada': 'max'
                }).reset_index()
            
            produtos_agrupados = produtos_agrupados_aux.groupby('cod_produto').agg({
                'desc_produto': 'first',
                'marca': 'first',
                'saldo_estoque': 'sum',
                'valor_total_estoque': 'sum',
                'quantidade_vendida': 'sum',
                'quantidade_bonificada': 'sum'
                }).reset_index()

            # Passo 2: Filtragem para remover produtos com somatório de quantidade_vendida igual a zero
            produtos_sem_vendas = produtos_agrupados[(produtos_agrupados['quantidade_vendida'] == 0) & (produtos_agrupados['saldo_estoque'] > 0)]
         
            logging.info(f"Número de produtos sem vendas após agregação: {len(produtos_sem_vendas)}")

            colunas_display = ['cod_produto', 'desc_produto', 'marca', 'saldo_estoque', 'valor_total_estoque', 'quantidade_vendida','quantidade_bonificada']
            colunas_disponiveis = [col for col in colunas_display if col in produtos_sem_vendas.columns]

            if len(colunas_disponiveis) < len(colunas_display):
                colunas_faltantes = set(colunas_display) - set(colunas_disponiveis)
                logging.warning(f"Colunas faltantes: {colunas_faltantes}")
                st.warning(f"Algumas colunas estão faltando nos dados: {', '.join(colunas_faltantes)}")

            # Verificar se temos as colunas mínimas necessárias
            if len(colunas_disponiveis) < 3:
                st.error("Dados insuficientes para exibir produtos sem vendas.")
                return                                            

            # Adicionar seção de análise de produtos sem vendas
            st.subheader("Análise de Produtos Sem Vendas no Período")

            # Métricas gerais sobre produtos sem vendas
            col1, col2, col3 = st.columns(3)
            col1.metric("Quantidade de Produtos Sem Vendas", f"{len(produtos_sem_vendas):,}")
            col2.metric("% do Total de SKUs", f"{(len(produtos_sem_vendas) / len(produtos_agrupados) * 100):.2f}%")
            col3.metric("Valor Total em Estoque (Sem Vendas)", f"R$ {produtos_sem_vendas['valor_total_estoque'].sum():,.2f}")

            # Gráfico de barras das top 10 marcas com mais produtos sem vendas
            # Gráfico de barras das top 10 marcas com mais produtos sem vendas
            top_marcas_sem_vendas = produtos_sem_vendas['marca'].value_counts().nlargest(10)
            # Converter a Series para DataFrame
            df_marcas_sem_vendas = pd.DataFrame({
                'Marca': top_marcas_sem_vendas.index,
                'Quantidade': top_marcas_sem_vendas.values
            })

            fig_marcas = px.bar(
                df_marcas_sem_vendas,
                x='Marca',
                y='Quantidade',
                title='Top 10 Marcas com Mais Produtos Sem Vendas',
                text='Quantidade'  # Mostra os valores nas barras
            )

            # Remover o eixo vertical (y-axis)
            fig_marcas.update_layout(
                yaxis=dict(visible=False),  # Oculta o eixo y
            )

            #st.plotly_chart(fig_marcas)
            
            # Exibir tabela de produtos sem vendas
            st.subheader("Detalhes dos Produtos Sem Vendas")
            col1, col2, col3 = st.columns([1, 5, 1])  # Ajuste de largura das colunas
            with col2:
                    st.markdown('<div class="custom-dataframe-container">', unsafe_allow_html=True)
                    st.dataframe(
                        produtos_sem_vendas[colunas_disponiveis].set_index('cod_produto')
                        .sort_values('valor_total_estoque', ascending=False)
                        .style.format({
                            'saldo_estoque': '{:,.0f}',
                            'valor_total_estoque': 'R$ {:,.2f}',
                            'quantidade_vendida': '{:,.0f}',
                            'quantidade_bonificada': '{:,.0f}'
                        }),
                        height=400,
                        use_container_width=True
                    ) 
                    st.markdown('</div>', unsafe_allow_html=True) 

            st.subheader("Resumo do Estoque por Marca")
            col1, col2, col3 = st.columns([1, 5, 1])  # Ajuste de largura das colunas

            with col2:
                st.markdown('<div class="custom-dataframe-container">', unsafe_allow_html=True)
                
                # Passo 1: Agrupamento inicial
                resumo_marca = abc_data.groupby('marca').agg({
                    'valor_estoque': 'sum',
                    'saldo_estoque': 'sum',
                    'giro_anual': 'mean',
                    'cobertura_dias': 'median',
                    'quantidade_vendida': 'sum',
                    'quantidade_bonificada': 'sum'
                }).reset_index()

                # Passo 2: Cálculo do share de participação baseado no 'valor_estoque'
                total_valor_estoque = resumo_marca['valor_estoque'].sum()

                # Adicionando coluna com o share de participação no valor_estoque
                resumo_marca['share_valor_estoque'] = (resumo_marca['valor_estoque'] / total_valor_estoque) 

                # Passo 3: Ordenar pelo 'valor_estoque' e formatar os dados
                resumo_marca = resumo_marca.sort_values('valor_estoque', ascending=False)

                # Exibindo o DataFrame com formatação
                st.dataframe(
                    resumo_marca.style.format({
                        'valor_estoque': 'R$ {:,.2f}',
                        'share_valor_estoque': '{:.2f}%' , # Formatação do share de valor_estoque
                        'saldo_estoque': '{:,.0f}',
                        'giro_anual': '{:.2f}',
                        'cobertura_dias': '{:.0f}',
                        'quantidade_vendida': '{:,.0f}',
                        'quantidade_bonificada': '{:,.0f}',
                        
                    }),
                    column_config={
                        "share_valor_estoque": st.column_config.ProgressColumn("Share Estoque", min_value=0, max_value=1)
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                st.markdown('</div>', unsafe_allow_html=True)



            # Resumo por Empresa
            st.subheader("Resumo do Estoque por Empresa")
            col1, col2, col3 = st.columns([1, 5, 1])  # Ajuste de largura das colunas
            with col2:
                    st.markdown('<div class="custom-dataframe-container">', unsafe_allow_html=True)
                    resumo_empresa = stock_data.groupby(['empresa', 'uf_empresa']).agg({
                        'valor_total_estoque': 'sum',
                        'saldo_estoque': 'sum',
                        'giro_anual': 'mean',
                        'cobertura_dias': 'median'
                    }).reset_index().sort_values('valor_total_estoque', ascending=False)
                    
                    st.dataframe(
                        resumo_empresa.style.format({
                            'valor_total_estoque': 'R$ {:,.2f}',
                            'saldo_estoque': '{:,.0f}',
                            'giro_anual': '{:.2f}',
                            'cobertura_dias': '{:.0f}'
                        }),
                        hide_index=True,
                        use_container_width=True
                    )
                    st.markdown('</div>', unsafe_allow_html=True) 

            st.session_state.data_needs_update = False

    except Exception as e:
        st.error(f"Ocorreu um erro: {str(e)}")
        logging.error(f"Erro detalhado: {traceback.format_exc()}")
        st.error(traceback.format_exc())

if __name__ == "__main__":
    main()