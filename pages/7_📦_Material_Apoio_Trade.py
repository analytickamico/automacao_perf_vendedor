import streamlit as st
import pandas as pd
import plotly.express as px
from utils import get_stock_material_apoio_trade, get_static_data, create_metric_html
from session_state_manager import init_session_state, load_page_specific_state
import logging
from datetime import datetime, timedelta
import time
from io import BytesIO
from styles import apply_theme

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Page config
st.set_page_config(page_title="Material de Trade e Apoio", page_icon="📦", layout="wide")
#apply_theme()

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

def load_filters():
    """Load and display filters in sidebar"""
    initialize_filters()
    
    static_data = st.session_state.static_data
    
    st.sidebar.title('Filtros')
    
    # Date filters
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=90)
    
    st.session_state['start_date'] = st.sidebar.date_input(
        "Data Inicial",
        value=st.session_state.get('end_date', end_date) - timedelta(days=90),
        key='start_date_input'
    )

    st.session_state['end_date'] = st.sidebar.date_input(
        "Data Final",
        value=end_date,
        key='end_date_input'
    )
    
    # UF filter
    st.session_state.selected_ufs = st.sidebar.multiselect(
        "UFs",
        options=static_data.get('ufs', []),
        default=st.session_state.get('selected_ufs', [])
    )
    
    # Brand filter with "Select All" option
    all_brands_selected = st.sidebar.checkbox("Selecionar Todas as Marcas", value=False)

    with st.sidebar.expander("Selecionar/Excluir Marcas Específicas", expanded=False):
        available_brands = [brand for brand in static_data.get('marcas', []) if brand is not None]

        if all_brands_selected:
            default_brands = available_brands  # Selecionar todas as marcas disponíveis
        else:
            default_brands = [
                brand for brand in st.session_state.get('selected_brands', []) 
                if brand in available_brands
            ]  # Apenas marcas válidas

        selected_brands = st.multiselect(
            "Marcas",
            options=available_brands,
            default=default_brands
        )



    
    st.session_state.selected_brands = selected_brands if not all_brands_selected else static_data.get('marcas', [])

def generate_excel_report(data):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Configurações do workbook
            workbook = writer.book
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            number_format = workbook.add_format({'num_format': '#,##0'})
            currency_format = workbook.add_format({'num_format': 'R$ #,##0.00'})

            # Aba principal com todos os materiais
            data.to_excel(writer, sheet_name='Materiais', index=False)
            worksheet = writer.sheets['Materiais']

            # Formatar colunas
            for idx, col in enumerate(data.columns):
                worksheet.write(0, idx, col, header_format)
                if 'valor' in col.lower():
                    worksheet.set_column(idx, idx, 15, currency_format)
                elif any(x in col.lower() for x in ['quantidade', 'saldo']):
                    worksheet.set_column(idx, idx, 12, number_format)
                else:
                    worksheet.set_column(idx, idx, 15)

            # Aba de resumo por tipo de material
            summary_by_type = data.groupby('tipo_material').agg({
                'cod_produto': 'count',
                'saldo_estoque': 'sum',
                'valor_total_estoque': 'sum',
                'quantidade_utilizada': 'sum'
            }).reset_index()

            summary_by_type.to_excel(writer, sheet_name='Resumo por Tipo', index=False)
            worksheet = writer.sheets['Resumo por Tipo']
            
            # Formatar aba de resumo
            for idx, col in enumerate(summary_by_type.columns):
                worksheet.write(0, idx, col, header_format)

        return output.getvalue()

def main():
    logging.info("Iniciando página Material de Trade e Apoio...")
    
    try:
        init_session_state()
        logging.info("Estado da sessão inicializado")
        
        load_page_specific_state("Material_Apoio_Trade")
        logging.info("Estado específico da página carregado")
        
        if not st.session_state.get('logged_in', False):
            st.warning("Por favor, faça login na página inicial para acessar esta página.")
            logging.warning("Tentativa de acesso sem login")
            return
        
        logging.info("Iniciando carregamento dos filtros...")
        load_filters()
        logging.info("Filtros carregados com sucesso")
        
        st.title("Análise de Materiais de Trade e Apoio 📦")

        try:
            if st.session_state.get('data_needs_update', True):
                with st.spinner("Carregando dados..."):
                    data = get_stock_material_apoio_trade(
                        start_date=st.session_state['start_date'].strftime('%Y-%m-%d'),
                        end_date=st.session_state['end_date'].strftime('%Y-%m-%d'),
                        selected_channels=[],
                        selected_ufs=st.session_state.selected_ufs,
                        selected_brands=st.session_state.selected_brands,
                        selected_empresas=[]
                    )

                    if data.empty:
                        st.warning("Não há dados disponíveis para os filtros selecionados.")
                        return

                    data = data.fillna({
                        'tipo_material': 'Não Classificado',
                        'nop': 'Sem NOP'
                    })
                    data['tipo_material'] = data['tipo_material'].astype(str)
                    data['nop'] = data['nop'].astype(str)

                    st.session_state['trade_materials_data'] = data
                    st.session_state.data_needs_update = False

            if 'trade_materials_data' not in st.session_state:
                st.info("Clique em 'Atualizar Dados' para carregar a análise.")
                return

            data = st.session_state['trade_materials_data']

            # Métricas principais
            col1, col2, col3 = st.columns(3)
            # Métricas iniciais com layout aprimorado
            # Calcular valores primeiro
            # Calcular métricas uma única vez no início
            total_materials = data['saldo_estoque'].sum()
            total_used = data['quantidade_utilizada'].sum()
            usage_rate = (total_used / total_materials * 100) if total_materials > 0 else 0
            total_value = data['valor_total_estoque'].sum()

            # Exibir métricas em um único layout
            st.markdown("""
            <div style="display: flex; justify-content: space-between; gap: 20px; margin: 20px 0;">
                <div style="background: #f0f2f6; padding: 20px; border-radius: 10px; flex: 1; text-align: center;">
                    <div style="font-size: 16px; color: #666;">Total de Materiais</div>
                    <div style="font-size: 24px; font-weight: bold; color: #1f77b4; margin-top: 10px;">{:,.0f}</div>
                </div>
                <div style="background: #f0f2f6; padding: 20px; border-radius: 10px; flex: 1; text-align: center;">
                    <div style="font-size: 16px; color: #666;">Taxa de Utilização</div>
                    <div style="font-size: 24px; font-weight: bold; color: #1f77b4; margin-top: 10px;">{:.1f}%</div>
                </div>
                <div style="background: #f0f2f6; padding: 20px; border-radius: 10px; flex: 1; text-align: center;">
                    <div style="font-size: 16px; color: #666;">Valor Total</div>
                    <div style="font-size: 24px; font-weight: bold; color: #1f77b4; margin-top: 10px;">R$ {:,.2f}</div>
                </div>
                <div style="background: #f0f2f6; padding: 20px; border-radius: 10px; flex: 1; text-align: center;">
                    <div style="font-size: 16px; color: #666;">Quantidade Utilizada</div>
                    <div style="font-size: 24px; font-weight: bold; color: #1f77b4; margin-top: 10px;">{:,.0f}</div>
                </div>
            </div>
            """.format(total_materials, usage_rate, total_value, total_used), unsafe_allow_html=True)


            #with col1:
                #total_materials = data['saldo_estoque'].sum()  # Definir antes de usar
                #st.metric("Total de Materiais", f"{total_materials:,.0f}".replace(',', '.'))
  
               
            #with col3:
                #total_used = data['quantidade_utilizada'].sum()
                #usage_rate = (usage_rate) 
                #st.markdown(create_metric_html(
                    #"Taxa de Utilização",
                    #f"{usage_rate:.1f}%",
                    #is_currency=False
                #), unsafe_allow_html=True)

            # Criar as tabs
            if 'current_tab' not in st.session_state:
                st.session_state.current_tab = "Visão Geral"
                
            # Tab 1 - Visão Geral
            tab1, tab2 = st.tabs(["Visão Geral", "Detalhamento"])

            # Tab 1 - Visão Geral
            # Na Tab 1
            with tab1:
                container = st.container()
                col1, col2 = container.columns(2)
                
                with col1:
                    tipos_material = data['tipo_material'].unique()
                    selected_tipo_overview = st.selectbox(
                        "Filtrar por Tipo de Material",
                        options=['Todos'] + sorted([x for x in tipos_material if x is not None]),
                        key="tipo_material_overview"
                    )
                    
                    filtered_data = data.copy()
                    if selected_tipo_overview != 'Todos':
                        filtered_data = filtered_data[filtered_data['tipo_material'] == selected_tipo_overview]

                    brand_summary = filtered_data.groupby('marca').agg({
                        'quantidade_utilizada': 'sum',
                        'saldo_estoque': 'sum'
                    }).reset_index()
                    
                    brand_summary_melted = pd.melt(
                        brand_summary,
                        id_vars=['marca'],
                        value_vars=['quantidade_utilizada', 'saldo_estoque'],
                        var_name='Tipo',
                        value_name='Quantidade'
                    )
                    
                    fig_usage = px.bar(
                        brand_summary_melted,
                        x='marca',
                        y='Quantidade',
                        color='Tipo',
                        title='Utilização por Marca',
                        color_discrete_map={'quantidade_utilizada': '#1f77b4', 'saldo_estoque': '#ff7f0e'},
                        template='plotly_white',
                        height=500
                    )
                    
                    fig_usage.update_layout(
                        legend_title_text='',
                        xaxis_title="",
                        yaxis_title="Quantidade",
                        bargap=0.2
                    )
                    
                    st.plotly_chart(fig_usage, use_container_width=True)

                with col2:
                    uf_summary = filtered_data.groupby(['uf_empresa', 'tipo_material']).agg({
                        'valor_total_estoque': 'sum'
                    }).reset_index()
                    
                    fig_stock = px.bar(
                        uf_summary,
                        x='uf_empresa',
                        y='valor_total_estoque',
                        color='tipo_material',
                        title='Valor em Estoque por UF',
                        template='plotly_white',
                        height=500
                    )
                    
                    fig_stock.update_layout(
                        xaxis_title="UF",
                        yaxis_title="Valor em Estoque (R$)",
                        legend_title_text='Tipo Material',
                        bargap=0.2
                    )
                    
                    fig_stock.update_yaxes(tickformat=",.2f", tickprefix="R$ ")
                    
                    st.plotly_chart(fig_stock, use_container_width=True)

                # Atualizar o estado da tab
                st.session_state.current_tab = "Visão Geral"

            # Tab 2 - Detalhamento
            # Na tab2:
            with tab2:
                st.subheader("Detalhamento dos Materiais")
                
                # Métricas em cards

                # Filtros locais
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    search_term = st.text_input("Buscar por Código ou Descrição", key="search_detail")
                with col2:
                    marcas_disponiveis = ['Todas'] + sorted(data['marca'].dropna().unique().tolist())
                    selected_marca = st.selectbox("Filtrar por Marca", options=marcas_disponiveis, key="marca_detail")
                with col3:
                    ufs_disponiveis = ['Todas'] + sorted(data['uf_empresa'].dropna().unique().tolist())
                    selected_uf = st.selectbox("Filtrar por UF", options=ufs_disponiveis, key="uf_detail")
                with col4:
                    tipos_material = ['Todos'] + sorted(data['tipo_material'].dropna().unique().tolist())
                    selected_tipo = st.selectbox("Filtrar por Tipo de Material", options=tipos_material, key="tipo_material_detail")

                # Aplicar filtros com tratamento de nulos
                filtered_data = data.copy()
                if search_term:
                    filtered_data = filtered_data[
                        filtered_data['cod_produto'].fillna('').str.contains(search_term, case=False, na=False) |
                        filtered_data['desc_produto'].fillna('').str.contains(search_term, case=False, na=False)
                    ]
                if selected_marca != 'Todas':
                    filtered_data = filtered_data[filtered_data['marca'].fillna('') == selected_marca]
                if selected_uf != 'Todas':
                    filtered_data = filtered_data[filtered_data['uf_empresa'].fillna('') == selected_uf]
                if selected_tipo != 'Todos':
                    filtered_data = filtered_data[filtered_data['tipo_material'].fillna('') == selected_tipo]

                st.dataframe(
                    filtered_data[[
                        'cod_produto', 'desc_produto', 'marca', 'uf_empresa', 'empresa',
                        'tipo_material', 'nop', 'saldo_estoque', 'valor_total_estoque',
                        'quantidade_utilizada'
                    ]].style.format({
                        'valor_total_estoque': 'R$ {:,.2f}',
                        'saldo_estoque': '{:,.0f}',
                        'quantidade_utilizada': '{:,.0f}'
                    }),
                    hide_index=True,
                    use_container_width=True
                )
                st.markdown("""
                    <style>
                    .custom-dataframe {
                        background-color: #2D2D2D !important;
                    }
                    </style>
                """, unsafe_allow_html=True)

                # Botão de exportação Excel com melhor posicionamento
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("Exportar para Excel"):
                        excel_data = generate_excel_report(filtered_data)
                        st.download_button(
                            label="📥 Baixar Relatório",
                            data=excel_data,
                            file_name=f"materiais_trade_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.ms-excel"
                        )

            # Atualizar o estado da tab atual baseado na tab selecionada
                if tab1:
                    st.session_state.current_tab = "Visão Geral"
                if tab2:
                    st.session_state.current_tab = "Detalhamento"

            # Botão de atualização
            if st.button("Atualizar Dados"):
                st.session_state.data_needs_update = True

        except Exception as e:
            st.error(f"Erro ao processar dados: {str(e)}")
            logging.error(f"Error in Trade Materials Analysis: {str(e)}")

    except Exception as e:
        logging.error(f"Erro na função main: {str(e)}", exc_info=True)
        st.error(f"""
            Ocorreu um erro ao carregar a página. 
            Detalhes: {str(e)}
            
            Por favor, verifique os logs para mais informações.
        """)

if __name__ == "__main__":
    logging.info("Iniciando aplicação Material de Trade e Apoio...")
    try:
        main()
    except Exception as e:
        logging.error(f"Erro na execução principal: {str(e)}", exc_info=True)
        st.error("Erro ao iniciar a aplicação. Verifique os logs para mais detalhes.")