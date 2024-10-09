# Curva_ABC.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils import get_abc_curve_data_cached, get_static_data
from session_state_manager import init_session_state, load_page_specific_state, ensure_cod_colaborador
import sys
import os
from plotly.subplots import make_subplots
import plotly.express as px
import time
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")

st.set_page_config(page_title="Curva ABC - Vendas",page_icon=ico_path, layout="wide")

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
ico_path = os.path.join(parent_dir, "favicon.ico")



def format_currency(value):
    if isinstance(value, str):
        if value.startswith("R$"):
            return value
        try:
            value = float(value.replace(".", "").replace(",", ".").strip())
        except ValueError:
            return value
    
    if isinstance(value, (int, float)):
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    return str(value) 

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
    try:
        my_bar.progress(50, text="Carregando dados dos produtos...")
        st.session_state['abc_data'] = get_abc_curve_data_cached(
            cod_colaborador=st.session_state['cod_colaborador'],
            start_date=st.session_state['start_date'],
            end_date=st.session_state['end_date'],
            selected_channels=st.session_state.selected_channels,
            selected_ufs=st.session_state.selected_ufs,
            selected_brands=st.session_state.selected_brands,
            selected_nome_colaborador=st.session_state.selected_colaboradores,
            selected_teams=st.session_state.selected_teams
        )
        my_bar.progress(100, text="Carregamento concluído!")
        time.sleep(1)
        my_bar.empty()
        st.session_state['data_needs_update'] = False
    except Exception as e:
        my_bar.empty()
        st.error(f"Erro ao carregar dados: {str(e)}")
        logging.error(f"Erro ao carregar dados: {str(e)}", exc_info=True)

def create_dashboard():
    st.title("Curva ABC de Produtos")

    if 'abc_data' in st.session_state and st.session_state['abc_data'] is not None:
        df = st.session_state['abc_data']
        
        if not df.empty:
            # Resumo geral da Curva ABC
            st.subheader("Resumo da Curva ABC")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Produtos A", f"{len(df[df['curva'] == 'A'])} ({len(df[df['curva'] == 'A']) / len(df):.1%})")
            with col2:
                st.metric("Produtos B", f"{len(df[df['curva'] == 'B'])} ({len(df[df['curva'] == 'B']) / len(df):.1%})")
            with col3:
                st.metric("Produtos C", f"{len(df[df['curva'] == 'C'])} ({len(df[df['curva'] == 'C']) / len(df):.1%})")

            # Gráfico de distribuição da Curva ABC
            st.subheader("Distribuição da Curva ABC")
            fig = create_abc_chart(df)
            st.plotly_chart(fig, use_container_width=True)

            # Texto explicativo
            with st.expander("Clique aqui para ver como interpretar o gráfico"):
                st.markdown("""
                ### Como interpretar o gráfico da Curva ABC:
                - A linha azul representa o faturamento acumulado dos produtos.
                - Produtos à esquerda da linha vermelha (80%) são categoria A:
                  - Representam cerca de 20% dos produtos e 80% do faturamento.
                  - São os itens mais importantes e devem receber maior atenção.
                - Produtos entre a linha vermelha e verde (95%) são categoria B:
                  - Representam aproximadamente 30% dos produtos e 15% do faturamento.
                  - São itens de importância intermediária.
                - Produtos à direita da linha verde são categoria C:
                  - Representam cerca de 50% dos produtos, mas apenas 5% do faturamento.
                  - São itens menos críticos, mas que ainda merecem atenção.
                - Quanto mais íngreme a curva, mais concentrado o faturamento em poucos produtos.
                - Os pontos coloridos destacam os top 10 produtos de cada categoria.
                
                **Dica:** Use esta análise para otimizar seu estoque, foco de vendas e estratégias de marketing.
                """)

            # Top 10 produtos de cada curva
            st.subheader("Top 10 Produtos por Curva")
            tab1, tab2, tab3 = st.tabs(["Curva A", "Curva B", "Curva C"])

            for tab, curva in zip([tab1, tab2, tab3], ['A', 'B', 'C']):
                with tab:
                    top_10 = df[df['curva'] == curva].head(10)
                    st.dataframe(
                        top_10[['sku', 'nome_produto', 'marca', 'faturamento_liquido', 'quantidade_vendida']].style.format({
                            'faturamento_liquido': lambda x: f"R$ {x:,.2f}",
                            'quantidade_vendida': lambda x: f"{x:,.0f}".replace(',', '.')
                        }),
                        use_container_width=True, 
                        hide_index=True
                    )

            # Tabela de percentual por marca para cada curva
            st.subheader("Percentual por Marca em Cada Curva")
            marca_percentages = create_marca_percentage_table(df)
            st.dataframe(marca_percentages.style.format("{:.2f}%"))

        else:
            st.warning("Não há dados disponíveis para o período e filtros selecionados.")
    else:
        st.warning("Nenhum dado carregado. Por favor, escolha os filtros e acione Atualizar Dados.")

def create_abc_chart(df):
    fig = go.Figure()

    # Curva ABC principal
    fig.add_trace(go.Scatter(
        x=df['faturamento_acumulado'], 
        y=df['faturamento_liquido'], 
        mode='lines',
        name='Faturamento Acumulado'
    ))

    # Destacar top 10 de cada categoria
    colors = {'A': 'red', 'B': 'green', 'C': 'blue'}
    for curva in ['A', 'B', 'C']:
        top_10 = df[df['curva'] == curva].head(10)
        fig.add_trace(go.Scatter(
            x=top_10['faturamento_acumulado'], 
            y=top_10['faturamento_liquido'],
            mode='markers',
            name=f'Top 10 {curva}',
            marker=dict(size=10, color=colors[curva])
        ))

    # Linhas de 80% e 95%
    fig.add_shape(type="line", x0=0.8, y0=0, x1=0.8, y1=df['faturamento_liquido'].max(), 
                  line=dict(color="red", width=2, dash="dash"))
    fig.add_shape(type="line", x0=0.95, y0=0, x1=0.95, y1=df['faturamento_liquido'].max(), 
                  line=dict(color="green", width=2, dash="dash"))

    fig.update_layout(
        title="Distribuição da Curva ABC",
        xaxis_title="Faturamento Acumulado",
        yaxis_title="Faturamento Líquido",
        xaxis=dict(tickformat=".0%"),
        yaxis=dict(tickformat="$,.0f")
    )

    # Adicionar anotações explicativas
    fig.add_annotation(x=0.4, y=df['faturamento_liquido'].max(), 
                       text="80% do faturamento - Limite da Categoria A", 
                       showarrow=False, yshift=10)
    fig.add_annotation(x=0.975, y=df['faturamento_liquido'].max(), 
                       text="95% do faturamento - Limite da Categoria B", 
                       showarrow=False, yshift=10)

    return fig

def create_marca_percentage_table(df):
    marca_percentages = df.groupby(['curva', 'marca'])['faturamento_liquido'].sum().unstack(level=0)
    marca_percentages = marca_percentages.div(marca_percentages.sum()) * 100
    marca_percentages = marca_percentages.round(2)
    marca_percentages = marca_percentages.sort_values(by='A', ascending=False)
    return marca_percentages

def main():
    init_session_state()
    load_page_specific_state("Curva_ABC")
    if not st.session_state.get('logged_in', False):
        st.warning("Por favor, faça login na página inicial para acessar esta página.")
        return    
    
    

    try:
        st.sidebar.title('Configurações do Dashboard')
        load_filters()

        #if st.session_state.get('data_needs_update', True):
        #    load_data()

        create_dashboard()

    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {str(e)}")
        logging.error(f"Erro ao carregar o dashboard: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()