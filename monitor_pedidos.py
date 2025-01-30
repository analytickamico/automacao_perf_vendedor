import streamlit as st
import pandas as pd
from pyathena import connect
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff

import streamlit as st

os.environ['STREAMLIT_SERVER_PORT'] = '8504'

# Configuração da página
st.set_page_config(
    page_title="Monitor de Pedidos",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Esconder elementos desnecessários
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        .stDeployButton {display:none;}
        [data-testid="stSidebar"] {display: none;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def buscar_dados_resumo(_conn):
    """Busca dados para o resumo dos pedidos"""
    query = """
    SELECT 
        status_pedido,
        empresa,
        COUNT(*) as quantidade,
        SUM(vlr_pedido) as valor_total,
        AVG(CAST(dias_aprovacao AS double)) as media_dias_aprovacao,
        AVG(CAST(em_aberto AS double)) as media_dias_aberto,
        MAX(em_aberto) as max_dias_aberto
    FROM databeautykami.tbl_distribuicao_stream_pedidos
    WHERE status_pedido IN (
        'Pré-Pedido', 'Pendente Financeiro', 'Pendente Comercial',
        'Aprovado', 'Separado', 'Faturado'
    )
    GROUP BY status_pedido, empresa
    """
    return pd.read_sql(query, _conn)

@st.cache_data(ttl=300)
def buscar_dados_detalhados(_conn):
    """Busca dados detalhados dos pedidos"""
    query = """
    SELECT 
        cod_pedido,
        empresa,
        cliente,
        representante,
        status_pedido,
        vlr_pedido,
        dt_implant,
        dt_aprovacao,
        dt_ultima_alteracao,
        dias_aprovacao,
        em_aberto
    FROM databeautykami.tbl_distribuicao_stream_pedidos
    WHERE status_pedido IN (
        'Pré-Pedido', 'Pendente Financeiro', 'Pendente Comercial',
        'Aprovado', 'Separado', 'Faturado'
    )
    ORDER BY dt_ultima_alteracao DESC
    """
    return pd.read_sql(query, _conn)

def criar_sankey_fluxo(df):
    """Cria diagrama Sankey do fluxo de pedidos com quantidades"""
    # Definir ordem dos status
    ordem_status = ['Pré-Pedido', 'Pendente Financeiro', 'Pendente Comercial', 
                   'Aprovado', 'Separado', 'Faturado']
    
    # Agrupar dados por status
    df_qtd = df.groupby('status_pedido')['quantidade'].sum().reset_index()
    
    # Criar labels com quantidade
    labels = [f"{status}\n({int(df_qtd[df_qtd['status_pedido'] == status]['quantidade'].iloc[0])} pedidos)" 
             for status in ordem_status]
    
    fig = go.Figure(data=[go.Sankey(
        arrangement = "snap",
        node = dict(
            pad = 15,
            thickness = 20,
            line = dict(color="black", width=0.5),
            label = labels,
            color = ["#FFD700",    # Amarelo
                    "#FF8C00",     # Laranja
                    "#FF6347",     # Tomate
                    "#32CD32",     # Verde Lima
                    "#4169E1",     # Azul Real
                    "#228B22"]     # Verde Floresta
        ),
        link = dict(
            source = [0, 0, 1, 2, 3, 4],
            target = [1, 2, 3, 3, 4, 5],
            value = [30, 20, 25, 15, 35, 30],
            color = ["rgba(200, 200, 200, 0.5)"] * 6  # Cinza claro para todos os links
        )
    )])
    
    fig.update_layout(
        height=250,
        font=dict(
            size=13,
            color='black',
            family='Arial, sans-serif'
        ),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(t=20, b=20, l=0, r=0)
    )
    
    return fig

def criar_metricas_principais(df_resumo):
    """Cria cards com métricas principais em destaque"""
    st.markdown("""
    <style>
    .metric-container {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        total_pedidos = df_resumo['quantidade'].sum()
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Total de Pedidos</div>
            <div class="metric-value">{total_pedidos:,}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        valor_total = df_resumo['valor_total'].sum()
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Valor Total</div>
            <div class="metric-value">R$ {valor_total:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        media_aprovacao = df_resumo['media_dias_aprovacao'].mean()
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Média Dias p/ Aprovação</div>
            <div class="metric-value">{media_aprovacao:.1f}</div>
        </div>
        """, unsafe_allow_html=True)

def criar_alertas_tempo(df_detalhes):
    """Cria seção de alertas com todas as categorias"""
    st.subheader("🚦 Alertas de Tempo")
    
    # Preparar dados para alertas
    alertas_df = df_detalhes[['cod_pedido', 'empresa', 'status_pedido', 'em_aberto', 'dt_ultima_alteracao']].copy()
    
    # Calcular dias na etapa atual
    hoje = pd.Timestamp.now()
    alertas_df['dias_etapa_atual'] = (hoje - pd.to_datetime(alertas_df['dt_ultima_alteracao'])).dt.days
    
    # Layout em duas colunas
    col1, col2 = st.columns(2)
    
    with col1:
        # Pedidos Críticos
        with st.container():
            st.markdown("""
            <div style="background-color: rgba(255, 0, 0, 0.1); padding: 10px; border-radius: 5px;">
                ⛔ Pedidos Críticos (> 30 dias)
                <br/>
                <small>Pedido | Empresa | Status | Dias Total | Dias na Etapa</small>
            </div>
            """, unsafe_allow_html=True)
            
            criticos = alertas_df[alertas_df['em_aberto'] > 30].head(5)
            for _, row in criticos.iterrows():
                st.error(
                    f"{row['cod_pedido']} | {row['empresa']} | {row['status_pedido']} | "
                    f"{int(row['em_aberto'])} | {int(row['dias_etapa_atual'])}"
                )
        # Pedidos em Atenção (5-3 dias)
            st.markdown("""
            <div style="background-color: rgba(255, 215, 0, 0.1); padding: 10px; border-radius: 5px;">
                🟡 Pedidos em Atenção (3-5 dias)
                <br/>
                <small>Pedido | Empresa | Status | Dias Total | Dias na Etapa</small>
            </div>
            """, unsafe_allow_html=True)
            
            atencao = alertas_df[
                (alertas_df['em_aberto'] <= 5) & 
                (alertas_df['em_aberto'] > 3)
            ].head(5)
            for _, row in atencao.iterrows():
                st.warning(
                    f"{row['cod_pedido']} | {row['empresa']} | {row['status_pedido']} | "
                    f"{int(row['em_aberto'])} | {int(row['dias_etapa_atual'])}"
                )
    
    with col2:
        # Pedidos em Alerta
        with st.container():
            st.markdown("""
            <div style="background-color: rgba(255, 150, 0, 0.1); padding: 10px; border-radius: 5px;">
                🔴 Pedidos em Alerta (6-30 dias)
                <br/>
                <small>Pedido | Empresa | Status | Dias Total | Dias na Etapa</small>
            </div>
            """, unsafe_allow_html=True)
            
            alertas = alertas_df[
                (alertas_df['em_aberto'] <= 30) & 
                (alertas_df['em_aberto'] > 5)
            ].head(5)
            for _, row in alertas.iterrows():
                st.warning(
                    f"{row['cod_pedido']} | {row['empresa']} | {row['status_pedido']} | "
                    f"{int(row['em_aberto'])} | {int(row['dias_etapa_atual'])}"
                )      
        
            
            # Pedidos Normais
            st.markdown("""
            <div style="background-color: rgba(0, 255, 0, 0.1); padding: 10px; border-radius: 5px;">
                🟢 Pedidos Normais (≤ 3 dias)
                <br/>
                <small>Pedido | Empresa | Status | Dias Total | Dias na Etapa</small>
            </div>
            """, unsafe_allow_html=True)
            
            normais = alertas_df[alertas_df['em_aberto'] <= 3].head(5)
            for _, row in normais.iterrows():
                st.success(
                    f"{row['cod_pedido']} | {row['empresa']} | {row['status_pedido']} | "
                    f"{int(row['em_aberto'])} | {int(row['dias_etapa_atual'])}"
                )                                                   

def criar_tab_visao_geral(monitor):
    # Busca dados
    df_resumo = buscar_dados_resumo(monitor.conn)
    df_detalhes = buscar_dados_detalhados(monitor.conn)
    
    # Header com última atualização
    st.title("📦 Monitor de Pedidos")
    st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Fluxo de pedidos
    st.subheader("🔄 Fluxo de Pedidos")
    st.plotly_chart(criar_sankey_fluxo(df_resumo), use_container_width=True)
    
    # Métricas principais em destaque
    criar_metricas_principais(df_resumo)
    
    # Alertas em duas colunas
    criar_alertas_tempo(df_detalhes)

def criar_tab_detalhamento(monitor):
    # Busca dados detalhados
    df_detalhes = buscar_dados_detalhados(monitor.conn)
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        empresa_filtro = st.multiselect(
            "Empresa",
            options=sorted(df_detalhes['empresa'].unique())
        )
    with col2:
        status_filtro = st.multiselect(
            "Status",
            options=sorted(df_detalhes['status_pedido'].unique())
        )
    with col3:
        representante_filtro = st.multiselect(
            "Representante",
            options=sorted(df_detalhes['representante'].unique())
        )
    
    # Aplicar filtros
    if empresa_filtro:
        df_detalhes = df_detalhes[df_detalhes['empresa'].isin(empresa_filtro)]
    if status_filtro:
        df_detalhes = df_detalhes[df_detalhes['status_pedido'].isin(status_filtro)]
    if representante_filtro:
        df_detalhes = df_detalhes[df_detalhes['representante'].isin(representante_filtro)]
    
    # Top 10 Representantes
    st.subheader("🏆 Top 10 Representantes")
    df_top10 = df_detalhes.groupby('representante').agg({
        'cod_pedido': 'count',
        'vlr_pedido': 'sum'
    }).reset_index().sort_values('vlr_pedido', ascending=False).head(10)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Por Valor Total de Pedidos**")
        st.dataframe(
            df_top10,
            column_config={
                "representante": "Representante",
                "cod_pedido": st.column_config.NumberColumn("Qtd. Pedidos"),
                "vlr_pedido": st.column_config.NumberColumn("Valor Total", format="R$ %.2f")
            },
            hide_index=True
        )
    
    # Tabela detalhada
    st.subheader("📋 Detalhamento dos Pedidos")
    st.dataframe(
        df_detalhes,
        column_config={
            "vlr_pedido": st.column_config.NumberColumn(
                "Valor do Pedido",
                format="R$ %.2f"
            ),
            "dt_implant": st.column_config.DatetimeColumn(
                "Data Implantação",
                format="DD/MM/YYYY HH:mm"
            ),
            "dt_aprovacao": st.column_config.DatetimeColumn(
                "Data Aprovação",
                format="DD/MM/YYYY HH:mm"
            ),
            "dt_ultima_alteracao": st.column_config.DatetimeColumn(
                "Última Alteração",
                format="DD/MM/YYYY HH:mm"
            )
        },
        hide_index=True
    )
class MonitorPedidos:
    def __init__(self):
        try:
            athena_output = "s3://aws-athena-query-results-168680478947-us-east-1/"
            self.conn = connect(
                region_name='us-east-1',
                s3_staging_dir=athena_output
            )
            st.session_state['conexao_ok'] = True
        except Exception as e:
            st.error(f"Erro ao conectar com Athena: {str(e)}")
            st.session_state['conexao_ok'] = False

def main():
    try:
        monitor = MonitorPedidos()
        
        if st.session_state.get('conexao_ok', False):
            # Criar tabs
            tab1, tab2 = st.tabs(["📈 Visão Geral", "🔍 Detalhamento"])
            
            with tab1:
                criar_tab_visao_geral(monitor)
            
            with tab2:
                criar_tab_detalhamento(monitor)
            
            # Configuração da atualização automática no sidebar
            with st.sidebar:
                st.header("⚙️ Configurações")
                auto_update = st.checkbox("Atualização Automática", value=True)
                if auto_update:
                    update_interval = st.slider(
                        "Intervalo (minutos)",
                        min_value=1,
                        max_value=60,
                        value=15
                    )
            
            # Atualização automática
            if auto_update:
                time.sleep(update_interval * 60)
                st.experimental_rerun()
                
    except Exception as e:
        st.error(f"Erro na aplicação: {str(e)}")

if __name__ == "__main__":
    main()