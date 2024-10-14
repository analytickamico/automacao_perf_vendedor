import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils import get_stock_data, get_abc_curve_data_with_stock, get_static_data
from session_state_manager import init_session_state, load_page_specific_state
import traceback
import logging
import numpy as np
from datetime import datetime, timedelta
import time

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Análise de Estoque", page_icon="📦", layout="wide")

end_date_est = datetime.now() - timedelta(days=1)
start_date_est = (end_date_est - timedelta(days=90)).strftime('%Y-%m-%d')

def initialize_session_state():
    if 'filter_options' not in st.session_state:
        st.session_state.filter_options = {
            'channels': [],
            'ufs': [],
            'brands': []
        }
    if 'selected_channels' not in st.session_state:
        st.session_state.selected_channels = []
    if 'selected_ufs' not in st.session_state:
        st.session_state.selected_ufs = []
    if 'selected_brands' not in st.session_state:
        st.session_state.selected_brands = []
    #if 'selected_teams' not in st.session_state:
        #st.session_state.selected_teams = []
    #if 'selected_colaboradores' not in st.session_state:
        #st.session_state.selected_colaboradores = []

def load_filters():
    logging.info("Iniciando load_filters")
    initialize_session_state()

    user = st.session_state['user']
    user_role = user.get('role')
    logging.info(f"Papel do usuário: {user_role}")

    static_data = get_static_data()
    logging.info(f"Dados estáticos obtidos: {static_data.keys()}")
    
    st.session_state.filter_options['channels'] = static_data.get('canais_venda', [])
    st.session_state.filter_options['ufs'] = static_data.get('ufs', [])
    st.session_state.filter_options['brands'] = static_data.get('marcas', [])
    #st.session_state.filter_options['equipes'] = static_data.get('equipes', [])
    #st.session_state.filter_options['colaboradores'] = static_data.get('colaboradores', [])

    st.sidebar.header("Filtros")
    
    st.session_state.selected_brands = st.sidebar.multiselect(
        "Marcas", 
        options=st.session_state.filter_options['brands'],
        default=st.session_state.get('selected_brands', [])
    )

    #if user_role in ['admin', 'gestor']:
        #st.session_state.selected_teams = st.sidebar.multiselect(
            #"Equipes", 
            #options=st.session_state.filter_options['equipes'],
            #default=st.session_state.get('selected_teams', [])
        #)
        
        #st.session_state['cod_colaborador'] = st.sidebar.text_input("Código do Colaborador (deixe em branco para todos)", st.session_state.get('cod_colaborador', ''))
        
        #st.session_state.selected_colaboradores = st.sidebar.multiselect(
            #"Colaboradores", 
            #options=st.session_state.filter_options['colaboradores'],
            #default=st.session_state.get('selected_colaboradores', [])
        #)
    #elif user_role == 'vendedor':
        #st.sidebar.info(f"Código do Colaborador: {st.session_state.get('cod_colaborador', '')}")

    if st.sidebar.button("Atualizar Dados"):
        st.session_state.data_needs_update = True
        st.rerun()

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
        (df['quantidade_vendida'] / df['saldo_estoque']) * (365 / dias_periodo),
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
    if not st.session_state.get('logged_in', False):
        st.warning("Por favor, faça login na página inicial para acessar esta página.")
        return

    st.title("Análise de Estoque 📦")
    with st.expander("Clique para ver as regras de negócio utilizadas"):
                st.markdown("""
                ### Regras utilizadas para análise de estoque:
                - O período de vendas dos produtos é dos últimos 90 dias até (d-1).
                - Curva ABC de valor de estoque:
                    A: 80% do valor total do estoque
                    B: 15% do valor total do estoque
                    C: 5% do valor total do estoque
                - Giro de Estoque:
                    Alto: Menos de 90 dias de cobertura
                    Médio: Entre 90 e 180 dias de cobertura
                    Baixo: Mais de 180 dias de cobertura                
                """)

    try:
        progress_text = "Carregando filtros. Aguarde..."
        my_bar = st.progress(0, text=progress_text)

        load_filters()

        if st.session_state.get('data_needs_update', True):
            my_bar.progress(50, text="Carregando dados de estoque e venda...")
        
            # Carregar dados de estoque
            with st.spinner("Carregando dados do estoque..."):
                stock_data = get_stock_data(
                    start_date_est,
                    end_date_est.strftime('%Y-%m-%d'),
                    selected_channels=st.session_state.selected_channels,
                    selected_ufs=st.session_state.selected_ufs,
                    selected_brands=st.session_state.selected_brands
                )

            if stock_data.empty:
                st.warning("Não há dados de estoque disponíveis para o período e filtros selecionados.")
                return
            
            # Aplicar filtro de marca aos dados de estoque
            if st.session_state.selected_brands:
                stock_data = stock_data[stock_data['marca'].isin(st.session_state.selected_brands)]
            


            dias_periodo = 90  # Assumindo um período de 90 dias para o cálculo
            stock_data = calculate_giro_and_coverage(stock_data, dias_periodo)

            # Calcular métricas iniciais com stock_data
            total_itens_estoque = stock_data['saldo_estoque'].sum()
            valor_total_estoque = stock_data['valor_total_estoque'].sum()
            giro_medio = stock_data['giro_anual'].mean()
            
            # Calcular cobertura média usando uma abordagem mais robusta
            cobertura_media = np.percentile(stock_data['cobertura_dias'], 50)  # Mediana
            
            logging.info(f"Giro médio calculado: {giro_medio}")
            logging.info(f"Cobertura média calculada: {cobertura_media}")
            
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
                    st.session_state.get('selected_teams')
                )

            if abc_data.empty:
                st.warning("Não há dados ABC disponíveis para o período e filtros selecionados.")
                return

            # Calcular métricas adicionais para abc_data
            abc_data = calculate_giro_and_coverage(abc_data, dias_periodo)
            
            # Classificar giro
            abc_data['classificacao_giro'] = abc_data['giro_anual'].apply(classify_giro)

            # Filtrar produtos com saldo_estoque > 0
            abc_data = abc_data[abc_data['saldo_estoque'] > 0]

            # Identificar outliers
            outliers_cobertura = identify_outliers(abc_data, 'cobertura_dias')
            outliers_giro = identify_outliers(abc_data, 'giro_anual')

            # Criar dataset sem outliers
            abc_data_sem_outliers = abc_data[~abc_data.index.isin(outliers_cobertura.index) & ~abc_data.index.isin(outliers_giro.index)]

            # Calcular métricas sem outliers
            giro_medio_sem_outliers = abc_data_sem_outliers['giro_anual'].mean()
            cobertura_media_sem_outliers = abc_data_sem_outliers['cobertura_dias'].median()

            my_bar.progress(100, text="Carregamento concluído!")
            time.sleep(1)
            my_bar.empty()

            st.session_state.data_needs_update = False

            # Exibindo métricas iniciais
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total de Itens em Estoque", f"{total_itens_estoque:,.0f}")
            col2.metric("Valor Total do Estoque", f"R$ {valor_total_estoque:,.2f}")
            col3.metric("Giro Médio de Estoque (Anual)", f"{giro_medio:.2f}")
            col4.metric("Cobertura Média de Estoque", f"{cobertura_media:.0f} dias")

            # Matriz de Análise
            st.subheader("Matriz de Análise de Estoque")
            matriz_analise = pd.crosstab(abc_data['curva'], abc_data['classificacao_giro'])
            st.write(matriz_analise)

            # Gráfico de dispersão: Valor de Estoque vs Giro
            st.subheader("Análise de Valor de Estoque vs Giro")
            fig = px.scatter(abc_data, x='valor_estoque', y='giro_anual', color='curva',
                            hover_name='nome_produto', log_x=True, log_y=True,
                            labels={'valor_estoque': 'Valor de Estoque (log)', 'giro_anual': 'Giro Anual (log)'},
                            title='Valor de Estoque vs Giro Anual')
            st.plotly_chart(fig)

            # Produtos Críticos (Alto valor, Baixo giro)
            st.subheader("Produtos Críticos (Alto valor, Baixo giro)")
            produtos_criticos = abc_data[(abc_data['curva'] == 'A') & (abc_data['classificacao_giro'] == 'Baixo')]
            st.dataframe(
                produtos_criticos[['sku', 'nome_produto', 'marca', 'valor_estoque', 'saldo_estoque', 'giro_anual', 'cobertura_dias','quantidade_vendida']]
                .sort_values('valor_estoque', ascending=False)
                .style.format({
                    'valor_estoque': 'R$ {:,.2f}',
                    'saldo_estoque': '{:.0f}',
                    'giro_anual': '{:.2f}',
                    'cobertura_dias': '{:.0f}',
                    'quantidade_vendida': '{:.0f}'
                }),
                hide_index=True
            )

            # Totais dos Produtos Críticos
            total_produtos_criticos = len(produtos_criticos)
            total_valor_estoque_criticos = produtos_criticos['valor_estoque'].sum()
            cobertura_media_criticos = produtos_criticos['cobertura_dias'].mean()

            st.write(f"Total de Produtos Críticos: {total_produtos_criticos}")
            st.write(f"Valor Total de Estoque dos Produtos Críticos: R$ {total_valor_estoque_criticos:,.2f}")
            st.write(f"Cobertura Média dos Produtos Críticos: {cobertura_media_criticos:.0f} dias")

            # Exibir outliers
            st.subheader("Maiores Cobertura de Estoque")
            if not outliers_cobertura.empty:
                st.dataframe(
                    outliers_cobertura[['sku', 'nome_produto', 'marca', 'valor_estoque', 'saldo_estoque', 'giro_anual', 'cobertura_dias']]
                    .sort_values('cobertura_dias', ascending=False)
                    .style.format({
                        'valor_estoque': 'R$ {:,.2f}',
                        'saldo_estoque': '{:.0f}',
                        'giro_anual': '{:.2f}',
                        'cobertura_dias': '{:.0f}'
                    }),
                    hide_index=True
                )
            else:
                st.write("Nenhum outlier de cobertura identificado.")

            st.subheader("Menores Coberturas Estoque")
            if not outliers_giro.empty:
                st.dataframe(
                    outliers_giro[['sku', 'nome_produto', 'marca', 'valor_estoque', 'saldo_estoque', 'giro_anual', 'cobertura_dias']]
                    .sort_values('giro_anual', ascending=False)
                    .style.format({
                        'valor_estoque': 'R$ {:,.2f}',
                        'saldo_estoque': '{:.0f}',
                        'giro_anual': '{:.2f}',
                        'cobertura_dias': '{:.0f}'
                    }),
                    hide_index=True
                )
            else:
                st.write("Nenhum outlier de giro identificado.")

            



            # Produtos com Excesso de Estoque
            st.subheader("Produtos com Excesso de Estoque (Cobertura > 90 dias)")
            excess_stock = abc_data[abc_data['cobertura_dias'] > 90].sort_values('cobertura_dias', ascending=False)
            st.dataframe(
                excess_stock[['sku', 'nome_produto', 'marca', 'saldo_estoque', 'valor_estoque', 'giro_anual', 'cobertura_dias']]
                .style.format({
                    'saldo_estoque': '{:,.0f}',
                    'valor_estoque': 'R$ {:,.2f}',
                    'giro_anual': '{:.2f}',
                    'cobertura_dias': '{:.0f}'
                }),
                hide_index=True
            )

            # Resumo por Marca
            st.subheader("Resumo do Estoque por Marca")
            resumo_marca = abc_data.groupby('marca').agg({
                'valor_estoque': 'sum',
                'saldo_estoque': 'sum',
                'giro_anual': 'mean',
                'cobertura_dias': 'median'
            }).reset_index().sort_values('valor_estoque', ascending=False)
            
            st.dataframe(
                resumo_marca.style.format({
                    'valor_estoque': 'R$ {:,.2f}',
                    'saldo_estoque': '{:,.0f}',
                    'giro_anual': '{:.2f}',
                    'cobertura_dias': '{:.0f}'
                }),
                hide_index=True
            )

            # Resumo por Empresa
            st.subheader("Resumo do Estoque por Empresa")
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
                hide_index=True
            )

    except Exception as e:
        st.error(f"Ocorreu um erro: {str(e)}")
        logging.error(f"Erro detalhado: {traceback.format_exc()}")
        st.error(traceback.format_exc())

if __name__ == "__main__":
    main()