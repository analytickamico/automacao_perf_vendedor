import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import logging
from pyathena import connect
from dotenv import load_dotenv
from pyathena.pandas.util import as_pandas
import json
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError



__all__ = [
    'get_monthly_revenue_cached', 'get_brand_data_cached', 'get_channels_and_ufs_cached',
    'get_colaboradores_cached', 'get_rfm_summary_cached', 'get_rfm_heatmap_data_cached',
    'query_athena', 'get_monthly_revenue', 'get_brand_data', 'get_rfm_summary',
    'get_rfm_segment_clients', 'get_rfm_heatmap_data', 'create_rfm_heatmap_from_aggregated',
    'get_channels_and_ufs', 'get_colaboradores', 'get_client_status',
    'create_client_status_chart', 'create_new_rfm_heatmap', 'clear_cache', 'get_team_options',
    'get_static_data', 'force_update_static_data','get_stock_purchases','get_stock_data','calculate_stock_metrics',
    'create_metric_html','get_recency_clients','get_unique_customers_by_granularity','get_weighted_markup'
]

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Carregar variáveis de ambiente
load_dotenv()

# Configurações de conexão Athena
ATHENA_S3_STAGING_DIR = os.environ.get('ATHENA_S3_STAGING_DIR', 's3://databeautykamico/Athena/')
ATHENA_REGION = os.environ.get('ATHENA_REGION', 'us-east-1')

logging.info(f"Usando ATHENA_S3_STAGING_DIR: {ATHENA_S3_STAGING_DIR}")
logging.info(f"Usando ATHENA_REGION: {ATHENA_REGION}")




def format_filter(items, column):
    if items:
        formatted_items = ", ".join(f"'{item}'" for item in items)
        return f"AND {column} IN ({formatted_items})"
    return ""

def load_from_cache(cache_key):
    cache_file = f"cache_{cache_key}.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        if datetime.now() < datetime.fromisoformat(cache_data['expires']):
            return cache_data['data']
    return None

def save_to_cache(cache_key, data, ttl_hours=24):
    cache_file = f"cache_{cache_key}.json"
    expires = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
    cache_data = {
        'data': data,
        'expires': expires
    }
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)

@st.cache_data(ttl=24*60*60)
def get_static_data():
    logging.info("Iniciando get_static_data")
    cache_key = 'static_data'
    cached_data = load_from_cache(cache_key)
    
    if cached_data is not None and all(key in cached_data for key in ['canais_venda', 'marcas', 'ufs', 'equipes', 'colaboradores','empresas']):
        logging.info(f"Dados completos carregados do cache: {cached_data.keys()}")
        return cached_data
    
    logging.info("Cache incompleto ou não encontrado. Buscando dados do banco...")
    
    canais_venda = get_canais_venda()
    marcas = get_marcas_from_database()
    ufs = get_ufs_from_database()
    equipes = get_team_options()
    colaboradores = get_colaboradores_options()
    empresas = get_empresas_from_database()
    logging.info(f"Número de empresas obtidas: {len(empresas)}")
    
    static_data = {
        'canais_venda': canais_venda,
        'marcas': marcas,
        'ufs': ufs,
        'equipes': equipes,
        'colaboradores': colaboradores,
        'empresas': empresas  # Nova linha
    }
    
    logging.info(f"Dados completos obtidos: {static_data.keys()}")
    logging.debug(f"Número de colaboradores obtidos: {len(colaboradores)}")
    logging.debug(f"Número de empresas obtidas: {len(empresas)}") 
    
    save_to_cache(cache_key, static_data)
    
    return static_data

def get_empresas_from_database():
    query = """
    SELECT DISTINCT nome_empresa_faturamento as empresa 
    FROM "databeautykami".vw_distribuicao_empresa_pedido 
    WHERE cod_empresa_faturamento not in ('9','21')
    ORDER BY 1
    """
    empresas = query_athena(query)['empresa'].tolist()
    logging.info(f"Empresas obtidas do banco de dados: {empresas}")
    return empresas

def get_canais_venda():
    # Assumindo que os canais de venda são fixos
    return ['VAREJO', 'SALÃO']

def get_marcas_from_database():
    query = """
    SELECT DISTINCT marca 
    FROM "databeautykami".vw_distribuicao_item_pedidos 
    ORDER BY marca
    """
    return query_athena(query)['marca'].tolist()

def get_ufs_from_database():
    query = """
    SELECT DISTINCT uf_empresa_faturamento as uf
    FROM databeautykami.vw_distribuicao_empresa_pedido
    WHERE uf_empresa_faturamento IS NOT NULL AND uf_empresa_faturamento != ''
    ORDER BY uf_empresa_faturamento
    """
    result = query_athena(query)
    return result['uf'].tolist() if 'uf' in result.columns else []    

def force_update_static_data():
    logging.debug("Forçando atualização dos dados estáticos")
    canais_venda = get_canais_venda()
    marcas = get_marcas_from_database()
    ufs = get_ufs_from_database()
    equipes = get_team_options()
    empresas = get_empresas_from_database()
    
    static_data = {
        'canais_venda': canais_venda,
        'marcas': marcas,
        'ufs': ufs,
        'equipes': equipes,
        'empresas': empresas
    }
    
    save_to_cache('static_data', static_data)
    logging.debug(f"Dados atualizados e salvos no cache: {static_data.keys()}")
    return static_data

def query_athena(query):
    try:
        boto3.Session().get_credentials().get_frozen_credentials()

        conn = connect(s3_staging_dir=ATHENA_S3_STAGING_DIR, region_name=ATHENA_REGION)
        df = pd.read_sql(query, conn)
        logging.info(f"Query executada com sucesso. Resultado: {df.shape}")
        return df
    except NoCredentialsError:
        logging.error("Não foi possível encontrar credenciais AWS válidas.")
        return pd.DataFrame()
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logging.error(f"Erro do cliente AWS: {error_code} - {error_message}")
        return pd.DataFrame()
    
    except Exception as e:
        logging.error(f"Erro ao executar query no Athena: {str(e)}")
        return pd.DataFrame()   

# Funções cacheadas
@st.cache_data(ttl=3600)
def get_monthly_revenue_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, 
                             selected_brands, selected_nome_colaborador, selected_teams):
    # Os filtros serão acessados diretamente do session_state dentro da função get_monthly_revenue
    return get_monthly_revenue(cod_colaborador, start_date, end_date, selected_channels, 
                             selected_ufs, selected_brands, selected_nome_colaborador, 
                             selected_teams)

@st.cache_data(ttl=3600)
def get_brand_data_cached(cod_colaborador, start_date, end_date, selected_channels, 
                         selected_ufs, selected_nome_colaborador, selected_teams):
    # Adicionar os filtros de carteira/pedido como parte da chave do cache
    filtro_carteira = st.session_state.get('filtro_carteira', True)
    filtro_pedido = st.session_state.get('filtro_pedido', False)
    return get_brand_data(cod_colaborador, start_date, end_date, selected_channels, 
                         selected_ufs, selected_nome_colaborador, selected_teams)

@st.cache_data
def get_unique_customers_period_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams):
    return get_unique_customers_period(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams)


@st.cache_data
def get_abc_curve_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams):
    return get_abc_curve_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams)

#@st.cache_data
#def get_brand_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador,selected_teams):
    #logging.info(f"Chamando get_brand_data_cached com os seguintes parâmetros:")
    #logging.info(f"cod_colaborador: {cod_colaborador}")
    #logging.info(f"start_date: {start_date}")
    #logging.info(f"end_date: {end_date}")
    #logging.info(f"selected_channels: {selected_channels}")
    #logging.info(f"selected_ufs: {selected_ufs}")
    #logging.info(f"selected_nome_colaborador: {selected_nome_colaborador}")
    #return get_brand_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador,selected_teams)

@st.cache_data
def get_channels_and_ufs_cached(cod_colaborador, start_date, end_date):
    return get_channels_and_ufs(cod_colaborador, start_date, end_date)

@st.cache_data
def get_colaboradores_cached(start_date, end_date, selected_channels, selected_ufs):
    return get_colaboradores(start_date, end_date, selected_channels, selected_ufs)

@st.cache_data
def get_rfm_summary_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores,selected_teams):
    logging.info(f"Chamando get_rfm_summary_cached com os seguintes parâmetros:")
    logging.info(f"cod_colaborador: {cod_colaborador}")
    logging.info(f"start_date: {start_date}")
    logging.info(f"end_date: {end_date}")
    logging.info(f"selected_channels: {selected_channels}")
    logging.info(f"selected_ufs: {selected_ufs}")
    logging.info(f"selected_colaboradores: {selected_colaboradores}")
    #logging.info(f"selected_colaboradores: {selected_teams}")
    return get_rfm_summary(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores,selected_teams)

@st.cache_data
def get_rfm_heatmap_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores,selected_teams):
    return get_rfm_heatmap_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores,selected_teams)

@st.cache_data
def get_rfm_segment_clients_cached(cod_colaborador, start_date, end_date, segmentos, selected_channels, selected_ufs, selected_colaboradores,selected_teams):
    return get_rfm_segment_clients(cod_colaborador, start_date, end_date, segmentos, selected_channels, selected_ufs, selected_colaboradores,selected_teams)

@st.cache_data
def load_filter_options(cod_colaborador, start_date, end_date):
    channels, ufs = get_channels_and_ufs(cod_colaborador, start_date, end_date)
    colaboradores = get_colaboradores(start_date, end_date, None, None)
    colaboradores_options = colaboradores['nome_colaborador'].tolist() if not colaboradores.empty else []
    
    # Carregar marcas sem filtros iniciais
    brand_data = get_brand_data(cod_colaborador, start_date, end_date, None, None, None)
    brand_options = brand_data['marca'].unique().tolist() if 'marca' in brand_data.columns else []
    
    return channels, ufs, colaboradores_options, brand_options

# Em utils.py

@st.cache_data
def get_brand_options(start_date, end_date):
    try:
        query = f"""
        SELECT DISTINCT item_pedidos.marca
        FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
        LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
            ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
        WHERE date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
            AND pedidos."desc_abrev_cfop" IN (
                'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
                'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
                'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
                'Venda de mercadoria sujeita ao regime de substituição tributária',
                'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
            )
        ORDER BY item_pedidos.marca
        """
        logging.info(f"Executando query para obter marcas: {query}")
        df = query_athena(query)
        logging.info(f"Query executada com sucesso. Número de marcas obtidas: {len(df)}")
        return df['marca'].tolist() if not df.empty else []
    except Exception as e:
        logging.error(f"Erro ao obter opções de marca: {str(e)}")
        return []


def get_stock_data(start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_empresas):
    channel_filter = f"AND pedidos.canal_venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{','.join(selected_ufs)}')" if selected_ufs else ""
    brand_filter = ""
    empresa_filter = ""
    empresa_filter_stock = ""
    brand_filter_stock = ""

        # Filtro de marcas
    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = format_filter(selected_brands, "item_pedidos.marca") 
        brand_filter_stock = format_filter(selected_brands, "e.marca") 
    
    # Filtro de empresas
    if selected_empresas:
        empresas_str = "', '".join([str(empresa) for empresa in selected_empresas if empresa is not None])
        empresa_filter = format_filter(selected_empresas, "empresa_pedido.nome_empresa_faturamento")    
        empresa_filter_stock = format_filter(selected_empresas, "e.empresa")    



    logging.info(f"Chamada get_stock_data com filtros: channels={selected_channels}, ufs={selected_ufs}, brands={selected_brands}, empresas={selected_empresas}")       


    query = f"""
    WITH vendas AS (
        SELECT 
            upper(item_pedidos.sku) cod_produto, 
            empresa_pedido.cod_empresa_faturamento cod_empresa,
            SUM(item_pedidos.qtd) as quantidade_vendida
        FROM 
            databeautykami.vw_distribuicao_pedidos pedidos
        JOIN 
            databeautykami.vw_distribuicao_item_pedidos item_pedidos ON pedidos.cod_pedido = item_pedidos.cod_pedido
        JOIN 
            databeautykami.vw_distribuicao_empresa_pedido empresa_pedido ON pedidos.cod_pedido = empresa_pedido.cod_pedido
        WHERE 
            pedidos."desc_abrev_cfop" IN (
            'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
            'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
            'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
            'Venda de mercadoria sujeita ao regime de substituição tributária',
            'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
        )
        AND pedidos.operacoes_internas = 'N'
        AND pedidos.dt_faturamento BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        AND empresa_pedido.cod_empresa_faturamento not in ('9','21')
            {channel_filter}
            {uf_filter}
            {brand_filter}
            {empresa_filter}
        GROUP BY 
            upper(item_pedidos.sku),
            empresa_pedido.cod_empresa_faturamento
    ),
        bonificacao AS (
        SELECT            
            upper(item_pedidos.sku) cod_produto,
            empresa_pedido.cod_empresa_faturamento cod_empresa,
            SUM(item_pedidos.qtd) as quantidade_bonificada
            FROM
                "databeautykami"."vw_distribuicao_pedidos" pedidos
            LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
                ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
            LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
                ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
            WHERE
                upper(pedidos."desc_abrev_cfop") in ('BONIFICADO','BONIFICADO STORE','BONIFICADO FORA DO ESTADO','REMESSA EM BONIFICAÇÃO','BRINDE OU DOAÇÃO','BRINDE','CAMPANHA','PROMOCAO')
                AND pedidos.operacoes_internas = 'N'
                AND date(dt_faturamento) BETWEEN date('{start_date}') AND date('{end_date}')
                AND empresa_pedido.cod_empresa_faturamento not in ('9','21')
                {channel_filter}
                {uf_filter}
                {brand_filter}
                {empresa_filter}
            GROUP BY 1, 2
        )

    SELECT 
        e.cod_empresa,
        e.empresa,
        e.uf_empresa,
        upper(e.cod_produto) cod_produto,
        max(e.desc_produto) desc_produto,
        e.cod_marca,
        e.marca,
        e.deposito,
        (e.saldo_estoque) saldo_estoque,
        e.custo_total,
        (e.saldo_estoque*e.custo_total) as valor_total_estoque,
        COALESCE(v.quantidade_vendida, 0) as quantidade_vendida,
        COALESCE(b.quantidade_bonificada, 0) as quantidade_bonificada,
        DATE_DIFF('day', DATE('{start_date}'), DATE('{end_date}')) as dias_periodo
    FROM 
        databeautykami.tbl_varejo_saldo_estoque e
    LEFT JOIN
        vendas v ON upper(e.cod_produto) = v.cod_produto and e.cod_empresa = v.cod_empresa
    LEFT JOIN
        bonificacao b ON upper(e.cod_produto) = b.cod_produto and e.cod_empresa = b.cod_empresa        
    WHERE e.cod_empresa not in ('9','21')
    {empresa_filter_stock}
    {brand_filter_stock}
    and upper(e.cod_produto) not in (Select upper(cod_produto) from databeautykami.tbl_distribuicao_material_apoio)
    GROUP BY 1,2,3,4,6,7,8,9,10,11,12,13,14
    """
    logging.info(f"Executando query para get_stock_data: {query}")
    return query_athena(query)

def get_stock_material_apoio_trade(start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_empresas):
    channel_filter = f"AND pedidos.canal_venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{','.join(selected_ufs)}')" if selected_ufs else ""
    brand_filter = ""
    empresa_filter = ""
    empresa_filter_stock = ""
    brand_filter_stock = ""

        # Filtro de marcas
    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = format_filter(selected_brands, "item_pedidos.marca") 
        brand_filter_stock = format_filter(selected_brands, "e.marca") 
    
    # Filtro de empresas
    if selected_empresas:
        empresas_str = "', '".join([str(empresa) for empresa in selected_empresas if empresa is not None])
        empresa_filter = format_filter(selected_empresas, "empresa_pedido.nome_empresa_faturamento")    
        empresa_filter_stock = format_filter(selected_empresas, "e.empresa")    



    logging.info(f"Chamada get_stock_data com filtros: channels={selected_channels}, ufs={selected_ufs}, brands={selected_brands}, empresas={selected_empresas}")       


    query = f"""
    WITH vendas AS (
        SELECT 
            upper(item_pedidos.sku) cod_produto, 
            empresa_pedido.cod_empresa_faturamento cod_empresa,
            pedidos."desc_abrev_cfop" nop,
            SUM(item_pedidos.qtd) as quantidade_vendida
        FROM 
            databeautykami.vw_distribuicao_pedidos pedidos
        JOIN 
            databeautykami.vw_distribuicao_item_pedidos item_pedidos ON pedidos.cod_pedido = item_pedidos.cod_pedido
        JOIN 
            databeautykami.vw_distribuicao_empresa_pedido empresa_pedido ON pedidos.cod_pedido = empresa_pedido.cod_pedido
        WHERE 
            pedidos.operacoes_internas = 'N'
        AND pedidos.dt_faturamento BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        AND empresa_pedido.cod_empresa_faturamento not in ('9','21')
            {channel_filter}
            {uf_filter}
            {brand_filter}
            {empresa_filter}
        GROUP BY 
            upper(item_pedidos.sku),
            empresa_pedido.cod_empresa_faturamento,
            pedidos."desc_abrev_cfop"

    )       

    SELECT 
        e.cod_empresa,
        e.empresa,
        e.uf_empresa,
        nop,
        m.desc_abrev tipo_material,
        upper(e.cod_produto) cod_produto,
        max(e.desc_produto) desc_produto,
        e.cod_marca,
        e.marca,
        e.deposito,
        (e.saldo_estoque) saldo_estoque,
        e.custo_total,
        (e.saldo_estoque*e.custo_total) as valor_total_estoque,
        COALESCE(v.quantidade_vendida, 0) as quantidade_utilizada,
        DATE_DIFF('day', DATE('{start_date}'), DATE('{end_date}')) as dias_periodo
    FROM 
        databeautykami.tbl_varejo_saldo_estoque e
    INNER JOIN databeautykami.tbl_distribuicao_material_apoio m ON
        e.cod_produto = m.cod_produto
    LEFT JOIN
        vendas v ON upper(e.cod_produto) = v.cod_produto and e.cod_empresa = v.cod_empresa
    WHERE e.cod_empresa not in ('9','21')
    {empresa_filter_stock}
    {brand_filter_stock}
    -- and upper(e.cod_produto) in (Select upper(cod_produto) from databeautykami.tbl_distribuicao_material_apoio)
    GROUP BY 1,2,3,4,5,6,8,9,10,11,12,13,14,15
    """
    logging.info(f"Executando query para get_stock_material_apoio_trade: {query}")
    return query_athena(query)


def calculate_stock_metrics(df):
    logging.info("Iniciando cálculo de métricas de estoque")
    logging.info(f"Colunas disponíveis no DataFrame inicial: {df.columns}")

    if 'custo_total' not in df.columns or 'saldo_estoque' not in df.columns:
        logging.error("Colunas necessárias não encontradas no DataFrame")
        raise KeyError("As colunas 'custo_total' e 'saldo_estoque' são necessárias para o cálculo")

    # Calcular valor_total_estoque
    df['valor_total_estoque'] = df['custo_total'] * df['saldo_estoque']
    
    # Calcular giro de estoque anualizado
    df['giro_estoque_anual'] = (df['quantidade_vendida'] / df['dias_periodo']) * 365 / df['saldo_estoque'].where(df['saldo_estoque'] != 0, 1)
    
    # Calcular cobertura de estoque em dias
    df['cobertura_estoque'] = df['saldo_estoque'] / (df['quantidade_vendida'] / df['dias_periodo']).where(df['quantidade_vendida'] != 0, 1)
    
    # Calcular estoque em excesso (assumindo que 90 dias de cobertura é o máximo desejado)
    df['estoque_excesso'] = df.apply(lambda row: max(0, row['saldo_estoque'] - (row['quantidade_vendida'] / row['dias_periodo'] * 90)), axis=1)

    # Agrupar por produto para eliminar possíveis duplicatas
    #df = df.groupby(['cod_produto', 'marca', 'empresa', 'uf_empresa']).agg({
        #'desc_produto': 'max',
        #'saldo_estoque': 'sum',
        #'quantidade_vendida': 'sum',
        #'valor_total_estoque': 'sum',
        #'estoque_excesso': 'sum',
        #'giro_estoque_anual': 'mean',
        #'cobertura_estoque': 'mean'
   # }).reset_index()

    # Calcular a curva ABC
    df_sorted = df.sort_values('valor_total_estoque', ascending=False)
    df_sorted['valor_acumulado'] = df_sorted['valor_total_estoque'].cumsum()
    total_valor = df_sorted['valor_total_estoque'].sum()
    df_sorted['percentual_acumulado'] = df_sorted['valor_acumulado'] / total_valor
    df_sorted['curva'] = df_sorted['percentual_acumulado'].apply(lambda x: 'A' if x <= 0.8 else ('B' if x <= 0.95 else 'C'))

    # Mesclar a coluna 'curva' de volta ao DataFrame original
    df = df.merge(df_sorted[['cod_produto', 'curva']], on='cod_produto', how='left')

    logging.info(f"Métricas calculadas. Colunas finais: {df.columns}")
    logging.info(f"Amostra dos dados finais:\n{df.head()}")
    
    if 'curva' not in df.columns:
        logging.error("A coluna 'curva' não foi criada corretamente")
    else:
        logging.info(f"Distribuição da curva ABC:\n{df['curva'].value_counts()}")

    return df
@st.cache_data
def get_stock_turnover_data(start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_colaboradores, selected_teams):
    query = f"""
    WITH vendas AS (
        SELECT 
            upper(item_pedidos.sku) as cod_produto, 
            SUM(item_pedidos.qtd) as quantidade_vendida
        FROM 
            databeautykami.vw_distribuicao_pedidos pedidos
        JOIN 
            databeautykami.vw_distribuicao_item_pedidos item_pedidos ON pedidos.cod_pedido = item_pedidos.cod_pedido
        JOIN 
            databeautykami.vw_distribuicao_empresa_pedido empresa_pedido ON pedidos.cod_pedido = empresa_pedido.cod_pedido
        WHERE 
            pedidos.dt_faturamento BETWEEN '{start_date}' AND '{end_date}'
            {f"AND pedidos.canal_venda IN ('{','.join(selected_channels)}')" if selected_channels else ""}
            {f"AND empresa_pedido.uf_empresa_faturamento IN ('{','.join(selected_ufs)}')" if selected_ufs else ""}
            {f"AND item_pedidos.marca IN ('{','.join(selected_brands)}')" if selected_brands else ""}
            {f"AND empresa_pedido.nome_colaborador_atual IN ('{','.join(selected_colaboradores)}')" if selected_colaboradores else ""}
            {f"AND empresa_pedido.equipes IN ('{','.join(selected_teams)}')" if selected_teams else ""}
        GROUP BY 
            upper(item_pedidos.sku)
    )
    SELECT 
        e.cod_produto,
        e.desc_produto,
        e.marca,
        e.saldo_estoque,
        e.custo_total as valor_estoque,
        COALESCE(v.quantidade_vendida, 0) as quantidade_vendida,
        CASE 
            WHEN e.saldo_estoque > 0 THEN COALESCE(v.quantidade_vendida, 0) / e.saldo_estoque
            ELSE 0 
        END as giro_estoque
    FROM 
        "databeautykami"."tbl_varejo_saldo_estoque" e
    LEFT JOIN
        vendas v ON e.cod_produto = v.cod_produto
    ORDER BY
        giro_estoque DESC
    """
    logging.info(f"Executando query para get_stock_turnover_data: {query}")
    return query_athena(query)

@st.cache_data
def get_stock_purchases(start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_colaboradores, selected_teams):
    channel_filter = f"AND r.canal_venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND r.uf_empresa IN ('{','.join(selected_ufs)}')" if selected_ufs else ""
    brand_filter = f"AND r.marca IN ('{','.join(selected_brands)}')" if selected_brands else ""
    colaborador_filter = f"AND r.nome_colaborador IN ('{','.join(selected_colaboradores)}')" if selected_colaboradores else ""
    team_filter = format_filter(selected_teams, "r.equipes")

    query = f"""
    SELECT 
        r.marca,
        SUM(r.quantidade) as quantidade_comprada
    FROM 
        databeautykami.tbl_varejo_recebimento r
    WHERE 
        r.dt_movimento BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {colaborador_filter}
        {team_filter}
    GROUP BY 
        r.marca
    """
    logging.info(f"Executando query para get_stock_purchases: {query}")
    return query_athena(query)


def get_abc_curve_data_with_stock(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams, selected_empresas):
    # Inicialização de variáveis (mesma lógica da função original)
    brand_filter = ""
    channel_filter = ""
    uf_filter = ""
    team_filter = ""
    colaborador_filter = ""
    empresa_filter = ""
    empresa_filter_stock = ""
    brand_filter_stock = ""

    # Filtros (mesma lógica da função original)    
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = f"AND pedidos.canal_venda IN ('{channels_str}')"
    
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{ufs_str}')"
    
    if selected_teams:
        teams_str = "', '".join(selected_teams)
        team_filter = format_filter(selected_teams, "empresa_pedido.equipes")

    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        colaborador_filter = f"AND ( empresa_pedido.nome_colaborador_atual IN ('{nome_str}') OR empresa_pedido.nome_colaborador_pedido IN ('{nome_str}') )"

    if selected_empresas:
        empresas_str = "', '".join(selected_empresas)
        empresa_filter = format_filter(selected_empresas, "empresa_pedido.nome_empresa_faturamento") 
        empresa_filter_stock = format_filter(selected_empresas, "e.empresa")    

    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = format_filter(selected_brands, "item_pedidos.marca") 
        brand_filter_stock = format_filter(selected_brands, "e.marca")           

    #empresa_filter = f"AND empresa_pedido.empresa IN ({','.join([f"'{e}'" for e in selected_empresas])})" if selected_empresas else ""        

    query = f"""
    WITH produto_sales AS (
      SELECT
        upper(item_pedidos.sku) sku,
        MAX(item_pedidos.desc_produto) as nome_produto,
        item_pedidos.marca,
        SUM(item_pedidos.preco_desconto_rateado) AS faturamento_liquido,
        SUM(item_pedidos.qtd) AS quantidade_vendida
      FROM
        "databeautykami"."vw_distribuicao_pedidos" pedidos
      LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
        ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
      LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
        ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
      WHERE
        pedidos."desc_abrev_cfop" IN (
            'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
            'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
            'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
            'Venda de mercadoria sujeita ao regime de substituição tributária',
            'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
        )
        AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        AND pedidos.operacoes_internas = 'N'
        AND empresa_pedido.cod_empresa_faturamento not in ('9','21')
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {empresa_filter}
      GROUP BY 1,3
    ),
    bonificacao AS (
        SELECT    
            upper(item_pedidos.sku) sku,        
            MAX(item_pedidos.desc_produto) as nome_produto,
            item_pedidos.marca,
            MAX(0.00) AS faturamento_liquido,
            SUM(item_pedidos.qtd) AS quantidade_bonificada
            FROM
                "databeautykami"."vw_distribuicao_pedidos" pedidos
            LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
                ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
            LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
                ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
            WHERE
                upper(pedidos."desc_abrev_cfop") in ('BONIFICADO','BONIFICADO STORE','BONIFICADO FORA DO ESTADO','REMESSA EM BONIFICAÇÃO','BRINDE OU DOAÇÃO','BRINDE','CAMPANHA','PROMOCAO')
                AND pedidos.operacoes_internas = 'N'
                AND date(dt_faturamento) BETWEEN date('{start_date}') AND date('{end_date}')
                AND empresa_pedido.cod_empresa_faturamento not in ('9','21')
                {channel_filter}
                {uf_filter}
                {brand_filter}
                {empresa_filter}
            GROUP BY 1, 3
        ),

    produto_abc AS (
      SELECT
        produto_sales.*,
        COALESCE(bonificacao.quantidade_bonificada,0) as quantidade_bonificada,
        SUM(produto_sales.faturamento_liquido) OVER () AS total_faturamento
      FROM produto_sales LEFT JOIN bonificacao ON produto_sales.sku = bonificacao.sku
    ),
    estoque_info AS (
      SELECT
        upper(cod_produto) as sku,
        max(desc_produto) as nome_produto,
        marca,
        SUM(saldo_estoque) as saldo_estoque,
        SUM(custo_total*saldo_estoque) as valor_estoque,
         SUM(SUM(custo_total * saldo_estoque)) OVER () AS total_valor_estoque,
        SUM(SUM(custo_total * saldo_estoque)) OVER (ORDER BY SUM(custo_total * saldo_estoque) DESC) / SUM(SUM(custo_total * saldo_estoque)) OVER () AS estoque_acumulado,
        CASE
          WHEN SUM(SUM(custo_total * saldo_estoque)) OVER (ORDER BY SUM(custo_total * saldo_estoque) DESC) / SUM(SUM(custo_total * saldo_estoque)) OVER () <= 0.8 THEN 'A'
          WHEN SUM(SUM(custo_total * saldo_estoque)) OVER (ORDER BY SUM(custo_total * saldo_estoque) DESC) / SUM(SUM(custo_total * saldo_estoque)) OVER () <= 0.95 THEN 'B'
          ELSE 'C'
        END AS curva
      FROM
        "databeautykami"."tbl_varejo_saldo_estoque" e
      WHERE cod_empresa not in ('9','21')
      {empresa_filter_stock}
      {brand_filter_stock}
      and upper(cod_produto) not in (Select upper(cod_produto) from databeautykami.tbl_distribuicao_material_apoio)

      GROUP BY
        upper(cod_produto),marca
    )
    SELECT 
        COALESCE(p.sku,e.sku) as sku,
        COALESCE(p.nome_produto,e.nome_produto) as nome_produto,
        COALESCE(p.marca,e.marca) as marca,
        COALESCE(p.quantidade_vendida,0) as quantidade_vendida,
        COALESCE(p.quantidade_bonificada,0) as quantidade_bonificada,
        COALESCE(p.total_faturamento,0) as total_faturamento,
        COALESCE(e.estoque_acumulado,0) as estoque_acumulado,
        COALESCE(e.curva,'') as curva,
        COALESCE(e.saldo_estoque, 0) as saldo_estoque,
        COALESCE(e.valor_estoque, 0) as valor_estoque
    FROM 
      estoque_info e
    LEFT JOIN
      produto_abc p  ON p.sku = e.sku
    ORDER BY p.faturamento_liquido DESC
    """
    
    logging.info(f"Query executada para Curva ABC com estoque: {query}")
    logging.info(f"Parâmetros de entrada:")
    logging.info(f"cod_colaborador: {cod_colaborador}")
    logging.info(f"start_date: {start_date}")
    logging.info(f"end_date: {end_date}")
    logging.info(f"selected_channels: {selected_channels}")
    logging.info(f"selected_ufs: {selected_ufs}")
    logging.info(f"selected_brands: {selected_brands}")
    logging.info(f"selected_nome_colaborador: {selected_nome_colaborador}")
    logging.info(f"selected_teams: {selected_teams}")
    logging.info(f"selected_teams: {selected_empresas}")

    df = query_athena(query)
    if df is not None:
        logging.info(f"DataFrame resultante: shape={df.shape}, colunas={df.columns.tolist()}")
        if not df.empty:
            logging.info(f"Primeiras linhas:\n{df.head()}")
        else:
            logging.warning("DataFrame está vazio após a query")
    else:
        logging.warning("Query retornou None")
    return df if df is not None else pd.DataFrame()

def get_abc_curve_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams):
    # Inicialização dos filtros
    channel_filter = ""
    uf_filter = ""
    brand_filter = ""
    team_filter = ""
    colaborador_filter = ""

    # Aplicar filtros
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = f"AND pedidos.canal_venda IN ('{channels_str}')"
    
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{ufs_str}')"
    
    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = f"AND item_pedidos.marca IN ('{brands_str}')"

    if selected_teams:
        teams_str = "', '".join(selected_teams)
        team_filter = format_filter(selected_teams, "empresa_pedido.equipes")
    
    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        colaborador_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"

    query = f"""
    WITH vendas AS (
        SELECT
            upper(item_pedidos.sku) as sku,
            max(item_pedidos.desc_produto) as nome_produto,
            item_pedidos.marca,
            empresa_pedido.uf_empresa_faturamento as uf_empresa,
            empresa_pedido.nome_empresa_faturamento as empresa,
            SUM(item_pedidos.preco_desconto_rateado) as faturamento_liquido,
            SUM(item_pedidos.qtd) as quantidade_vendida
        FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
        LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
            ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
        LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
            ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
        WHERE pedidos."desc_abrev_cfop" IN (
            'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
            'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
            'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
            'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
        )
        AND pedidos.operacoes_internas = 'N'
        AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {colaborador_filter}
        {team_filter}
        GROUP BY 1,3,4,5
    ),
    bonificacao AS (
        SELECT
            upper(item_pedidos.sku) as sku,
            SUM(item_pedidos.qtd) as quantidade_bonificada
        FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
        LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
            ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
        LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
            ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
        WHERE upper(pedidos."desc_abrev_cfop") in (
            'BONIFICADO','BONIFICADO STORE','BONIFICADO FORA DO ESTADO',
            'REMESSA EM BONIFICAÇÃO','BRINDE OU DOAÇÃO','BRINDE','CAMPANHA','PROMOCAO'
        )
        AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {colaborador_filter}
        {team_filter}
        GROUP BY 1
    ),
    estoque AS (
        SELECT
            upper(e.cod_produto) as sku,
            max(e.desc_produto) as nome_produto,
            e.marca,
            e.empresa,
            e.uf_empresa,
            SUM(e.saldo_estoque) as saldo_estoque,
            AVG(e.custo_total) as custo_total,
            SUM(e.saldo_estoque * e.custo_total) as valor_estoque
        FROM "databeautykami"."tbl_varejo_saldo_estoque" e
        WHERE e.cod_empresa not in ('9','21')
        GROUP BY 1,3,4,5
    ),  
    faturamento_total AS (
        SELECT 
            sku,
            uf_empresa as uf,
            SUM(faturamento_liquido) as faturamento_liquido_sku,
            SUM(SUM(faturamento_liquido)) OVER (PARTITION BY uf_empresa ORDER BY SUM(faturamento_liquido) DESC) as fat_acumulado,
            SUM(SUM(faturamento_liquido)) OVER (PARTITION BY uf_empresa) as total_faturamento
        FROM vendas
        GROUP BY sku, uf_empresa
    )
    ,
    abc_classification AS (
        SELECT vendas.*,
            faturamento_total.fat_acumulado,
            faturamento_total.total_faturamento,
            (fat_acumulado / total_faturamento) as proporcao_faturamento,
            CASE
                WHEN (fat_acumulado / total_faturamento) <= 0.8 THEN 'A'
                WHEN (fat_acumulado / total_faturamento) <= 0.95 THEN 'B'
                ELSE 'C'
            END as curva
        FROM vendas
        JOIN faturamento_total 
            ON vendas.sku = faturamento_total.sku
            AND vendas.uf_empresa = faturamento_total.uf
    )
    SELECT 
        COALESCE(a.sku, e.sku) as sku,
        COALESCE(a.nome_produto, e.nome_produto) as nome_produto,
        COALESCE(a.marca, e.marca) as marca,
        COALESCE(a.uf_empresa, e.uf_empresa) as uf_empresa,
        COALESCE(a.empresa, e.empresa) as empresa,
        COALESCE(a.faturamento_liquido, 0) as faturamento_liquido,
        COALESCE(a.quantidade_vendida, 0) as quantidade_vendida,
        COALESCE(b.quantidade_bonificada, 0) as quantidade_bonificada,
        COALESCE(a.curva, 'C') as curva,
        COALESCE(e.saldo_estoque, 0) as saldo_estoque,
        COALESCE(e.valor_estoque, 0) as valor_estoque
    FROM abc_classification a
    FULL OUTER JOIN estoque e 
        ON a.sku = e.sku 
        AND a.uf_empresa = e.uf_empresa 
        AND a.empresa = e.empresa
    LEFT JOIN bonificacao b ON COALESCE(a.sku, e.sku) = b.sku
    WHERE e.saldo_estoque > 0 OR a.sku IS NOT NULL
    ORDER BY faturamento_liquido DESC, valor_estoque DESC;   
    """

    logging.info(f"Executando query ABC Regional: {query}")
    return query_athena(query)
    
def get_monthly_revenue(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams):
    # Inicialização de variáveis
    brand_filter = ""
    channel_filter = ""
    uf_filter = ""
    colaborador_filter = ""
    group_by_cols = "1, fator"
    group_by_cols_acum = "1"
    group_by_cols_acum_2 = "1,2"
    select_cols_subquery = ""
    select_cols_main = ""
    select_cols_subquery_alias = ""

    # Filtro de marcas
    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = f"AND item_pedidos.marca IN ('{brands_str}')"
    
    # Filtro de canais de venda
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = f"AND pedidos.canal_venda IN ('{channels_str}')"
    
    # Filtro de UFs
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{ufs_str}')"
    
    # Filtro e colunas adicionais para colaborador específico
    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        conditions = []
        
        # Acessar os valores do session_state dentro da função
        filtro_carteira = st.session_state.get('filtro_carteira', True)
        filtro_pedido = st.session_state.get('filtro_pedido', False)
        
        if filtro_carteira:
            conditions.append(f"empresa_pedido.nome_colaborador_atual IN ('{nome_str}')")
        if filtro_pedido:
            conditions.append(f"empresa_pedido.nome_colaborador_pedido IN ('{nome_str}')")
        
        if conditions:
            colaborador_filter = f"AND ({' OR '.join(conditions)})"
        else:
            colaborador_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"
       
        group_by_cols = "1, 2, 3, fator"
        group_by_cols_acum = " 1,2,3"
        group_by_cols_acum_2 = " 1,2,3,4"
    
        select_cols_subquery = """
        empresa_pedido.nome_colaborador_atual vendedor,
        empresa_pedido.cod_colaborador_atual cod_colaborador,
        """
        select_cols_subquery_alias = """
        vendedor,
        cod_colaborador,
        """
        select_cols_main = """
        f.vendedor,
        f.cod_colaborador,
    """
    else:
        colaborador_filter = ""
        group_by_cols = "1,fator"
        group_by_cols_acum = "1"
        select_cols_subquery = ""
        select_cols_subquery_alias = ""
        select_cols_main = ""
        nome_filter = ""

    if selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        nome_filter = f"AND ( empresa_pedido.nome_colaborador_atual IN ('{nome_str}') OR empresa_pedido.nome_colaborador_pedido IN ('{nome_str}') )"

    team_filter = format_filter(selected_teams, "empresa_pedido.equipes")

    
    query = f"""
    WITH bonificacao AS (
        SELECT 
            dt_faturamento as data_ref,  -- Mudamos para data original
            {select_cols_subquery_alias}
            ROUND(SUM(valor_bonificacao_ajustada),2) valor_bonificacao
    FROM (
            SELECT
                dt_faturamento,  -- Removemos o DATE_TRUNC
                {select_cols_subquery}
                CASE WHEN fator IS NULL Then ROUND(SUM(item_pedidos.preco_total), 2)
                Else ROUND(SUM(item_pedidos.preco_total)/1,2) END AS valor_bonificacao_ajustada
            FROM
                "databeautykami"."vw_distribuicao_pedidos" pedidos
            LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
                ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
            LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
                ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
            LEFT JOIN "databeautykami".tbl_distribuicao_bonificacao bonificacao
                ON date(bonificacao.mes_ref) = DATE_TRUNC('month', dt_faturamento)
            LEFT JOIN "databeautykami".tbl_varejo_marca marca ON marca.cod_marca = bonificacao.cod_marca
                and upper(trim(marca.desc_abrev)) = upper(trim(item_pedidos.marca))
            WHERE
                upper(pedidos."desc_abrev_cfop") in ('BONIFICADO','BONIFICADO STORE','BONIFICADO FORA DO ESTADO','REMESSA EM BONIFICAÇÃO','BRINDE OU DOAÇÃO','BRINDE','CAMPANHA','PROMOCAO')
                AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
                AND pedidos.operacoes_internas = 'N'
                {colaborador_filter}
                {channel_filter}
                {uf_filter}
                {brand_filter}  
                {team_filter}
            GROUP BY  {group_by_cols}  -- Alterado para usar dt_faturamento
        )   boni
    group by  {group_by_cols_acum}  -- Alterado para usar data_ref
    ),
   devolucao AS (
            SELECT
                dt_faturamento as data_ref,  -- Mudamos para data original
                {select_cols_subquery}
                SUM(item_pedidos.preco_total) AS valor_devolucao
            FROM
                "databeautykami"."vw_distribuicao_pedidos" pedidos
            LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
                ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
            LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
                ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"            
            WHERE
                (pedidos."desc_abrev_cfop") in (
                            'ENTRADA DE DEVOLUÇÃO DE VENDA COM ST',
                            'DEVOLUÇÃO DE VENDA FORA DO ESTADO',
                            'DEVOLUÇÃO DE COMPRA ',
                            'Devolução de compra para comercialização em operação com mercadoria sujeita ao regime de substituição tributária',
                            'DEVOLUÇÃO DE VENDA ESTADUAL ST',
                            'DEV. VENDA ',
                            'DEVOLUÇÃO DE COMPRA P/ COMERCIALIZACAO ST',
                            'ENTRADA DE DEVOLUÇÃO DE VENDA',
                            'DEV. COMPRA P/ COMERCIALIZACAO COM ST',
                            'DEV. VENDA MERC.ADQ. BRASIL DENTRO ESTADO',
                            'DEVOLUÇÃO DE VENDA',
                            'DEVOLUÇÃO DE VENDA DENTRO DO ESTADO ST'
                )
                AND pedidos.operacoes_internas = 'N'
                AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
                {colaborador_filter}
                {channel_filter}
                {uf_filter}
                {brand_filter}  
                {team_filter}           
            group by {group_by_cols_acum}  -- Alterado para usar dt_faturamento
    )

    SELECT
        f.data_ref,
        f.mes_ref,  -- Mantemos a coluna mes_ref para compatibilidade
        {select_cols_main}
        f.faturamento_bruto,
        f.faturamento_liquido,
        f.desconto,
        COALESCE(b.valor_bonificacao, 0) AS valor_bonificacao,
        COALESCE(d.valor_devolucao, 0) AS valor_devolucao,
        f.custo_total,
        f.positivacao,
        f.qtd_pedido,
        f.qtd_itens,
        f.qtd_sku,
        f.qtd_marcas,
        f.Ticket_Medio_Positivacao,
        f.Ticket_Medio_Pedidos,
        CASE 
            WHEN f.custo_total > 0 THEN ((f.faturamento_liquido - f.custo_total) / f.custo_total) * 100 
            ELSE 0 
        END AS markup_percentual
    FROM (
    SELECT
        pedidos.dt_faturamento as data_ref,
        DATE_TRUNC('month', pedidos.dt_faturamento) mes_ref,  -- Mantemos para compatibilidade
        {select_cols_subquery}
        ROUND(SUM(item_pedidos."preco_total"), 2) AS "faturamento_bruto",
        ROUND(SUM(item_pedidos."preco_desconto_rateado"), 2) AS "faturamento_liquido",
        ROUND(SUM(item_pedidos.preco_total) - SUM(item_pedidos.preco_desconto_rateado), 2) AS desconto,
        ROUND(SUM(COALESCE(cmv.custo_medio, 0) * item_pedidos.qtd), 2) AS custo_total,
        COUNT(DISTINCT pedidos.cpfcnpj) AS "positivacao",
        COUNT(DISTINCT pedidos.cod_pedido) AS "qtd_pedido",
        SUM(item_pedidos.qtd) AS qtd_itens,
        COUNT(DISTINCT item_pedidos.cod_produto) AS qtd_sku,
        COUNT(DISTINCT item_pedidos.marca) AS qtd_marcas,
        ROUND(SUM(item_pedidos."preco_desconto_rateado") / NULLIF(COUNT(DISTINCT pedidos.cpfcnpj), 0), 2) AS Ticket_Medio_Positivacao,
        ROUND(SUM(item_pedidos."preco_desconto_rateado") / NULLIF(COUNT(DISTINCT pedidos.cod_pedido), 0), 2) AS Ticket_Medio_Pedidos
    FROM
        "databeautykami"."vw_distribuicao_pedidos" pedidos
    LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
        ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
    LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
        ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
    LEFT JOIN (
SELECT
            cod_pedido,
            cod_produto,
            mes_ref,
            SUM(custo_medio) as custo_medio
    FROM (
            SELECT 
                cod_pedido,
                cod_produto,
                DATE_TRUNC('month', dt_faturamento) mes_ref,
                CASE WHEN fator IS NULL Then ROUND(SUM(qtd * custo_unitario) / NULLIF(SUM(qtd), 0), 2)
                Else ROUND(SUM(qtd * (custo_unitario/1)) / NULLIF(SUM(qtd), 0), 2)  END custo_medio
            FROM "databeautykami".tbl_varejo_cmv left join "databeautykami".tbl_distribuicao_bonificacao
            ON tbl_varejo_cmv.cod_marca = tbl_distribuicao_bonificacao.cod_marca
            and DATE_TRUNC('month', dt_faturamento) = date(tbl_distribuicao_bonificacao.mes_ref)
            GROUP BY 1, 2, 3, fator 
            UNION ALL 
            SELECT
                cod_pedido,
                codprod,
                DATE_TRUNC('month', dtvenda) mes_ref,
                CASE WHEN fator IS NULL Then ROUND(SUM(quant * custo) / NULLIF(SUM(quant), 0), 2)
                Else ROUND(SUM(quant * (custo/1)) / NULLIF(SUM(quant), 0), 2)  END custo_medio
            FROM "databeautykami".tbl_salao_pedidos_salao left join "databeautykami".tbl_distribuicao_bonificacao
            ON DATE_TRUNC('month', dtvenda) = date(tbl_distribuicao_bonificacao.mes_ref)
            AND ( trim(upper(tbl_salao_pedidos_salao.categoria)) = trim(upper(tbl_distribuicao_bonificacao.marca))
                  OR substring(replace(upper(tbl_salao_pedidos_salao.categoria),'-',''),1,4) = upper(tbl_distribuicao_bonificacao.marca)
                  )
            where fator is not null
            GROUP BY 1, 2, 3 , fator   
            ) cmv_aux
            group by 1,2,3
    ) cmv ON pedidos.cod_pedido = cmv.cod_pedido 
        AND item_pedidos.sku = cmv.cod_produto 
        AND DATE_TRUNC('month', pedidos.dt_faturamento) = cmv.mes_ref
    WHERE
        pedidos."desc_abrev_cfop" IN (
            'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
            'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
            'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
            'Venda de mercadoria sujeita ao regime de substituição tributária',
            'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
        )
        AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        AND pedidos.operacoes_internas = 'N'
        AND (pedidos."origem" IN ('egestor','uno'))        
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {team_filter}
    group by {group_by_cols_acum_2}  -- Incluímos dt_faturamento no group by
    ) f
    LEFT JOIN bonificacao b ON f.data_ref = b.data_ref 
        {' AND f.cod_colaborador = b.cod_colaborador' if cod_colaborador or selected_nome_colaborador else ''}
    LEFT JOIN devolucao d ON f.data_ref = d.data_ref 
        {' AND f.cod_colaborador = d.cod_colaborador' if cod_colaborador or selected_nome_colaborador else ''}        
    ORDER BY f.data_ref{', f.vendedor' if cod_colaborador or selected_nome_colaborador else ''}
    """
    
    logging.info(f"Query executada: {query}")
    logging.info(f"Parâmetros de entrada:")
    logging.info(f"cod_colaborador: {cod_colaborador}")
    logging.info(f"start_date: {start_date}")
    logging.info(f"end_date: {end_date}")
    logging.info(f"selected_channels: {selected_channels}")
    logging.info(f"selected_ufs: {selected_ufs}")
    logging.info(f"selected_brands: {selected_brands}")
    logging.info(f"selected_nome_colaborador: {selected_nome_colaborador}")
    logging.info(f"selected_teams: {selected_teams}")

    logging.info(f"Filtros aplicados:")
    logging.info(f"colaborador_filter: {colaborador_filter}")
    logging.info(f"channel_filter: {channel_filter}")
    logging.info(f"uf_filter: {uf_filter}")
    logging.info(f"brand_filter: {brand_filter}")

    logging.info(f"Filtro de colaborador aplicado: {colaborador_filter}")
    logging.info(f"Código do colaborador: {cod_colaborador}")
    logging.info(f"Nome do colaborador selecionado: {selected_nome_colaborador}")
    
    df = query_athena(query)
    if df is not None:
        logging.info(f"DataFrame resultante: shape={df.shape}, colunas={df.columns.tolist()}")
        if not df.empty:
            logging.info(f"Primeiras linhas:\n{df.head()}")
        else:
            logging.warning("DataFrame está vazio após a query")
    else:
        logging.warning("Query retornou None")
    return df if df is not None else pd.DataFrame()

def get_unique_customers_period(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams):
    
    brand_filter = ""
    channel_filter = ""
    uf_filter = ""
    colaborador_filter = ""

    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        #colaborador_filter = f"AND ( empresa_pedido.nome_colaborador_atual IN ('{nome_str}') OR empresa_pedido.nome_colaborador_pedido IN ('{nome_str}') )"
        colaborador_filter = build_colaborador_filter(
            cod_colaborador, 
            selected_nome_colaborador,
            st.session_state.get('filtro_carteira', True),
            st.session_state.get('filtro_pedido', False)
        )

    channel_filter = f"AND pedidos.canal_venda IN ('{', '.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{', '.join(selected_ufs)}')" if selected_ufs else ""
    #brand_filter = f"AND item_pedidos.marca IN ('{', '.join(selected_brands)}')" if selected_brands else ""
    team_filter = format_filter(selected_teams, "empresa_pedido.equipes")

    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = f"AND item_pedidos.marca IN ('{brands_str}')"


    query = f"""
    SELECT COUNT(DISTINCT pedidos.cpfcnpj) AS clientes_unicos
    FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
    LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
        ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
    LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
        ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
    WHERE
        pedidos."desc_abrev_cfop" IN (
            'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
            'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
            'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
            'Venda de mercadoria sujeita ao regime de substituição tributária',
            'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
        )
        AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        AND pedidos.operacoes_internas = 'N'
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {team_filter}
    """
    
    df = query_athena(query)
    logging.info(f"Query executada clientes únicos: {query}")
    return df['clientes_unicos'].iloc[0] if not df.empty else 0

@st.cache_data(ttl=3600)
def get_weighted_markup(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, 
                       selected_brands, selected_nome_colaborador, selected_teams):
    """
    Calcula o markup ponderado pelo faturamento de cada SKU
    """
    brand_filter = ""
    channel_filter = ""
    uf_filter = ""
    colaborador_filter = ""

    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        #colaborador_filter = f"AND ( empresa_pedido.nome_colaborador_atual IN ('{nome_str}') OR empresa_pedido.nome_colaborador_pedido IN ('{nome_str}') )"
        colaborador_filter = build_colaborador_filter(
            cod_colaborador, 
            selected_nome_colaborador,
            st.session_state.get('filtro_carteira', True),
            st.session_state.get('filtro_pedido', False)
        )

    if selected_channels:
        channel_filter = f"AND pedidos.canal_venda IN ('{', '.join(selected_channels)}')"
    
    if selected_ufs:
        uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{', '.join(selected_ufs)}')"
    
    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = f"AND item_pedidos.marca IN ('{brands_str}')"

    team_filter = format_filter(selected_teams, "empresa_pedido.equipes")

    query = f"""
    WITH dados_sku AS (
        SELECT 
            item_pedidos.sku,
            item_pedidos.preco_desconto_rateado as faturamento_liquido,
            COALESCE(cmv.custo_medio, 0) * item_pedidos.qtd as custo_total
        FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
        LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
            ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
        LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
            ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
        LEFT JOIN (
            SELECT
                cod_pedido,
                cod_produto,
                mes_ref,
                SUM(custo_medio) as custo_medio
            FROM (
                SELECT 
                    cod_pedido,
                    cod_produto,
                    DATE_TRUNC('month', dt_faturamento) mes_ref,
                    CASE 
                        WHEN fator IS NULL Then ROUND(SUM(qtd * custo_unitario) / NULLIF(SUM(qtd), 0), 2)
                        -- Else ROUND(SUM(qtd * (custo_unitario/1)) / NULLIF(SUM(qtd), 0), 2)  
                        Else ROUND(SUM(qtd * (custo_unitario/1)) / NULLIF(SUM(qtd), 0), 2) 
                    END custo_medio
                FROM "databeautykami".tbl_varejo_cmv 
                LEFT JOIN "databeautykami".tbl_distribuicao_bonificacao
                    ON tbl_varejo_cmv.cod_marca = tbl_distribuicao_bonificacao.cod_marca
                    AND DATE_TRUNC('month', dt_faturamento) = date(tbl_distribuicao_bonificacao.mes_ref)
                GROUP BY 1, 2, 3, fator 
                UNION ALL 
                SELECT
                    cod_pedido,
                    codprod,
                    DATE_TRUNC('month', dtvenda) mes_ref,
                    CASE 
                        WHEN fator IS NULL Then ROUND(SUM(quant * custo) / NULLIF(SUM(quant), 0), 2)
                        Else ROUND(SUM(quant * (custo/1)) / NULLIF(SUM(quant), 0), 2)  
                    END custo_medio
                FROM "databeautykami".tbl_salao_pedidos_salao 
                LEFT JOIN "databeautykami".tbl_distribuicao_bonificacao
                    ON DATE_TRUNC('month', dtvenda) = date(tbl_distribuicao_bonificacao.mes_ref)
                    AND ( 
                        trim(upper(tbl_salao_pedidos_salao.categoria)) = trim(upper(tbl_distribuicao_bonificacao.marca))
                        OR substring(replace(upper(tbl_salao_pedidos_salao.categoria),'-',''),1,4) = upper(tbl_distribuicao_bonificacao.marca)
                    )
                WHERE fator is not null
                GROUP BY 1, 2, 3, fator   
            ) cmv_aux
            GROUP BY 1,2,3
        ) cmv 
            ON pedidos.cod_pedido = cmv.cod_pedido 
            AND item_pedidos.sku = cmv.cod_produto 
            AND DATE_TRUNC('month', pedidos.dt_faturamento) = cmv.mes_ref
        WHERE
            pedidos."desc_abrev_cfop" IN (
                'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
                'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
                'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
                'Venda de mercadoria sujeita ao regime de substituição tributária',
                'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
            )
            AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
            AND pedidos.operacoes_internas = 'N'
            {colaborador_filter}
            {channel_filter}
            {uf_filter}
            {brand_filter}
            {team_filter}
    )
    SELECT 
        SUM(CASE 
            WHEN custo_total > 0 
            THEN ((faturamento_liquido / custo_total) - 1) * faturamento_liquido 
            ELSE 0 
        END) / NULLIF(SUM(faturamento_liquido), 0) + 1 as markup_ponderado
    FROM dados_sku
    WHERE custo_total > 0
    """

    df = query_athena(query)
    
    if df.empty:
        return 1.0  # valor default se não houver dados
    
    markup_ponderado = df['markup_ponderado'].iloc[0]
    return markup_ponderado if markup_ponderado > 0 else 1.0
        
# Função auxiliar para formatar data nos logs
def format_date(date_obj):
    return date_obj.strftime('%Y-%m-%d') if date_obj else None

def build_colaborador_filter(cod_colaborador, selected_nome_colaborador, filtro_carteira=True, filtro_pedido=False):
    """
    Constrói o filtro SQL para colaboradores baseado nas seleções do usuário
    """
    if cod_colaborador:
        return f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        conditions = []
        
        if filtro_carteira:
            conditions.append(f"nome_colaborador_atual IN ('{nome_str}')")
        if filtro_pedido:
            conditions.append(f"nome_colaborador_pedido IN ('{nome_str}')")
        
        if conditions:
            return f"AND ({' OR '.join(conditions)})"
        else:
            # Fallback para evitar SQL inválido
            return f"AND nome_colaborador_atual IN ('{nome_str}')"
    return ""

def get_unique_customers_by_granularity(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, 
                                      selected_brands, selected_nome_colaborador, selected_teams, granularity='Mensal'):
    """
    Retorna a contagem de clientes únicos por período
    """
    brand_filter = ""
    channel_filter = ""
    uf_filter = ""
    colaborador_filter = ""

    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        #colaborador_filter = f"AND ( empresa_pedido.nome_colaborador_atual IN ('{nome_str}') OR empresa_pedido.nome_colaborador_pedido IN ('{nome_str}') )"
        colaborador_filter = build_colaborador_filter(
            cod_colaborador, 
            selected_nome_colaborador,
            st.session_state.get('filtro_carteira', True),
            st.session_state.get('filtro_pedido', False)
        )

    if selected_channels:
        channel_filter = f"AND pedidos.canal_venda IN ('{', '.join(selected_channels)}')"
    
    if selected_ufs:
        uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{', '.join(selected_ufs)}')"
    
    if selected_brands:
        brands_str = "', '".join(selected_brands)
        brand_filter = f"AND item_pedidos.marca IN ('{brands_str}')"

    team_filter = format_filter(selected_teams, "empresa_pedido.equipes")

    if granularity == 'Mensal':
        query = f"""
        WITH dados_mensais AS (
            SELECT 
                date_trunc('month', pedidos.dt_faturamento) as mes_ref,
                pedidos.cpfcnpj
            FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
            LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
                ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
            LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
                ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
            WHERE
                pedidos."desc_abrev_cfop" IN (
                    'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
                    'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
                    'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
                    'Venda de mercadoria sujeita ao regime de substituição tributária',
                    'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
                )
                AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
                AND pedidos.operacoes_internas = 'N'
                {colaborador_filter}
                {channel_filter}
                {uf_filter}
                {brand_filter}
                {team_filter}
        )
        SELECT 
            mes_ref as data_ref,
            COUNT(DISTINCT cpfcnpj) as clientes_unicos
        FROM dados_mensais
        GROUP BY mes_ref
        ORDER BY mes_ref
        """
    else:  # Semanal
        query = f"""
        WITH dados_semanais AS (
            SELECT 
                date_trunc('week', pedidos.dt_faturamento) as data_inicio,
                date_trunc('week', pedidos.dt_faturamento) + interval '6' day as data_fim,
                pedidos.cpfcnpj
            FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
            LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
                ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
            LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
                ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
            WHERE
                pedidos."desc_abrev_cfop" IN (
                    'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
                    'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
                    'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
                    'Venda de mercadoria sujeita ao regime de substituição tributária',
                    'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
                )
                AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
                AND pedidos.operacoes_internas = 'N'
                {colaborador_filter}
                {channel_filter}
                {uf_filter}
                {brand_filter}
                {team_filter}
        )
        SELECT 
            data_inicio,
            data_fim,
            COUNT(DISTINCT cpfcnpj) as clientes_unicos
        FROM dados_semanais
        GROUP BY data_inicio, data_fim
        ORDER BY data_inicio
        """

    logging.info(f"Query de clientes únicos sendo executada ({granularity}): {query}")
    
    df = query_athena(query)
    
    if df.empty:
        logging.warning("Query retornou DataFrame vazio")
        return pd.DataFrame()

    # Formatar períodos de acordo com a granularidade
    if granularity == 'Mensal':
        df['data_ref'] = pd.to_datetime(df['data_ref'])
        df['periodo_desc'] = df['data_ref'].dt.strftime('%m-%Y')
    else:
        df['data_inicio'] = pd.to_datetime(df['data_inicio'])
        df['data_fim'] = pd.to_datetime(df['data_fim'])
        df['periodo_desc'] = df.apply(
            lambda x: f"{x['data_inicio'].strftime('%d/%m')} a {x['data_fim'].strftime('%d/%m')}",
            axis=1
        )

    # Log para debug
    logging.info(f"Dados de clientes únicos processados por {granularity}:")
    logging.info(f"Total de períodos: {len(df)}")
    logging.info(f"Períodos gerados: {df['periodo_desc'].tolist()}")
    logging.info(f"Contagens: {df['clientes_unicos'].tolist()}")

    return df[['periodo_desc', 'clientes_unicos']]

def get_brand_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador, selected_teams):
    colaborador_filter = ""
    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        conditions = []
        
        # Pegar os valores do session_state dentro da função
        filtro_carteira = st.session_state.get('filtro_carteira', True)
        filtro_pedido = st.session_state.get('filtro_pedido', False)
        
        if filtro_carteira:
            conditions.append(f"empresa_pedido.nome_colaborador_atual IN ('{nome_str}')")
        if filtro_pedido:
            conditions.append(f"empresa_pedido.nome_colaborador_pedido IN ('{nome_str}')")
        
        if conditions:
            colaborador_filter = f"AND ({' OR '.join(conditions)})"
        else:
            colaborador_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"

    channel_filter = f"AND pedidos.canal_venda IN ('{', '.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{', '.join(selected_ufs)}')" if selected_ufs else ""
    team_filter = format_filter(selected_teams, "empresa_pedido.equipes")


    query = f"""
    SELECT
    item_pedidos.marca,
    ROUND(SUM(item_pedidos."preco_desconto_rateado"), 2) AS faturamento,
    COUNT(DISTINCT pedidos.cpfcnpj) AS clientes_unicos,
    COUNT(DISTINCT pedidos.cod_pedido) AS qtd_pedido,
    SUM(item_pedidos.qtd) AS qtd_itens,
    COUNT(DISTINCT item_pedidos.cod_produto) AS qtd_sku,
    ROUND(SUM(item_pedidos."preco_desconto_rateado") / NULLIF(COUNT(DISTINCT pedidos.cpfcnpj), 0), 2) AS Ticket_Medio_Positivacao,
    ROUND(SUM(item_pedidos."preco_desconto_rateado") / NULLIF(COUNT(DISTINCT pedidos.cod_pedido), 0), 2) AS Ticket_Medio_Pedidos,
    CASE 
        WHEN SUM(COALESCE(cmv.custo_medio, 0) * item_pedidos.qtd) > 0 
        THEN ((SUM(item_pedidos."preco_desconto_rateado") - SUM(COALESCE(cmv.custo_medio, 0) * item_pedidos.qtd)) / SUM(COALESCE(cmv.custo_medio, 0) * item_pedidos.qtd)) * 100 
        ELSE 0 
    END AS markup_percentual
    FROM
        "databeautykami"."vw_distribuicao_pedidos" pedidos
    LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
        ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
    LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
        ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
    LEFT JOIN (
        SELECT
            cod_pedido,
            cod_produto,
            mes_ref,
            marca, 
            SUM(custo_medio) as custo_medio 
            FROM (            
            SELECT 
                cod_pedido,
                cod_produto,
                upper(marca.desc_abrev) marca,
                DATE_TRUNC('month', dt_faturamento) mes_ref,
                CASE WHEN fator IS NULL Then ROUND(SUM(qtd * custo_unitario) / NULLIF(SUM(qtd), 0), 2)
                Else ROUND(SUM(qtd * (custo_unitario/1)) / NULLIF(SUM(qtd), 0), 2)  END custo_medio
            FROM "databeautykami".tbl_varejo_cmv left join "databeautykami".tbl_distribuicao_bonificacao
                ON tbl_varejo_cmv.cod_marca = tbl_distribuicao_bonificacao.cod_marca
                and DATE_TRUNC('month', dt_faturamento) = date(tbl_distribuicao_bonificacao.mes_ref)
                LEFT JOIN "databeautykami".tbl_varejo_marca marca ON marca.cod_marca = tbl_varejo_cmv.cod_marca
                GROUP BY 1, 2, 3, 4, fator 
                UNION ALL 
                SELECT
                    cod_pedido,
                    codprod,
                    upper(categoria) marca,
                    DATE_TRUNC('month', dtvenda) mes_ref,
                    CASE WHEN fator IS NULL Then ROUND(SUM(quant * custo) / NULLIF(SUM(quant), 0), 2)
                    -- Else ROUND(SUM(quant * (custo/fator)) / NULLIF(SUM(quant), 0), 2)  END custo_medio
                    Else ROUND(SUM(quant * (custo/1)) / NULLIF(SUM(quant), 0), 2)  END custo_medio
                FROM "databeautykami".tbl_salao_pedidos_salao left join "databeautykami".tbl_distribuicao_bonificacao
                ON DATE_TRUNC('month', dtvenda) = date(tbl_distribuicao_bonificacao.mes_ref)
                AND ( trim(upper(tbl_salao_pedidos_salao.categoria)) = trim(upper(tbl_distribuicao_bonificacao.marca))
                    OR substring(replace(upper(tbl_salao_pedidos_salao.categoria),'-',''),1,4) = upper(tbl_distribuicao_bonificacao.marca)
                    )
                where fator is not null
                GROUP BY 1, 2, 3, 4 , fator   
            ) cmv_aux
            group by 1,2,3,4
    ) cmv ON pedidos.cod_pedido = cmv.cod_pedido 
        AND item_pedidos.sku = cmv.cod_produto 
        AND DATE_TRUNC('month', pedidos.dt_faturamento) = cmv.mes_ref
    WHERE
        pedidos."desc_abrev_cfop" IN (
            'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
            'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
            'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
            'Venda de mercadoria sujeita ao regime de substituição tributária',
            'VENDA MERCADORIA FORA ESTADO', 'VENDA MERC. SUJEITA AO REGIME DE ST'
        )
        AND date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        AND pedidos.operacoes_internas = 'N'
        AND (pedidos."origem" IN ('egestor','uno'))
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {team_filter}
        GROUP BY item_pedidos.marca
    ORDER BY faturamento DESC
    """
    logging.info(f"Executando query para dados de marca: {query}")
    df = query_athena(query)
    logging.info(f"Query para dados de marca executada com sucesso. Retornando DataFrame com {len(df)} linhas.")
    return df

@st.cache_data(ttl=24*60*60)
def get_team_options():
    logging.info("Iniciando get_team_options")
    query = """
    SELECT DISTINCT empresa_pedido.equipes
    FROM "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
    WHERE empresa_pedido.equipes IS NOT NULL
    AND empresa_pedido.equipes != ''
    ORDER BY empresa_pedido.equipes
    """
    logging.debug(f"Query para obter equipes: {query}")
    
    result = query_athena(query)
    
    if result.empty:
        logging.warning("A query não retornou resultados para equipes")
        return []
    
    if 'equipes' not in result.columns:
        logging.error(f"Coluna 'equipes' não encontrada. Colunas disponíveis: {result.columns}")
        return []
    
    teams = result['equipes'].tolist()
    logging.info(f"Equipes obtidas: {teams}")
    return teams
  

def get_rfm_summary(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores,selected_teams):
    # Adicione a lógica para filtrar por selected_colaboradores
    colaborador_filter = ""
    if cod_colaborador:
        colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_colaboradores:
        colaboradores_str = "', '".join(selected_colaboradores)
        colaborador_filter = f"AND (b.nome_colaborador_atual IN ('{colaboradores_str}') )"
    
    channel_filter = ""
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = f"AND a.Canal_Venda IN ('{channels_str}')"

    uf_filter = ""
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = f"AND a.uf_empresa IN ('{ufs_str}')"
    
    team_filter = format_filter(selected_teams, "b.equipes")

    query = f"""
    WITH rfm_base AS (
        SELECT DISTINCT
            a.Cod_Cliente,
            a.uf_empresa,
            a.Canal_Venda,
            a.Recencia,
            a.Positivacao AS Frequencia,
            a.Monetario,
            b.cod_colaborador_atual
        FROM
            "databeautykami".vw_analise_perfil_cliente_V2 a
        LEFT JOIN
            "databeautykami".vw_distribuicao_cliente_vendedor b ON a.Cod_Cliente = b.cod_cliente
        
        WHERE 1 = 1         
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {team_filter}

    ),
    rfm_scores AS (
        SELECT
            *,
            CASE
                WHEN Recencia BETWEEN 0 AND 1 THEN 5
                WHEN Recencia BETWEEN 2 AND 2 THEN 4
                WHEN Recencia BETWEEN 3 AND 3 THEN 3
                WHEN Recencia BETWEEN 4 AND 6 THEN 2
                ELSE 1
            END AS R_Score,
            CASE
                WHEN Frequencia >= 10 THEN 5
                WHEN Frequencia BETWEEN 7 AND 9 THEN 4
                WHEN Frequencia BETWEEN 3 AND 6 THEN 3
                WHEN Frequencia BETWEEN 2 AND 2 THEN 2
                ELSE 1
            END AS F_Score,
            NTILE(5) OVER (ORDER BY Monetario DESC) AS M_Score
        FROM
            rfm_base
    ),
    rfm_segments AS (
        SELECT
            *,
                CASE
                    WHEN R_Score = 5 AND F_Score >= 4 AND M_Score >= 4 THEN 'Campeões'
                    WHEN R_Score >= 4 AND F_Score >= 4 THEN 'Clientes fiéis'
                    WHEN R_Score = 5 AND F_Score <= 2 THEN 'Novos clientes'
                    WHEN R_Score = 1 THEN 'Perdidos'
                    WHEN R_Score <= 3 AND F_Score = 1 THEN 'Atenção'
                    WHEN F_Score <= 3 AND R_Score BETWEEN 2 and 3 THEN 'Em risco'                 
                    WHEN R_Score >= 3 AND F_Score >= 3 AND M_Score >= 2 THEN 'Potencial'
                    ELSE 'Acompanhar'
                END AS Segmento
        FROM
            rfm_scores
    )
    SELECT
        Segmento,
        Canal_Venda,
        uf_empresa as Regiao,
        COUNT(*) AS Numero_Clientes,
        SUM(Monetario) AS Valor_Total,
        AVG(Monetario) AS Valor_Medio,
        AVG(Recencia) AS Recencia_Media,
        AVG(Frequencia) Positivacoes_Media,
        AVG(M_Score) AS Health_Score_Medio
    FROM
        rfm_segments
    GROUP BY
        Segmento, Canal_Venda, uf_empresa
    ORDER BY
        Valor_Total DESC, Canal_Venda;
    """
    logging.info(f"Executando query para dados de marca: {query}")
    return query_athena(query)

def get_segmentos_query(segmentos):
    if 'Todos' in segmentos:
        return "1=1"  # Isso seleciona todos os segmentos
    elif not segmentos:
        return "1=0"  # Não seleciona nenhum segmento se a lista estiver vazia
    else:
        segmentos_str = ", ".join([f"'{seg}'" for seg in segmentos if seg != 'Todos'])
        return f"Segmento IN ({segmentos_str})"

def get_rfm_segment_clients(cod_colaborador, start_date, end_date, segmentos, selected_channels, selected_ufs, selected_colaboradores, selected_teams):
    logging.info(f"Iniciando get_rfm_segment_clients com os seguintes parâmetros:")
    logging.info(f"cod_colaborador: {cod_colaborador}")
    logging.info(f"start_date: {start_date}")
    logging.info(f"end_date: {end_date}")
    logging.info(f"segmentos: {segmentos}")
    logging.info(f"selected_channels: {selected_channels}")
    logging.info(f"selected_ufs: {selected_ufs}")
    logging.info(f"selected_colaboradores: {selected_colaboradores}")

    colaborador_filter = ""
    if cod_colaborador:
        colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_colaboradores:
        colaboradores_str = "', '".join(selected_colaboradores)
        colaborador_filter = f"AND (b.nome_colaborador_atual IN ('{colaboradores_str}'))"
    
    segmentos_query = get_segmentos_query(segmentos)
    
    channel_filter = f"AND a.Canal_Venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND a.uf_empresa IN ('{','.join(selected_ufs)}')" if selected_ufs else ""
    team_filter = format_filter(selected_teams, "b.equipes")
 

    query = f"""
    WITH rfm_base AS (
        SELECT DISTINCT
            a.Cod_Cliente,
            a.Nome_Cliente,
            a.uf_empresa,
            a.Canal_Venda,
            a.Recencia,
            a.Positivacao,
            a.Monetario,
            a.ticket_medio_posit,
            b.cod_colaborador_atual,
            b.nome_colaborador_atual Vendedor,
            b.equipes as Equipe,
            a.Maior_Mes as Mes_Ultima_Compra,
            a.Ciclo_Vida as Life_Time,
            a.marcas_concatenadas,
            c.status status_inadimplente,
            c.qtd_titulos,
            c.vlr_inadimplente
        FROM
            "databeautykami".vw_analise_perfil_cliente_V2 a
        LEFT JOIN "databeautykami".vw_distribuicao_cliente_vendedor b 
            ON a.Cod_Cliente = b.cod_cliente
        LEFT JOIN "databeautykami".tbl_distribuicao_clientes_inadimplentes c 
            ON a.Cod_Cliente = c.Cod_Cliente and a.uf_empresa = c.uf_empresa     
        WHERE 1 = 1 
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {team_filter}
    ),
    rfm_scores AS (
        SELECT
            *,
            CASE
                WHEN Recencia BETWEEN 0 AND 1 THEN 5
                WHEN Recencia BETWEEN 2 AND 2 THEN 4
                WHEN Recencia BETWEEN 3 AND 3 THEN 3
                WHEN Recencia BETWEEN 4 AND 6 THEN 2
                ELSE 1
            END AS R_Score,
            CASE
                WHEN Positivacao >= 10 THEN 5
                WHEN Positivacao BETWEEN 7 AND 9 THEN 4
                WHEN Positivacao BETWEEN 3 AND 6 THEN 3
                WHEN Positivacao BETWEEN 2 AND 2 THEN 2
                ELSE 1
            END AS F_Score,
            NTILE(5) OVER (ORDER BY Monetario DESC) AS M_Score
        FROM
            rfm_base
    ),
    rfm_segments AS (
        SELECT
            *,
                CASE
                    WHEN R_Score = 5 AND F_Score >= 4 AND M_Score >= 4 THEN 'Campeões'
                    WHEN R_Score >= 4 AND F_Score >= 4 THEN 'Clientes fiéis'
                    WHEN R_Score = 5 AND F_Score <= 2 THEN 'Novos clientes'
                    WHEN R_Score = 1 THEN 'Perdidos'
                    WHEN R_Score <= 3 AND F_Score = 1 THEN 'Atenção'
                    WHEN F_Score <= 3 AND R_Score BETWEEN 2 and 3 THEN 'Em risco'                 
                    WHEN R_Score >= 3 AND F_Score >= 3 AND M_Score >= 2 THEN 'Potencial'
                    ELSE 'Acompanhar'
                END AS Segmento
        FROM
            rfm_scores
    )
    SELECT DISTINCT
        Cod_Cliente,
        Nome_Cliente,
        uf_empresa,
        Canal_Venda,        
        Vendedor,
        Recencia,
        Positivacao,
        Monetario,
        ticket_medio_posit,
        R_Score,
        F_Score,
        M_Score,
        Mes_Ultima_Compra,
        Life_time,
        Segmento,
        marcas_concatenadas as marcas,
        status_inadimplente,
        qtd_titulos,
        vlr_inadimplente
    FROM
        rfm_segments
    WHERE
        {segmentos_query}
    ORDER BY
        Monetario DESC, Canal_Venda;
    """
    
    logging.info(f"Query construída segmento:")
    logging.info(query)
    
    try:
        logging.info("Executando query no Athena...")
        result = query_athena(query)
        logging.info(f"Query executada com sucesso. Tipo do resultado: {type(result)}")
        logging.info(f"Número de linhas no resultado: {len(result)}")
        
        if result.empty:
            logging.warning("O resultado da query é um DataFrame vazio.")
        else:
            logging.info(f"Colunas do DataFrame: {result.columns.tolist()}")
            logging.info(f"Primeiras linhas do DataFrame:\n{result.head().to_string()}")
        
        return result
    except Exception as e:
        logging.error(f"Erro ao executar a query: {str(e)}")
        raise

def get_recency_clients(cod_colaborador, start_date, end_date, recencias, selected_channels, selected_ufs, selected_colaboradores, selected_teams):
    """
    Função similar ao get_rfm_segment_clients mas para recência
    """
    logging.info(f"Iniciando get_recency_clients com os seguintes parâmetros:")
    logging.info(f"recencias selecionadas: {recencias}")

    colaborador_filter = ""
    if cod_colaborador:
        colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_colaboradores:
        colaboradores_str = "', '".join(selected_colaboradores)
        colaborador_filter = f"AND (b.nome_colaborador_atual IN ('{colaboradores_str}'))"
    
    channel_filter = f"AND a.Canal_Venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND a.uf_empresa IN ('{','.join(selected_ufs)}')" if selected_ufs else ""
    team_filter = format_filter(selected_teams, "b.equipes")

    if not isinstance(recencias, list):
        recencias = [recencias]
    
    # Converter todos os valores para inteiros, exceto 'Maior que 6'
    recencias_processadas = []
    for rec in recencias:
        if isinstance(rec, (int, float)) or (isinstance(rec, str) and rec.isdigit()):
            recencias_processadas.append(int(float(rec)))
        else:
            recencias_processadas.append(rec)
            
    logging.info(f"Recências processadas: {recencias_processadas}")

    # Construir a condição WHERE para recência
    if len(recencias_processadas) == 1:
            if recencias_processadas[0] == 0:
                recency_condition = "recencia = 0"  # Corrigido aqui para recency_condition
            elif recencias_processadas[0] == 'Maior que 6':
                recency_condition = "recencia > 6"  # Corrigido aqui para recency_condition
            else:
                recency_condition = f"recencia = {recencias_processadas[0]}"  # Corrigido aqui para recency_condition
    else:
        # Para múltiplas recências
        conditions = []
        for rec in recencias_processadas:
            if rec == 'Maior que 6':
                    conditions.append("recencia > 6")
            else:
                conditions.append(f"recencia = {rec}")
        recency_condition = f"({' OR '.join(conditions)})"  # Corrigido aqui para recency_condition
        
    logging.info(f"Condição de recência construída: {recency_condition}")

    # Resto da função permanece igual...
    query = f"""
    WITH rfm_base AS (
        SELECT DISTINCT
            a.Cod_Cliente,
            a.Nome_Cliente,
            a.uf_empresa,
            a.Canal_Venda,
            a.Recencia,
            a.Positivacao,
            a.Monetario,
            a.ticket_medio_posit,
            b.cod_colaborador_atual,
            b.nome_colaborador_atual Vendedor,
            b.equipes as Equipe,
            a.Maior_Mes as Mes_Ultima_Compra,
            a.Ciclo_Vida as Life_Time,
            a.marcas_concatenadas,
            c.status status_inadimplente,
            c.qtd_titulos,
            c.vlr_inadimplente
        FROM
            "databeautykami"._V2 a
        LEFT JOIN "databeautykami".vw_distribuicao_cliente_vendedor b 
            ON a.Cod_Cliente = b.cod_cliente
        LEFT JOIN "databeautykami".tbl_distribuicao_clientes_inadimplentes c 
            ON a.Cod_Cliente = c.Cod_Cliente and a.uf_empresa = c.uf_empresa     
        WHERE 1 = 1 
        AND {recency_condition}
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {team_filter}
    ),
    rfm_scores AS (
        SELECT
            *,
            CASE
                WHEN Recencia BETWEEN 0 AND 1 THEN 5
                WHEN Recencia BETWEEN 2 AND 2 THEN 4
                WHEN Recencia BETWEEN 3 AND 3 THEN 3
                WHEN Recencia BETWEEN 4 AND 6 THEN 2
                ELSE 1
            END AS R_Score,
            CASE
                WHEN Positivacao >= 10 THEN 5
                WHEN Positivacao BETWEEN 7 AND 9 THEN 4
                WHEN Positivacao BETWEEN 3 AND 6 THEN 3
                WHEN Positivacao BETWEEN 2 AND 2 THEN 2
                ELSE 1
            END AS F_Score,
            NTILE(5) OVER (ORDER BY Monetario DESC) AS M_Score
        FROM
            rfm_base
    )
    SELECT DISTINCT
        Cod_Cliente,
        Nome_Cliente,
        uf_empresa,
        Canal_Venda,        
        Vendedor,
        Recencia,
        Positivacao,
        Monetario,
        ticket_medio_posit,
        R_Score,
        F_Score,
        M_Score,
        Mes_Ultima_Compra,
        Life_time,
        marcas_concatenadas as marcas,
        status_inadimplente,
        qtd_titulos,
        vlr_inadimplente
    FROM
        rfm_scores
    ORDER BY
        Monetario DESC, Canal_Venda;
    """
    
    try:
        logging.info("Executando query no Athena...")
        result = query_athena(query)
        return result
    except Exception as e:
        logging.error(f"Erro ao executar a query: {str(e)}")
        raise

def get_rfm_heatmap_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores,selected_teams):
    if cod_colaborador or selected_colaboradores:
        colaborador_filter = ""
        if cod_colaborador:
            colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'"
        elif selected_colaboradores:
            # Apenas aplique o filtro de nome se não houver um código de colaborador
            nome_str = "', '".join(selected_colaboradores)
            colaborador_filter = f"AND (b.nome_colaborador_atual IN ('{nome_str}'))"
    else:
        colaborador_filter = ""

    channel_filter = f"AND a.Canal_Venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND a.uf_empresa IN ('{','.join(selected_ufs)}')" if selected_ufs else ""
    team_filter = format_filter(selected_teams, "b.equipes")


    query = f"""
    WITH rfm_base AS (
        SELECT
            a.Recencia,
            a.Positivacao AS Frequencia
        FROM
            "databeautykami".vw_analise_perfil_cliente_V2 a
        LEFT JOIN
            "databeautykami".vw_distribuicao_cliente_vendedor b ON a.Cod_Cliente = b.cod_cliente
                    
        WHERE 1 = 1 
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {team_filter}
  
    ),
    rfm_scores AS (
        SELECT
            LEAST(FLOOR(Recencia), 12) AS R_Score,
            LEAST(FLOOR(Frequencia), 13) AS F_Score
        FROM
            rfm_base
    )
    SELECT
        R_Score AS Recencia,
        F_Score AS Frequencia,
        COUNT(*) AS Quantidade
    FROM
        rfm_scores
    GROUP BY
        R_Score, F_Score
    ORDER BY
        R_Score, F_Score
    """
    
    return query_athena(query)
    # Log para depuração
    print(f"Query executada: {query}")
    return query_athena(query)

def create_rfm_heatmap_from_aggregated(df):
    if df is None or df.empty:
        st.warning("Não há dados disponíveis para criar o mapa de calor RFM.")
        return None

    # Verificar se as colunas necessárias existem
    required_columns = ['Recencia', 'Frequencia', 'Quantidade']
    if not all(col in df.columns for col in required_columns):
        st.error(f"Colunas necessárias não encontradas. Colunas esperadas: {required_columns}")
        st.error(f"Colunas presentes: {df.columns.tolist()}")
        return None

    try:
        # Converter para tipos numéricos, se necessário
        df['Recencia'] = pd.to_numeric(df['Recencia'], errors='coerce')
        df['Frequencia'] = pd.to_numeric(df['Frequencia'], errors='coerce')
        df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce')

        # Remover linhas com valores NaN
        df = df.dropna()

        # Criar uma matriz 13x13 preenchida com zeros
        heatmap_data = np.zeros((13, 13))

        # Preencher a matriz com os dados
        for _, row in df.iterrows():
            recency = int(row['Recencia'])
            frequency = int(row['Frequencia'])
            if 0 <= recency < 13 and 1 <= frequency <= 13:
                heatmap_data[recency, frequency - 1] = row['Quantidade']

        # Criar o mapa de calor
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            x=list(range(1, 14)),
            y=list(range(13)),
            colorscale='YlOrRd',
            hovertemplate='Recência: %{y}<br>Frequência: %{x}<br>Número de Clientes: %{z:.0f}<extra></extra>'
        ))

        # Adicionar anotações com o número de clientes em cada célula
        for i in range(13):
            for j in range(13):
                value = heatmap_data[i, j]
                if value > 0:
                    text_color = 'black' if value < np.max(heatmap_data) / 2 else 'white'
                    fig.add_annotation(
                        x=j+1, y=i,
                        text=f"{int(value)}",
                        showarrow=False,
                        font=dict(color=text_color, size=12)  # Fonte ainda menor
                    )

        fig.update_layout(
            title={
                'text': 'Matriz Recencia vs Positivacao',
                'y':0.95,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title='Frequência (Positivacao)',
            yaxis_title='Recência',
            xaxis=dict(
                tickmode='array', 
                tickvals=list(range(1, 14)), 
                ticktext=[str(i) for i in range(1, 14)],
                tickfont=dict(size=12)
            ),
            yaxis=dict(
                tickmode='array', 
                tickvals=list(range(13)), 
                ticktext=[str(i) for i in range(13)],
                tickfont=dict(size=12)
            ),
            width=800,  # Largura reduzida
            #height=500,  # Altura reduzida
            margin=dict(l=40, r=20, t=40, b=20),  # Margens ajustadas
            font=dict(size=12)  # Tamanho da fonte geral
        )

        return fig

    except Exception as e:
        st.error(f"Erro ao criar o mapa de calor RFM: {str(e)}")
        return None


def get_channels_and_ufs(cod_colaborador, start_date, end_date):


    query = f"""
    SELECT DISTINCT 
        pedidos.canal_venda,
        empresa_pedido.uf_empresa_faturamento
    FROM
        "databeautykami"."vw_distribuicao_pedidos" pedidos
    LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
        ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
    WHERE
        date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        {'AND empresa_pedido.cod_colaborador_atual = ' + f"'{cod_colaborador}'" if cod_colaborador else ''}
    """
    df = query_athena(query)
    return df['canal_venda'].unique().tolist(), df['uf_empresa_faturamento'].unique().tolist()

def get_colaboradores(start_date, end_date, selected_channels=None, selected_ufs=None):
    channel_filter = ""
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = f"AND pedidos.canal_venda IN ('{channels_str}')"

    uf_filter = ""
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{ufs_str}')"

    query = f"""
    SELECT DISTINCT
        empresa_pedido.nome_colaborador_atual as nome_colaborador,
        empresa_pedido.cod_colaborador_atual as cod_colaborador
    FROM
        "databeautykami"."vw_distribuicao_pedidos" pedidos
    LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
        ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
    WHERE
        date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        {channel_filter}
        {uf_filter}
    ORDER BY
        empresa_pedido.nome_colaborador_atual
    """
    
    return query_athena(query)

@st.cache_data(ttl=24*60*60)
def get_colaboradores_options():
    logging.info("Iniciando get_colaboradores_options")
    query = """
    SELECT DISTINCT
        empresa_pedido.nome_colaborador_atual as nome_colaborador
    FROM "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
    WHERE empresa_pedido.nome_colaborador_atual IS NOT NULL
    AND empresa_pedido.nome_colaborador_atual != ''
    ORDER BY
        empresa_pedido.nome_colaborador_atual
    """
    logging.debug(f"Query para obter colaboradores: {query}")
    
    result = query_athena(query)
    
    if result.empty:
        logging.warning("A query não retornou resultados para colaboradores")
        return []
    
    if 'nome_colaborador' not in result.columns:
        logging.error(f"Coluna 'nome_colaborador' não encontrada. Colunas disponíveis: {result.columns}")
        return []
    
    colaboradores = result['nome_colaborador'].tolist()
    logging.info(f"Número de colaboradores obtidos: {len(colaboradores)}")
    return colaboradores

def get_client_status(start_date, end_date, cod_colaborador, selected_channels, selected_ufs, selected_nome_colaborador, selected_brands,selected_teams):

    colaborador_filter = ""
    if cod_colaborador or selected_nome_colaborador:
            colaborador_filter = ""
    if cod_colaborador:
            colaborador_filter = f"AND vw_distribuicao_empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        # Apenas aplique o filtro de nome se não houver um código de colaborador
        nome_str = "', '".join(selected_nome_colaborador)
        #colaborador_filter = f"AND ( vw_distribuicao_empresa_pedido.nome_colaborador_atual IN ('{nome_str}') OR vw_distribuicao_empresa_pedido.nome_colaborador_pedido IN ('{nome_str}') )"
        colaborador_filter = build_colaborador_filter(
            cod_colaborador, 
            selected_nome_colaborador,
            st.session_state.get('filtro_carteira', True),
            st.session_state.get('filtro_pedido', False)
        )
        
  
    channel_filter = ""
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = "AND vw_distribuicao_pedidos.canal_venda IN ('{}')".format(channels_str)

    brand_filter = ""
    if selected_brands:
            selected_brands = [brand for brand in selected_brands if brand is not None]
            brand_str = "', '".join(selected_brands)
            brand_filter = f"AND vw_distribuicao_item_pedidos.marca IN ('{brand_str}')"
    else:
            brand_filter = ""
    
    uf_filter = ""
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = "AND vw_distribuicao_empresa_pedido.uf_empresa_faturamento IN ('{}')".format(ufs_str)

   
    team_filter = format_filter(selected_teams, "vw_distribuicao_empresa_pedido.equipes")  

    query = """
    WITH Meses AS (
            SELECT 
                DATE_TRUNC('month', date_add('month', -seq, DATE('2024-12-01'))) AS mes
            FROM 
                UNNEST(SEQUENCE(0, 15)) AS t(seq)
    ),
    PedidosComItens AS (
        SELECT
            vw_distribuicao_pedidos.cod_pedido,
            vw_distribuicao_pedidos.cpfcnpj as cod_cliente,
            vw_distribuicao_pedidos.dt_faturamento,
            vw_distribuicao_empresa_pedido.nome_empresa_faturamento AS empresa,
            vw_distribuicao_empresa_pedido.equipes,
            vw_distribuicao_pedidos.origem,
            vw_distribuicao_item_pedidos.marca,
            vw_distribuicao_pedidos.canal_venda,
            vw_distribuicao_pedidos.Operacoes_Internas,
            vw_distribuicao_empresa_pedido.nome_colaborador_atual,
            vw_distribuicao_empresa_pedido.nome_colaborador_pedido
        FROM
            "databeautykami".vw_distribuicao_pedidos 
        LEFT JOIN
            "databeautykami".vw_distribuicao_item_pedidos ON vw_distribuicao_pedidos.cod_pedido = vw_distribuicao_item_pedidos.cod_pedido
        LEFT JOIN 
            "databeautykami".vw_distribuicao_empresa_pedido ON vw_distribuicao_empresa_pedido.cod_pedido = vw_distribuicao_pedidos.cod_pedido
        WHERE vw_distribuicao_pedidos.desc_abrev_cfop IN (
                'VENDA', 'VENDA DE MERC.SUJEITA ST', 'VENDA DE MERCADORIA P/ NÃO CONTRIBUINTE',
                'VENDA DO CONSIGNADO', 'VENDA MERC. REC. TERCEIROS DESTINADA A ZONA FRANCA DE MANAUS',
                'VENDA MERC.ADQ. BRASIL FORA ESTADO', 'VENDA MERCADORIA DENTRO DO ESTADO',
                'VENDA MERCADORIA FORA ESTADO', 'Venda de mercadoria sujeita ao regime de substituição tributária',
                'VENDA MERC. SUJEITA AO REGIME DE ST'
            )
            AND ("databeautykami"."vw_distribuicao_pedidos"."operacoes_internas" = 'N')
            AND ("databeautykami"."vw_distribuicao_pedidos"."origem" IN ('egestor','uno'))
            {channel_filter}
            {uf_filter}
            {colaborador_filter}
            {brand_filter}
            {team_filter}
    ),
        PrimeirasCompras AS (
            SELECT
                cod_cliente,
                MIN(DATE_TRUNC('month', dt_faturamento)) AS mes_primeira_compra
            FROM 
                PedidosComItens
            GROUP BY
                cod_cliente
        ),
        UltimaCompra AS (
            SELECT
                cod_cliente,
                MAX(dt_faturamento) AS ultima_data_compra
            FROM 
                PedidosComItens
            GROUP BY
                cod_cliente
        ),
        ChurnClientes AS (
            SELECT
                mes,
                cod_cliente
            FROM (
                SELECT
                    m.mes,
                    u.cod_cliente,
                    ROW_NUMBER() OVER (PARTITION BY u.cod_cliente ORDER BY m.mes) as rn
                FROM
                    Meses m
                JOIN
                    UltimaCompra u ON u.ultima_data_compra < DATE_ADD('day', -180, m.mes) AND m.mes > date_parse('2023-07-01', '%Y-%m-%d')
            ) sub
            WHERE sub.rn = 1
        ),
        RecuperacaoClientes AS (
            SELECT
                cod_cliente,
                DATE_TRUNC('month', dt_faturamento) AS mes_recuperacao,
                CASE 
                    WHEN (dt_faturamento > DATE_ADD('day', 90, penultima_data_compra) AND dt_faturamento <= DATE_ADD('day', 180, penultima_data_compra)) THEN 'Reativacao'
                    WHEN (dt_faturamento > DATE_ADD('day', 180, penultima_data_compra)) THEN 'Recuperacao'
                END AS Status_Cliente
            FROM (
                SELECT
                    cod_cliente,
                    dt_faturamento,
                    LAG(dt_faturamento) OVER (PARTITION BY cod_cliente ORDER BY dt_faturamento) AS penultima_data_compra
                FROM
                    PedidosComItens
            ) p
            WHERE
                dt_faturamento IS NOT NULL
                AND penultima_data_compra IS NOT NULL
                AND (dt_faturamento > DATE_ADD('day', 180, penultima_data_compra)
                    OR (dt_faturamento > DATE_ADD('day', 90, penultima_data_compra) AND dt_faturamento <= DATE_ADD('day', 180, penultima_data_compra)))
                AND DATE_TRUNC('month', dt_faturamento) >= DATE('2024-01-01')
        ),
        ClientesPositivados AS (
            SELECT
                cod_cliente,
                DATE_TRUNC('month', dt_faturamento) AS mes_positivado
            FROM
                PedidosComItens
            WHERE
                DATE_TRUNC('month', dt_faturamento) >= DATE('2024-01-01')
            GROUP BY
                cod_cliente,
                DATE_TRUNC('month', dt_faturamento)
        ),
        BaseClientes AS (
            SELECT
                m.mes,
                COUNT(DISTINCT p.cod_cliente) AS total_clientes_base
            FROM
                Meses m
            JOIN
                PedidosComItens p ON p.dt_faturamento > DATE_ADD('day', -180, m.mes)
                                AND p.dt_faturamento <= m.mes
            WHERE
                m.mes >= DATE('2024-01-01')
            GROUP BY
                m.mes
        )

    -- União final dos resultados
        SELECT
            m.mes,
            'novas_aberturas' AS status,
            COUNT(DISTINCT CASE WHEN p.mes_primeira_compra = m.mes THEN p.cod_cliente END) AS qtd
        FROM
            Meses m
        LEFT JOIN
            PrimeirasCompras p ON m.mes = p.mes_primeira_compra
        WHERE
            m.mes <= DATE_TRUNC('month', CURRENT_DATE)
            AND m.mes BETWEEN date_trunc('month',date('{start_date}')) AND date_trunc('month',date('{end_date}')) 
        GROUP BY
            m.mes
        HAVING 
            COUNT(DISTINCT CASE WHEN p.mes_primeira_compra = m.mes THEN p.cod_cliente END) > 0

        UNION ALL

        SELECT
            m.mes,
            'churn' AS status,
            COUNT(DISTINCT CASE WHEN c.cod_cliente IS NOT NULL THEN c.cod_cliente END) AS qtd
        FROM
            Meses m
        LEFT JOIN
            ChurnClientes c ON m.mes = c.mes
        WHERE
            m.mes <= DATE_TRUNC('month', CURRENT_DATE)
            AND m.mes BETWEEN date_trunc('month',date('{start_date}')) AND date_trunc('month',date('{end_date}'))
        GROUP BY
            m.mes
        HAVING 
            COUNT(DISTINCT CASE WHEN c.cod_cliente IS NOT NULL THEN c.cod_cliente END) > 0

        UNION ALL

        SELECT
            m.mes,
            'Recuperado' AS status,
            COUNT(DISTINCT CASE WHEN r.mes_recuperacao = m.mes AND r.Status_Cliente = 'Recuperacao' THEN r.cod_cliente END) AS qtd
        FROM
            Meses m
        LEFT JOIN
            RecuperacaoClientes r ON m.mes = r.mes_recuperacao
        WHERE
            m.mes <= DATE_TRUNC('month', CURRENT_DATE)
            AND m.mes BETWEEN date_trunc('month',date('{start_date}')) AND date_trunc('month',date('{end_date}'))
        GROUP BY
            m.mes
        HAVING   
            COUNT(DISTINCT CASE WHEN r.mes_recuperacao = m.mes AND r.Status_Cliente = 'Recuperacao' THEN r.cod_cliente END) > 0

        UNION ALL

        SELECT
            m.mes,
            'Reativado' AS status,
            COUNT(DISTINCT CASE WHEN r.mes_recuperacao = m.mes AND r.Status_Cliente = 'Reativacao' THEN r.cod_cliente END) AS qtd
        FROM
            Meses m
        LEFT JOIN
            RecuperacaoClientes r ON m.mes = r.mes_recuperacao
        WHERE
            m.mes <= DATE_TRUNC('month', CURRENT_DATE)
            AND m.mes BETWEEN date_trunc('month',date('{start_date}')) AND date_trunc('month',date('{end_date}'))
        GROUP BY
            m.mes
        HAVING 
            COUNT(DISTINCT CASE WHEN r.mes_recuperacao = m.mes AND r.Status_Cliente = 'Reativacao' THEN r.cod_cliente END) > 0

        UNION ALL

        SELECT
            m.mes,
            'Positivado' AS status,
            COUNT(DISTINCT cp.cod_cliente) AS qtd
        FROM
            Meses m
        JOIN
            ClientesPositivados cp ON m.mes = cp.mes_positivado
        LEFT JOIN
            PrimeirasCompras pc ON cp.cod_cliente = pc.cod_cliente AND cp.mes_positivado = pc.mes_primeira_compra
        LEFT JOIN
            ChurnClientes cc ON cp.cod_cliente = cc.cod_cliente AND cp.mes_positivado = cc.mes
        LEFT JOIN
            RecuperacaoClientes rc ON cp.cod_cliente = rc.cod_cliente AND cp.mes_positivado = rc.mes_recuperacao
        WHERE
            m.mes <= DATE_TRUNC('month', CURRENT_DATE)
            AND m.mes BETWEEN date_trunc('month',date('{start_date}')) AND date_trunc('month',date('{end_date}'))
            AND pc.cod_cliente IS NULL
            AND cc.cod_cliente IS NULL
            AND rc.cod_cliente IS NULL
        GROUP BY
            m.mes
        HAVING 
            COUNT(DISTINCT cp.cod_cliente) > 0

        UNION ALL

        SELECT
            mes,
            'Base' AS status,
            total_clientes_base AS qtd
        FROM
            BaseClientes
        WHERE
            mes <= DATE_TRUNC('month', CURRENT_DATE)
            AND mes BETWEEN date_trunc('month',date('{start_date}')) AND date_trunc('month',date('{end_date}'))

        ORDER BY
            mes, status
   """.format(
        start_date=start_date,
        end_date=end_date,
        channel_filter=channel_filter,
        uf_filter=uf_filter,
        colaborador_filter=colaborador_filter,
        brand_filter=brand_filter,
        team_filter=team_filter
    )

    logging.info(f"Executing query for client status: {query}")
    df = query_athena(query)
    
    if df.empty:
        logging.warning("No data returned from client status query")
    else:
        logging.info(f"Client status data retrieved. Shape: {df.shape}")
        logging.info(f"Columns: {df.columns}")
        logging.info(f"First few rows:\n{df.head()}")
    
    return df if df is not None else pd.DataFrame()


    return get_rfm_summary(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores)

def create_client_status_chart(df):
    logging.info(f"Entering create_client_status_chart with DataFrame shape: {df.shape}")
    
    if df.empty:
        logging.warning("DataFrame is empty")
        return None, None, None

    # Calcular as médias de cada status
    status_averages = df.groupby('status')['qtd'].mean().sort_values(ascending=False)
    logging.info(f"Calculated status averages: {status_averages}")

    # Pivot the dataframe
    df_pivot = df.pivot(index='mes', columns='status', values='qtd').fillna(0)
    logging.info(f"Pivoted DataFrame shape: {df_pivot.shape}")
    logging.info(f"Pivoted DataFrame columns: {df_pivot.columns}")

    if 'Base' not in df_pivot.columns:
        logging.warning("Column 'Base' not found in pivoted data")
        return None, None, status_averages

    # Separate Base from other statuses
    base = df_pivot['Base']
    df_percentages = df_pivot.drop(columns=['Base']).div(base, axis=0) * 100

    # Create the line chart for percentages
    fig_percentages = go.Figure()
    
    for column in df_percentages.columns:
        show_text = column in ['Positivado', 'novas_aberturas']
        fig_percentages.add_trace(go.Scatter(
            x=df_percentages.index,
            y=df_percentages[column],
            mode='lines+markers+text' if show_text else 'lines+markers',
            name=column,
            text=[f'{p:.1f}%' if show_text else '' for p in df_percentages[column]],
            textposition='top center',
            hovertext=[f'{p:.1f}% ({v:,.0f})' for p, v in zip(df_percentages[column], df_pivot[column])],
            hoverinfo='text+name'
        ))

    fig_percentages.update_layout(
        title='Evolução Percentual dos Status dos Clientes',
        yaxis_title='Percentual',
        xaxis_title='Mês',
        legend_title='Status',
        hovermode='x unified',
        yaxis=dict(tickformat='.1f', ticksuffix='%'),
        xaxis=dict(tickangle=45),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Create the line chart for Base
    fig_base = go.Figure()
    fig_base.add_trace(go.Scatter(
        x=base.index, 
        y=base, 
        mode='lines+markers+text',
        name='Base Total',
        text=[f"{v:,.0f}" for v in base],
        textposition='top center',
        line=dict(color='#1f77b4', width=2),  # Cor e espessura da linha
        marker=dict(size=8, color='#1f77b4'),  # Tamanho e cor dos marcadores
        textfont=dict(size=10, color='#1f77b4')  # Tamanho e cor do texto
    ))

    fig_base.update_layout(
        title='Evolução da Base Total de Clientes',
        xaxis_title='Mês',
        xaxis=dict(
            showline=True,
            showgrid=False,
            showticklabels=True,
            linecolor='rgb(204, 204, 204)',
            linewidth=2,
            ticks='outside',
            tickfont=dict(
                family='Arial',
                size=12,
                color='rgb(82, 82, 82)',
            ),
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=False,
            showticklabels=False,
        ),
        showlegend=False,
        plot_bgcolor='white'
    )

    # Adicionar um pouco de espaço em branco acima do gráfico para os rótulos
    y_max = max(base) * 1.1
    fig_base.update_layout(yaxis_range=[0, y_max])

    return fig_percentages, fig_base, status_averages

def create_new_rfm_heatmap(df):
    if df.empty:
        st.warning("Não há dados disponíveis para o mapa de calor RFM.")
        return None

    # Verificar se as colunas necessárias existem
    required_columns = ['Recencia', 'Frequencia']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"Colunas ausentes no DataFrame: {', '.join(missing_columns)}")
        return None

    # Criando a matriz de contagem
    heatmap_data = pd.DataFrame(index=range(0, 13), columns=range(1, 14))
    heatmap_data = heatmap_data.fillna(0)

    try:
        for _, row in df.iterrows():
            r_score = int(row['Recencia'])
            f_score = int(row['Frequencia'])
            
            # Garantir que os scores estão dentro do intervalo
            r_score = max(0, min(12, r_score))
            f_score = max(1, min(13, f_score))
            
            heatmap_data.at[r_score, f_score] += 1

        # Criando o mapa de calor
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='YlOrRd',
            hovertemplate='Recência: %{y}<br>Frequência: %{x}<br>Número de Clientes: %{z:.0f}<extra></extra>'
        ))

        # Adicionando o texto com o número de clientes em cada célula
        for i, row in heatmap_data.iterrows():
            for j, value in row.items():
                if value > 0:
                    fig.add_annotation(
                        x=j,
                        y=i,
                        text=str(int(value)),
                        showarrow=False,
                        font=dict(color="black" if value < heatmap_data.values.max()/2 else "white")
                    )

        fig.update_layout(
            title='Matriz RFM',
            xaxis_title='Frequência',
            yaxis_title='Recência',
            xaxis=dict(tickmode='array', tickvals=list(range(1, 14)), ticktext=[str(i) for i in range(1, 14)]),
            yaxis=dict(tickmode='array', tickvals=list(range(0, 13)), ticktext=[str(i) for i in range(0, 13)])
        )

        return fig
    except Exception as e:
        st.error(f"Erro ao criar o mapa de calor RFM: {str(e)}")
        return None

def debug_heatmap_data(df):
    st.write("Primeiras linhas dos dados do mapa de calor:")
    st.write(df.head())
    st.write("Informações sobre os dados:")
    st.write(df.info())
    st.write("Estatísticas descritivas:")
    st.write(df.describe())

def debug_rfm_summary(df):
    st.write("Resumo dos dados RFM:")
    st.write(f"Número de linhas: {len(df)}")
    st.write("Colunas presentes:")
    st.write(df.columns.tolist())
    st.write("Primeiras linhas dos dados:")
    st.write(df.head())
    st.write("Informações sobre os dados:")
    st.write(df.info())
    st.write("Estatísticas descritivas:")
    st.write(df.describe())

def debug_brand_data(df):
    st.write("Resumo dos dados de marca:")
    st.write(f"Número de linhas: {len(df)}")
    st.write("Colunas presentes:")
    st.write(df.columns.tolist())
    st.write("Primeiras linhas dos dados:")
    st.write(df.head())
    st.write("Informações sobre os dados:")
    st.write(df.info())
    st.write("Estatísticas descritivas:")
    st.write(df.describe())

def clear_cache():
    st.cache_data.clear()

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