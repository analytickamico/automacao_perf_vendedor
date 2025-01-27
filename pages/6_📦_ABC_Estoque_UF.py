import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (
    get_abc_curve_data,
    get_stock_data,
    get_static_data,
    create_metric_html,
    format_currency
)
from session_state_manager import init_session_state, load_page_specific_state
import logging
from io import BytesIO
import numpy as np
from datetime import datetime, timedelta
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Page config
st.set_page_config(page_title="ABC Regional - Estoque", page_icon="📊", layout="wide")

def initialize_filters():
    """Initialize session state filters"""
    if 'filter_options' not in st.session_state:
        st.session_state.filter_options = {
            'channels': [],
            'ufs': [],
            'brands': [],
            'empresas': []
        }
    if 'static_data' not in st.session_state:
        st.session_state.static_data = get_static_data()
        
    # Inicializar variáveis de dados
    if 'abc_data' not in st.session_state:
        st.session_state.abc_data = pd.DataFrame()
    if 'data_with_sales' not in st.session_state:
        st.session_state.data_with_sales = pd.DataFrame()
    if 'data_without_sales' not in st.session_state:
        st.session_state.data_without_sales = pd.DataFrame()

    # Inicializar variáveis de seleção
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

    # Inicializar datas
    if 'end_date' not in st.session_state:
        st.session_state.end_date = datetime.now() - timedelta(days=1)
    if 'start_date' not in st.session_state:
        st.session_state.start_date = st.session_state.end_date - timedelta(days=90)

def load_filters():
    """Load and display filters in sidebar"""
    initialize_filters()
    
    static_data = st.session_state.static_data
    
    st.sidebar.title('Filtros')
    
    # Date filters - Corrigindo a manipulação do state
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=90)
    
    # Calcular start_date baseado no end_date selecionado
    st.session_state['start_date'] = st.sidebar.date_input(
        "Data Inicial",
        value=st.session_state['end_date'] - timedelta(days=90),
        key='start_date_input'
    )

    st.session_state['end_date'] = st.sidebar.date_input(
        "Data Final",
        value=end_date,
        key='end_date_input'
    )
    
    
    
    # Channel filter
    st.session_state.selected_channels = st.sidebar.multiselect(
        "Canais de Venda",
        options=static_data.get('canais_venda', []),
        default=st.session_state.get('selected_channels', [])
    )
    
    # UF filter
    st.session_state.selected_ufs = st.sidebar.multiselect(
        "UFs",
        options=static_data.get('ufs', []),
        default=st.session_state.get('selected_ufs', [])
    )
    
    # Brand filter with "Select All" option
# Brand filter with "Select All" option
    all_brands_selected = st.sidebar.checkbox("Selecionar Todas as Marcas", value=False)

    with st.sidebar.expander("Selecionar/Excluir Marcas Específicas", expanded=False):
        # Filtrar valores None e tratar lista de marcas
        available_brands = [brand for brand in static_data.get('marcas', []) if brand is not None]
        
        if all_brands_selected:
            default_brands = available_brands
        else:
            default_brands = st.session_state.get('selected_brands', [])
            
        selected_brands = st.multiselect(
            "Marcas",
            options=available_brands,  # Usando a lista filtrada
            default=default_brands
        )

    st.session_state.selected_brands = selected_brands if not all_brands_selected else available_brands

def merge_abc_with_stock(abc_data, stock_data):
    """Merge ABC curve data with stock data"""
    # Log inicial
    logging.info(f"Faturamento antes do merge: {abc_data['faturamento_liquido'].sum()}")
    
    # Ensure we're using uppercase SKUs for joining
    abc_data['sku'] = abc_data['sku'].str.upper()
    stock_data['cod_produto'] = stock_data['cod_produto'].str.upper()
    
    # Primeiro criar uma cópia dos dados ABC para preservar os valores originais
    base_data = abc_data.copy()
    
    # Agregar dados de estoque por SKU e UF
    stock_agg = stock_data.groupby(['cod_produto', 'uf_empresa', 'empresa']).agg({
        'saldo_estoque': 'sum',
        'custo_total': 'mean'
    }).reset_index()
    
    # Fazer o merge
    merged_data = pd.merge(
        base_data,
        stock_agg,
        left_on=['sku'],
        right_on=['cod_produto'],
        how='left'
    )
    
    # Distribuir o faturamento proporcionalmente entre as UFs
    if 'cod_produto' in merged_data.columns:
        n_ufs = merged_data.groupby('sku')['uf_empresa'].transform('count')
        merged_data['faturamento_liquido'] = merged_data['faturamento_liquido'] / n_ufs
        merged_data['quantidade_vendida'] = merged_data['quantidade_vendida'] / n_ufs
    
    # Calculate stock value
    merged_data['valor_estoque'] = merged_data['saldo_estoque'] * merged_data['custo_total']
    
    # Remover colunas desnecessárias
    if 'cod_produto' in merged_data.columns:
        merged_data = merged_data.drop('cod_produto', axis=1)
    
    # Garantir que todas as colunas necessárias existam e estejam nomeadas corretamente
    required_columns = ['sku', 'nome_produto', 'marca', 'uf_empresa', 'empresa', 'curva',
                       'faturamento_liquido', 'quantidade_vendida', 'saldo_estoque', 'valor_estoque']
    
    for col in required_columns:
        if col not in merged_data.columns:
            merged_data[col] = 'N/A'
    
    # Verificação do faturamento total
    total_fat_original = abc_data['faturamento_liquido'].sum()
    total_fat_final = merged_data['faturamento_liquido'].sum()
    
    logging.info(f"Faturamento original: {total_fat_original}")
    logging.info(f"Faturamento após merge e distribuição: {total_fat_final}")
    if abs(total_fat_original - total_fat_final) > 0.01:  # Tolerância de 1 centavo
        logging.warning("Diferença significativa no faturamento após o merge!")
    
    # Log após merge
    logging.info(f"Colunas após merge: {merged_data.columns.tolist()}")
    duplicates = merged_data[merged_data.duplicated(['sku', 'uf_empresa'], keep=False)]
    if not duplicates.empty:
        logging.warning(f"Encontradas {len(duplicates)} linhas duplicadas após o merge (por SKU e UF)")
    
    return merged_data

def generate_excel_report(data_with_sales=None, data_without_sales=None):
    """Generate Excel report with optional data for products with sales and without sales."""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1
        })
        number_format = workbook.add_format({'num_format': '#,##0'})
        currency_format = workbook.add_format({'num_format': 'R$ #,##0.00'})
        decimal_format = workbook.add_format({'num_format': '#,##0.00'})
        
        # Criar Resumo ABC se houver dados de produtos com venda
        if data_with_sales is not None:
            # Calculando o giro de estoque por produto
            days_period = (st.session_state['end_date'] - st.session_state['start_date']).days
            data_with_sales = data_with_sales.copy()
            data_with_sales['venda_media_diaria'] = (
                data_with_sales['quantidade_vendida'] + 
                data_with_sales['quantidade_bonificada']
            ) / days_period
            
            data_with_sales['giro_estoque'] = np.where(
                data_with_sales['venda_media_diaria'] == 0,
                0,
                data_with_sales['saldo_estoque'] / data_with_sales['venda_media_diaria']
            )
            
            summary_df = data_with_sales.groupby(['curva', 'marca', 'uf_empresa']).agg({
                'faturamento_liquido': 'sum',
                'saldo_estoque': 'sum',
                'valor_estoque': 'sum',
                'giro_estoque': 'mean'  # Média do giro de estoque por grupo
            }).reset_index()
            
            summary_df.to_excel(writer, sheet_name='Resumo ABC', index=False)
            worksheet = writer.sheets['Resumo ABC']
            
            # Formatar aba de resumo
            for idx, col in enumerate(summary_df.columns):
                worksheet.write(0, idx, col, header_format)
                if col in ['faturamento_liquido', 'valor_estoque']:
                    worksheet.set_column(idx, idx, 15, currency_format)
                elif col in ['saldo_estoque']:
                    worksheet.set_column(idx, idx, 12, number_format)
                elif col == 'giro_estoque':
                    worksheet.set_column(idx, idx, 12, decimal_format)
        
        # Produtos com venda
        if data_with_sales is not None:
            sheet_name = 'Produtos com Venda'
            export_cols = [
                'sku', 'nome_produto', 'marca', 'uf_empresa', 'empresa', 'curva',
                'faturamento_liquido', 'quantidade_vendida', 'quantidade_bonificada',
                'saldo_estoque', 'valor_estoque', 'giro_estoque'
            ]
            
            data_with_sales[export_cols].to_excel(
                writer, 
                sheet_name=sheet_name, 
                index=False
            )
            
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(export_cols):
                worksheet.write(0, idx, col, header_format)
                if 'valor' in col.lower() or 'faturamento' in col.lower():
                    worksheet.set_column(idx, idx, 15, currency_format)
                elif 'quantidade' in col.lower() or 'saldo' in col.lower():
                    worksheet.set_column(idx, idx, 12, number_format)
                elif col == 'giro_estoque':
                    worksheet.set_column(idx, idx, 12, decimal_format)
                else:
                    worksheet.set_column(idx, idx, 15)
        
        # Produtos sem venda
        if data_without_sales is not None:
            sheet_name = 'Produtos sem Venda'
            export_cols_no_sales = [
                'sku', 'nome_produto', 'marca', 'uf_empresa', 'empresa',
                'saldo_estoque', 'valor_total_estoque'
            ]

            data_without_sales = data_without_sales.rename(columns={
                'cod_produto': 'sku',
                'desc_produto': 'nome_produto',
                'valor_estoque': 'valor_total_estoque'
            })
            
            data_without_sales[export_cols_no_sales].to_excel(
                writer, 
                sheet_name=sheet_name, 
                index=False
            )
            
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(export_cols_no_sales):
                worksheet.write(0, idx, col, header_format)
                if 'valor' in col.lower():
                    worksheet.set_column(idx, idx, 15, currency_format)
                elif 'saldo' in col.lower():
                    worksheet.set_column(idx, idx, 12, number_format)
                else:
                    worksheet.set_column(idx, idx, 15)
    
    return output.getvalue()


def create_abc_regional_analysis():
    st.title("Análise ABC Regional com Estoque")
    
    try:       
        # Garantir que os DataFrames existem no session_state
        if 'abc_data' not in st.session_state:
            st.session_state.abc_data = pd.DataFrame()
        if 'data_with_sales' not in st.session_state:
            st.session_state.data_with_sales = pd.DataFrame()
        if 'data_without_sales' not in st.session_state:
            st.session_state.data_without_sales = pd.DataFrame()
            
        # Definir colunas de display
        display_cols = [
                'sku', 'nome_produto', 'marca', 'uf_empresa', 'empresa', 'curva',
                'faturamento_liquido', 'quantidade_vendida', 'quantidade_bonificada',
                'saldo_estoque', 'valor_estoque'
            ]
        # Botão de atualização
        if st.button("Atualizar Dados"):
            with st.spinner("Carregando dados..."):
                merged_data = get_abc_curve_data(
                    cod_colaborador=st.session_state.get('cod_colaborador'),
                    start_date=st.session_state['start_date'],
                    end_date=st.session_state['end_date'],
                    selected_channels=st.session_state.selected_channels,
                    selected_ufs=st.session_state.selected_ufs,
                    selected_brands=st.session_state.selected_brands,
                    selected_nome_colaborador=st.session_state.get('selected_colaboradores'),
                    selected_teams=st.session_state.get('selected_teams')
                )
                
                # Armazenar dados
                st.session_state['abc_data'] = merged_data
                st.session_state['data_with_sales'] = merged_data[merged_data['quantidade_vendida'] > 0].copy()
                
                # Carregar dados de estoque
                stock_data = get_stock_data(
                    start_date=st.session_state['start_date'],
                    end_date=st.session_state['end_date'],
                    selected_channels=st.session_state.selected_channels,
                    selected_ufs=st.session_state.selected_ufs,
                    selected_brands=st.session_state.selected_brands,
                    selected_empresas=st.session_state.get('selected_empresas', [])
                )
                
                # Filtrar produtos sem venda mas com estoque
                produtos_sem_venda = stock_data[
                    (stock_data['quantidade_vendida'] == 0) & 
                    (stock_data['saldo_estoque'] > 0)
                ].copy()
                
                if 'valor_total_estoque' not in produtos_sem_venda.columns:
                    produtos_sem_venda['valor_total_estoque'] = produtos_sem_venda['saldo_estoque'] * produtos_sem_venda['custo_total']

                st.session_state['data_without_sales'] = produtos_sem_venda
                st.rerun()

        if 'abc_data' not in st.session_state or st.session_state['abc_data'].empty:
            st.info("Clique em 'Atualizar Dados' para carregar a análise.")
            return


        # Métricas principais
        total_faturamento = st.session_state['abc_data']['faturamento_liquido'].sum()
        total_estoque = st.session_state['abc_data']['valor_estoque'].sum()
        total_skus = len(st.session_state['abc_data']['sku'].unique())

        # Calcular giro de estoque
        days_period = (st.session_state['end_date'] - st.session_state['start_date']).days
        venda_media_diaria = (
            st.session_state['abc_data']['quantidade_vendida'].sum() + 
            st.session_state['abc_data']['quantidade_bonificada'].sum()
        ) / days_period
        
        quantidade_estoque = st.session_state['abc_data']['saldo_estoque'].sum()
        giro_estoque = f"{quantidade_estoque / venda_media_diaria:.2f}x dias" if venda_media_diaria > 0 else "0x dias"

        # Calcular métricas por curva
        curvas = st.session_state['abc_data'].groupby('curva')['sku'].nunique()
        total_skus = curvas.sum()
        
        curva_a = f"{curvas.get('A', 0):,.0f} SKUs ({curvas.get('A', 0)/total_skus*100:.1f}%)".replace(',', '.')
        curva_b = f"{curvas.get('B', 0):,.0f} SKUs ({curvas.get('B', 0)/total_skus*100:.1f}%)".replace(',', '.')
        curva_c = f"{curvas.get('C', 0):,.0f} SKUs ({curvas.get('C', 0)/total_skus*100:.1f}%)".replace(',', '.')

        # Renderizar o componente React
        st.markdown("""
            <div id="metrics-root"></div>
            <script>
                const props = {
                    faturamentoTotal: "R$ " + Number(%s).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}),
                    valorEstoque: "R$ " + Number(%s).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}),
                    totalSkus: Number(%s).toLocaleString('pt-BR'),
                    giroEstoque: "%s",
                    curvaA: "%s",
                    curvaB: "%s",
                    curvaC: "%s"
                };
            </script>
        """ % (
            total_faturamento,
            total_estoque,
            total_skus,
            giro_estoque,
            curva_a,
            curva_b,
            curva_c
        ), unsafe_allow_html=True)

        
        # Criar as tabs
        tab1, tab2, tab3, tab4 = st.tabs(["Visão Geral", "Por Marca", "Produtos Vendidos", "Produtos Sem Venda"])

        # Verificar se existem dados
        if 'abc_data' not in st.session_state or st.session_state['abc_data'].empty:
            with tab1:
                st.info("Clique em 'Atualizar Dados' para carregar a análise.")
            with tab2:
                st.info("Clique em 'Atualizar Dados' para carregar a análise.")
            with tab3:
                st.info("Clique em 'Atualizar Dados' para carregar a análise.")
            with tab4:
                st.info("Clique em 'Atualizar Dados' para carregar a análise.")
            return



        # Tab 1 - Visão Geral
        with tab1:
            # Usar apenas os dados filtrados
            filtered_data = st.session_state['abc_data']
            
            # Aplicar filtros principais
            if st.session_state.selected_ufs:
                filtered_data = filtered_data[filtered_data['uf_empresa'].isin(st.session_state.selected_ufs)]
            
            if not filtered_data.empty:
                regional_summary = filtered_data.groupby(['curva', 'uf_empresa']).agg({
                    'faturamento_liquido': 'sum',
                    'valor_estoque': 'sum',
                    'saldo_estoque': 'sum'
                }).reset_index()
                
                # Criar treemap apenas com os dados filtrados
                fig_treemap = px.treemap(
                    regional_summary,
                    path=['uf_empresa', 'curva'],
                    values='valor_estoque',
                    color='curva',
                    title='Distribuição do Estoque por Regional e Curva ABC',
                    color_discrete_map={'A': '#2ecc71', 'B': '#f1c40f', 'C': '#e74c3c'}
                )
                st.plotly_chart(fig_treemap, use_container_width=True)
            else:
                st.info("Não há dados para exibir com os filtros selecionados.")

        # Tab 2 - Por Marca
        with tab2:
            brand_summary = st.session_state['abc_data'].groupby(['marca', 'curva']).agg({
                'faturamento_liquido': 'sum',
                'valor_estoque': 'sum'
            }).reset_index()
            
            col1, col2 = st.columns(2)
            with col1:
                fig_revenue = px.bar(
                    brand_summary,
                    x='marca',
                    y='faturamento_liquido',
                    color='curva',
                    title='Faturamento por Marca e Curva ABC',
                    color_discrete_map={'A': '#2ecc71', 'B': '#f1c40f', 'C': '#e74c3c'}
                )
                st.plotly_chart(fig_revenue, use_container_width=True)
            
            with col2:
                fig_stock = px.bar(
                    brand_summary,
                    x='marca',
                    y='valor_estoque',
                    color='curva',
                    title='Valor em Estoque por Marca e Curva ABC',
                    color_discrete_map={'A': '#2ecc71', 'B': '#f1c40f', 'C': '#e74c3c'}
                )
                st.plotly_chart(fig_stock, use_container_width=True)

        # Tab 3 - Produtos Vendidos
        with tab3:
            st.subheader("Detalhamento - Produtos com Venda no Período")
            filtered_data = st.session_state['data_with_sales'].copy()
            
            # 1. Filtros
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                search_term = st.text_input("Buscar por SKU ou Nome do Produto", key="search_with_sales")
            with col2:
                marcas_disponiveis = ['Todas'] + sorted(filtered_data['marca'].unique().tolist())
                selected_marca = st.selectbox("Filtrar por Marca", options=marcas_disponiveis, key="marca_with_sales")                
            with col3:
                curvas_disponiveis = ['Todas'] + sorted(filtered_data['curva'].unique().tolist())
                selected_curve = st.selectbox("Filtrar por Curva", options=curvas_disponiveis, key="curve_with_sales")
            with col4:
                ufs_disponiveis = ['Todas'] + sorted(filtered_data['uf_empresa'].unique().tolist())
                selected_uf = st.selectbox("Filtrar por UF", options=ufs_disponiveis, key="uf_with_sales")

            # 2. Aplicar filtros
            if search_term:
                filtered_data = filtered_data[
                    filtered_data['sku'].str.contains(search_term, case=False, na=False) |
                    filtered_data['nome_produto'].str.contains(search_term, case=False, na=False)
                ]
            if selected_curve != 'Todas':
                filtered_data = filtered_data[filtered_data['curva'] == selected_curve]
            if selected_uf != 'Todas':
                filtered_data = filtered_data[filtered_data['uf_empresa'] == selected_uf]
            if selected_marca != 'Todas':
                filtered_data = filtered_data[filtered_data['marca'] == selected_marca]

            # 3. Resumo por curva
            st.subheader("Totais por Curva ABC")
            resumo_curva = filtered_data.groupby('curva').agg({
                'sku': 'nunique',
                'faturamento_liquido': 'sum',
                'valor_estoque': 'sum',
                'quantidade_vendida': 'sum',
                'saldo_estoque': 'sum'
            }).reset_index()
            
            # Calcular percentuais
            total_skus_vendidos = resumo_curva['sku'].sum()
            total_faturamento = resumo_curva['faturamento_liquido'].sum()
            total_estoque = resumo_curva['valor_estoque'].sum()
            
            resumo_curva['perc_skus'] = (resumo_curva['sku'] / total_skus_vendidos * 100)
            resumo_curva['perc_faturamento'] = (resumo_curva['faturamento_liquido'] / total_faturamento * 100)
            resumo_curva['perc_estoque'] = (resumo_curva['valor_estoque'] / total_estoque * 100)
            
            # Formatar o DataFrame para exibição
            resumo_curva_display = pd.DataFrame({
                'Curva': resumo_curva['curva'],
                'Qtde SKUs': resumo_curva['sku'].map('{:,.0f}'.format).str.replace(',', '.'),
                '% SKUs': resumo_curva['perc_skus'].map('{:.1f}%'.format),
                'Faturamento': resumo_curva['faturamento_liquido'].map('R$ {:,.2f}'.format).str.replace(',', '_').str.replace('.', ',').str.replace('_', '.'),
                '% Faturamento': resumo_curva['perc_faturamento'].map('{:.1f}%'.format),
                'Valor em Estoque': resumo_curva['valor_estoque'].map('R$ {:,.2f}'.format).str.replace(',', '_').str.replace('.', ',').str.replace('_', '.'),
                '% Estoque': resumo_curva['perc_estoque'].map('{:.1f}%'.format),
                'Qtde Vendida': resumo_curva['quantidade_vendida'].map('{:,.0f}'.format).str.replace(',', '.'),
                'Saldo Estoque': resumo_curva['saldo_estoque'].map('{:,.0f}'.format).str.replace(',', '.')
            })
            
            st.dataframe(
                resumo_curva_display,
                hide_index=True,
                use_container_width=True
            )

            # 4. Tabela detalhada
            st.subheader("Detalhamento por Produto")
            st.dataframe(
                filtered_data[display_cols].style.format({
                    'faturamento_liquido': 'R$ {:,.2f}',
                    'valor_estoque': 'R$ {:,.2f}',
                    'quantidade_vendida': '{:,.0f}',
                    'quantidade_bonificada': '{:,.0f}',
                    'saldo_estoque': '{:,.0f}'
                }),
                hide_index=True,
                use_container_width=True
            )

            # 5. Botão de exportação
            if st.button("Exportar para Excel", key="export_with_sales"):
                excel_data = generate_excel_report(data_with_sales=filtered_data)
                st.download_button(
                    label="📥 Baixar Relatório",
                    data=excel_data,
                    file_name="analise_abc_regional.xlsx",
                    mime="application/vnd.ms-excel"
                )

        # Tab 4 - Produtos Sem Venda
        with tab4:
            st.subheader("Detalhamento - Produtos sem Venda no Período")
            filtered_data = st.session_state['data_without_sales'].copy()
            
            if filtered_data.empty:
                st.info("Não há produtos sem venda no período selecionado.")
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    search_term = st.text_input("Buscar por SKU ou Nome do Produto", key="search_no_sales")
                with col2:
                    marcas_disponiveis = ['Todas'] + sorted(filtered_data['marca'].dropna().unique().tolist())
                    selected_marca = st.selectbox("Filtrar por Marca", options=marcas_disponiveis, key="marca_no_sales")                     
                with col3:
                    # Ajustar o filtro de UF para respeitar a seleção principal
                    ufs_disponiveis = ['Todas'] + sorted(filtered_data['uf_empresa'].dropna().unique().tolist())
                    default_uf = st.session_state.selected_ufs[0] if st.session_state.selected_ufs else 'Todas'
                    selected_uf = st.selectbox(
                        "Filtrar por UF",
                        options=ufs_disponiveis,
                        key="uf_no_sales",
                        index=ufs_disponiveis.index(default_uf) if default_uf in ufs_disponiveis else 0
                    )


                # Aplicar filtros
                if search_term:
                    filtered_data = filtered_data[
                        filtered_data['cod_produto'].str.contains(search_term, case=False, na=False) |
                        filtered_data['desc_produto'].str.contains(search_term, case=False, na=False)
                    ]
                
                # Aplicar filtro de UF selecionado no filtro principal
                if selected_uf and selected_uf != 'Todas':
                    filtered_data = filtered_data[filtered_data['uf_empresa'] == selected_uf]
                if selected_marca and selected_marca != 'Todas':
                    filtered_data = filtered_data[filtered_data['marca'] == selected_marca]                 

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total de SKUs sem Venda", f"{len(filtered_data):,}".replace(',', '.'))
                with col2:
                    valor_total_sem_venda = filtered_data['valor_total_estoque'].sum()
                    st.metric("Valor Total em Estoque", 
                            f"R$ {valor_total_sem_venda:,.2f}".replace(',', '.').replace('.', ',', 1))
                
                display_cols_no_sales = [
                    'cod_produto', 'desc_produto', 'marca', 'uf_empresa', 'empresa',
                    'saldo_estoque', 'valor_total_estoque'
                ]
                
                st.dataframe(
                    filtered_data[display_cols_no_sales].style.format({
                        'valor_total_estoque': 'R$ {:,.2f}',
                        'saldo_estoque': '{:,.0f}'
                    }),
                    hide_index=True,
                    use_container_width=True
                )

            if st.button("Exportar para Excel", key="export_no_sales"):
                excel_data = generate_excel_report(data_without_sales=filtered_data)
                st.download_button(
                    label="📥 Baixar Relatório",
                    data=excel_data,
                    file_name="analise_abc_regional.xlsx",
                    mime="application/vnd.ms-excel"
                )

    except Exception as e:
        st.error(f"Erro ao processar dados: {str(e)}")
        logging.error(f"Error in ABC Regional Analysis: {str(e)}")    

def main():
    logging.info("Iniciando página ABC Estoque Regional...")
    
    try:
        init_session_state()
        logging.info("Estado da sessão inicializado")
        
        load_page_specific_state("ABC_Regional")
        logging.info("Estado específico da página carregado")
        
        if not st.session_state.get('logged_in', False):
            st.warning("Por favor, faça login na página inicial para acessar esta página.")
            logging.warning("Tentativa de acesso sem login")
            return
        
        logging.info("Iniciando carregamento dos filtros...")
        load_filters()
        logging.info("Filtros carregados com sucesso")
        
        logging.info("Iniciando análise ABC regional...")
        create_abc_regional_analysis()
        logging.info("Análise ABC regional concluída")
        
    except Exception as e:
        logging.error(f"Erro na função main: {str(e)}", exc_info=True)
        st.error(f"""
            Ocorreu um erro ao carregar a página. 
            Detalhes: {str(e)}
            
            Por favor, verifique os logs para mais informações.
        """)

if __name__ == "__main__":
    logging.info("Iniciando aplicação ABC Regional...")
    try:
        main()
    except Exception as e:
        logging.error(f"Erro na execução principal: {str(e)}", exc_info=True)
        st.error("Erro ao iniciar a aplicação. Verifique os logs para mais detalhes.")        