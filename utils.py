import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import logging
from pyathena import connect
from dotenv import load_dotenv
from pyathena.pandas.util import as_pandas
import os



__all__ = [
    'get_monthly_revenue_cached', 'get_brand_data_cached', 'get_channels_and_ufs_cached',
    'get_colaboradores_cached', 'get_rfm_summary_cached', 'get_rfm_heatmap_data_cached',
    'query_athena', 'get_monthly_revenue', 'get_brand_data', 'get_rfm_summary',
    'get_rfm_segment_clients', 'get_rfm_heatmap_data', 'create_rfm_heatmap_from_aggregated',
    'get_channels_and_ufs', 'get_colaboradores', 'get_client_status',
    'create_client_status_chart', 'create_new_rfm_heatmap', 'clear_cache', 'get_team_options'
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

# Funções cacheadas
@st.cache_data
def get_monthly_revenue_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams):
    return get_monthly_revenue(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams)

@st.cache_data
def get_abc_curve_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams):
    return get_abc_curve_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams)

@st.cache_data
def get_brand_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador,selected_teams):
    logging.info(f"Chamando get_brand_data_cached com os seguintes parâmetros:")
    logging.info(f"cod_colaborador: {cod_colaborador}")
    logging.info(f"start_date: {start_date}")
    logging.info(f"end_date: {end_date}")
    logging.info(f"selected_channels: {selected_channels}")
    logging.info(f"selected_ufs: {selected_ufs}")
    logging.info(f"selected_nome_colaborador: {selected_nome_colaborador}")
    return get_brand_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador,selected_teams)

@st.cache_data
def get_channels_and_ufs_cached(cod_colaborador, start_date, end_date):
    return get_channels_and_ufs(cod_colaborador, start_date, end_date)

@st.cache_data
def get_colaboradores_cached(start_date, end_date, selected_channels, selected_ufs):
    return get_colaboradores(start_date, end_date, selected_channels, selected_ufs)

@st.cache_data
def get_rfm_summary_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores):
    logging.info(f"Chamando get_rfm_summary_cached com os seguintes parâmetros:")
    logging.info(f"cod_colaborador: {cod_colaborador}")
    logging.info(f"start_date: {start_date}")
    logging.info(f"end_date: {end_date}")
    logging.info(f"selected_channels: {selected_channels}")
    logging.info(f"selected_ufs: {selected_ufs}")
    logging.info(f"selected_colaboradores: {selected_colaboradores}")
    #logging.info(f"selected_colaboradores: {selected_teams}")
    return get_rfm_summary(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores)

@st.cache_data
def get_rfm_heatmap_data_cached(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores):
    return get_rfm_heatmap_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores)

@st.cache_data
def get_rfm_segment_clients_cached(cod_colaborador, start_date, end_date, segmentos, selected_channels, selected_ufs, selected_colaboradores):
    return get_rfm_segment_clients(cod_colaborador, start_date, end_date, segmentos, selected_channels, selected_ufs, selected_colaboradores)

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

def query_athena(query):
    try:
        logging.info("Iniciando conexão com Athena")
        conn = connect(s3_staging_dir=ATHENA_S3_STAGING_DIR, region_name=ATHENA_REGION)
        cursor = conn.cursor()
        logging.info("Executando query")
        cursor.execute(query)
        logging.info("Convertendo resultado para DataFrame")
        df = as_pandas(cursor)
        logging.info(f"Query executada com sucesso. Retornando DataFrame com {len(df)} linhas.")
        return df
    except Exception as e:
        logging.error(f"Erro ao executar query no Athena: {str(e)}")
        st.error(f"Erro ao executar query no Athena: {str(e)}")
        return pd.DataFrame()

def get_abc_curve_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador, selected_teams):
    # Inicialização de variáveis
    brand_filter = ""
    channel_filter = ""
    uf_filter = ""
    team_filter = ""
    colaborador_filter = ""

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
    
    # Filtro de equipes
    if selected_teams:
        teams_str = "', '".join(selected_teams)
        team_filter = f"AND empresa_pedido.equipes IN ('{teams_str}')"

    # Filtro de colaborador
    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        colaborador_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"

    query = f"""
    WITH produto_sales AS (
      SELECT
        item_pedidos.sku,
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
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {team_filter}
        {colaborador_filter}
      GROUP BY 1,3
    ),
    produto_abc AS (
      SELECT
        *,
        SUM(faturamento_liquido) OVER () AS total_faturamento,
        SUM(faturamento_liquido) OVER (ORDER BY faturamento_liquido DESC) / SUM(faturamento_liquido) OVER () AS faturamento_acumulado,
        CASE
          WHEN SUM(faturamento_liquido) OVER (ORDER BY faturamento_liquido DESC) / SUM(faturamento_liquido) OVER () <= 0.8 THEN 'A'
          WHEN SUM(faturamento_liquido) OVER (ORDER BY faturamento_liquido DESC) / SUM(faturamento_liquido) OVER () <= 0.95 THEN 'B'
          ELSE 'C'
        END AS curva
      FROM produto_sales
    )
    SELECT *
    FROM produto_abc
    ORDER BY faturamento_liquido DESC
    """
    
    logging.info(f"Query executada para Curva ABC: {query}")
    logging.info(f"Parâmetros de entrada:")
    logging.info(f"cod_colaborador: {cod_colaborador}")
    logging.info(f"start_date: {start_date}")
    logging.info(f"end_date: {end_date}")
    logging.info(f"selected_channels: {selected_channels}")
    logging.info(f"selected_ufs: {selected_ufs}")
    logging.info(f"selected_brands: {selected_brands}")
    logging.info(f"selected_nome_colaborador: {selected_nome_colaborador}")
    logging.info(f"selected_teams: {selected_teams}")

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
    
def get_monthly_revenue(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands, selected_nome_colaborador,selected_teams):
    # Inicialização de variáveis
    brand_filter = ""
    channel_filter = ""
    uf_filter = ""
    colaborador_filter = ""
    group_by_cols = "1, fator"
    group_by_cols_acum = "1"
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
    if cod_colaborador or selected_nome_colaborador:
        colaborador_filter = ""
        if cod_colaborador:
            colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
        elif selected_nome_colaborador:
            # Apenas aplique o filtro de nome se não houver um código de colaborador
            nome_str = "', '".join(selected_nome_colaborador)
            colaborador_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"    
       
        group_by_cols = "1, 2, 3, fator"
        group_by_cols_acum = "1, 2, 3"
    
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
        group_by_cols = "1, fator"
        group_by_cols_acum = "1"
        select_cols_subquery = ""
        select_cols_subquery_alias = ""
        select_cols_main = ""
        nome_filter = ""

    if selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        nome_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"

    team_filter = f"AND empresa_pedido.equipes IN ('{', '.join(selected_teams)}')" if selected_teams else ""

    
    query = f"""
    WITH bonificacao AS (
        SELECT 
            mes_ref,
            {select_cols_subquery_alias}
            ROUND(SUM(valor_bonificacao_ajustada),2) valor_bonificacao
    FROM (
            SELECT
                DATE_TRUNC('month', dt_faturamento) mes_ref,
                {select_cols_subquery}
                CASE WHEN fator IS NULL Then ROUND(SUM(item_pedidos.preco_total), 2)
                Else ROUND(SUM(item_pedidos.preco_total)/fator,2) END AS valor_bonificacao_ajustada
            FROM
                "databeautykami"."vw_distribuicao_pedidos" pedidos
            LEFT JOIN "databeautykami"."vw_distribuicao_item_pedidos" AS item_pedidos 
                ON pedidos."cod_pedido" = item_pedidos."cod_pedido"
            LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
                ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
            LEFT JOIN "databeautykami".tbl_distribuicao_bonificacao bonificacao
                ON cast(bonificacao.cod_empresa as varchar) = empresa_pedido.cod_empresa_faturamento 
                and date(bonificacao.mes_ref) = DATE_TRUNC('month', dt_faturamento)
            LEFT JOIN "databeautykami".tbl_varejo_marca marca ON marca.cod_marca = bonificacao.cod_marca
                and upper(trim(marca.desc_abrev)) = upper(trim(item_pedidos.marca))
            WHERE
                upper(pedidos."desc_abrev_cfop") = 'BONIFICADO'
                AND pedidos.operacoes_internas = 'N'
                {colaborador_filter}
                {channel_filter}
                {uf_filter}
                {brand_filter}  
                {team_filter}
            GROUP BY {group_by_cols}
        )   boni 
    group by {group_by_cols_acum}
    )
    SELECT
        f.mes_ref,
        {select_cols_main}
        f.faturamento_bruto,
        f.faturamento_liquido,
        f.desconto,
        COALESCE(b.valor_bonificacao, 0) AS valor_bonificacao,
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
        DATE_TRUNC('month', pedidos.dt_faturamento) mes_ref,
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
                Else ROUND(SUM(qtd * (custo_unitario/fator)) / NULLIF(SUM(qtd), 0), 2)  END custo_medio
            FROM "databeautykami".tbl_varejo_cmv left join "databeautykami".tbl_distribuicao_bonificacao
            ON tbl_varejo_cmv.cod_marca = tbl_distribuicao_bonificacao.cod_marca
            and tbl_varejo_cmv.cod_empresa = cast(tbl_distribuicao_bonificacao.cod_empresa as varchar)
            and DATE_TRUNC('month', dt_faturamento) = date(tbl_distribuicao_bonificacao.mes_ref)
            GROUP BY 1, 2, 3, fator 
            UNION ALL 
            SELECT
                cod_pedido,
                codprod,
                DATE_TRUNC('month', dtvenda) mes_ref,
                CASE WHEN fator IS NULL Then ROUND(SUM(quant * custo) / NULLIF(SUM(quant), 0), 2)
                Else ROUND(SUM(quant * (custo/fator)) / NULLIF(SUM(quant), 0), 2)  END custo_medio
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
    group by {group_by_cols_acum}
    ) f
    LEFT JOIN bonificacao b ON f.mes_ref = b.mes_ref 
        {' AND f.cod_colaborador = b.cod_colaborador' if cod_colaborador or selected_nome_colaborador else ''}
    ORDER BY f.mes_ref{', f.vendedor' if cod_colaborador or selected_nome_colaborador else ''}
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

def get_brand_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador,selected_teams):
    colaborador_filter = ""
    if isinstance(selected_nome_colaborador, str):  # Para vendedores
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{selected_nome_colaborador}'"
    elif selected_nome_colaborador:  # Para admin/gestor
        colaborador_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{', '.join(selected_nome_colaborador)}')"
    elif cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"

    channel_filter = f"AND pedidos.canal_venda IN ('{', '.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{', '.join(selected_ufs)}')" if selected_ufs else ""
    team_filter = f"AND empresa_pedido.equipes IN ('{', '.join(selected_teams)}')" if selected_teams else ""

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
                Else ROUND(SUM(qtd * (custo_unitario/fator)) / NULLIF(SUM(qtd), 0), 2)  END custo_medio
            FROM "databeautykami".tbl_varejo_cmv left join "databeautykami".tbl_distribuicao_bonificacao
                ON tbl_varejo_cmv.cod_marca = tbl_distribuicao_bonificacao.cod_marca
                and tbl_varejo_cmv.cod_empresa = cast(tbl_distribuicao_bonificacao.cod_empresa as varchar)
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
                    Else ROUND(SUM(quant * (custo/fator)) / NULLIF(SUM(quant), 0), 2)  END custo_medio
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

@st.cache_data
def get_team_options(start_date, end_date):
    query = f"""
    SELECT DISTINCT empresa_pedido.equipes
    FROM "databeautykami"."vw_distribuicao_pedidos" pedidos
    LEFT JOIN "databeautykami"."vw_distribuicao_empresa_pedido" AS empresa_pedido 
        ON pedidos."cod_pedido" = empresa_pedido."cod_pedido"
    WHERE date(pedidos."dt_faturamento") BETWEEN date('{start_date}') AND date('{end_date}')
        AND empresa_pedido.equipes IS NOT NULL
        AND empresa_pedido.equipes != ''
    ORDER BY empresa_pedido.equipes
    """
    df = query_athena(query)
    return df['equipes'].tolist() if not df.empty else []

def get_rfm_summary(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores):
    # Adicione a lógica para filtrar por selected_colaboradores
    colaborador_filter = ""
    if cod_colaborador:
        colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_colaboradores:
        colaboradores_str = "', '".join(selected_colaboradores)
        colaborador_filter = f"AND b.nome_colaborador_atual IN ('{colaboradores_str}')"
    
    channel_filter = ""
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = f"AND a.Canal_Venda IN ('{channels_str}')"

    uf_filter = ""
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = f"AND a.uf_empresa IN ('{ufs_str}')"

    #team_filter = f"AND c.equipes IN ('{', '.join(selected_teams)}')" if selected_teams else ""        

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
            databeautykami.vw_analise_perfil_cliente a
        LEFT JOIN
            databeautykami.vw_distribuicao_cliente_vendedor b ON a.Cod_Cliente = b.cod_cliente
        
        WHERE 1 = 1         
        {colaborador_filter}
        {channel_filter}
        {uf_filter}

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
                    WHEN R_Score <= 3 AND F_Score BETWEEN 2 and 3 THEN 'Em risco'                 
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

def get_rfm_segment_clients(cod_colaborador, start_date, end_date, segmentos, selected_channels, selected_ufs, selected_colaboradores):
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
        colaborador_filter = f"AND b.nome_colaborador_atual IN ('{colaboradores_str}')"
    
    segmentos_query = get_segmentos_query(segmentos)
    
    channel_filter = f"AND a.Canal_Venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND a.uf_empresa IN ('{','.join(selected_ufs)}')" if selected_ufs else ""

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
            a.Maior_Mes as Mes_Ultima_Compra,
            a.Ciclo_Vida as Life_Time,
            a.marcas_concatenadas,
            c.status status_inadimplente,
            c.qtd_titulos,
            c.vlr_inadimplente
        FROM
            databeautykami.vw_analise_perfil_cliente a
        LEFT JOIN databeautykami.vw_distribuicao_cliente_vendedor b 
            ON a.Cod_Cliente = b.cod_cliente
        LEFT JOIN databeautykami.tbl_distribuicao_clientes_inadimplentes c 
            ON a.Cod_Cliente = c.Cod_Cliente and a.uf_empresa = c.uf_empresa     
        WHERE 1 = 1 
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
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
                    WHEN R_Score <= 3 AND F_Score BETWEEN 2 and 3 THEN 'Em risco'                 
                    WHEN R_Score >= 3 AND F_Score >= 3 AND M_Score >= 2 THEN 'Potencial'
                    ELSE 'Acompanhar'
                END AS Segmento
        FROM
            rfm_scores
    )
    SELECT
        Cod_Cliente,
        Nome_Cliente,
        uf_empresa,
        Canal_Venda,
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
    
    logging.info(f"Query construída:")
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

def get_rfm_heatmap_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_colaboradores):
    if cod_colaborador or selected_colaboradores:
        colaborador_filter = ""
        if cod_colaborador:
            colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'"
        elif selected_colaboradores:
            # Apenas aplique o filtro de nome se não houver um código de colaborador
            nome_str = "', '".join(selected_colaboradores)
            colaborador_filter = f"AND b.nome_colaborador_atual IN ('{nome_str}')"
    else:
        colaborador_filter = ""

    channel_filter = f"AND a.Canal_Venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND a.uf_empresa IN ('{','.join(selected_ufs)}')" if selected_ufs else ""
    #team_filter = f"AND c.equipes IN ('{', '.join(selected_teams)}')" if selected_teams else ""

    query = f"""
    WITH rfm_base AS (
        SELECT
            a.Recencia,
            a.Positivacao AS Frequencia
        FROM
            databeautykami.vw_analise_perfil_cliente a
        LEFT JOIN
            databeautykami.vw_distribuicao_cliente_vendedor b ON a.Cod_Cliente = b.cod_cliente
                    
        WHERE 1 = 1 
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
  
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

def get_client_status(start_date, end_date, cod_colaborador, selected_channels, selected_ufs, selected_nome_colaborador, selected_brands,selected_teams):

    colaborador_filter = ""
    if cod_colaborador or selected_nome_colaborador:
            colaborador_filter = ""
    if cod_colaborador:
            colaborador_filter = f"AND vw_distribuicao_empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
    elif selected_nome_colaborador:
        # Apenas aplique o filtro de nome se não houver um código de colaborador
        nome_str = "', '".join(selected_nome_colaborador)
        colaborador_filter = f"AND vw_distribuicao_empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"
  
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

    team_filter = f"AND vw_distribuicao_empresa_pedido.equipes IN ('{', '.join(selected_teams)}')" if selected_teams else ""        

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
            databeautykami.vw_distribuicao_pedidos 
        LEFT JOIN
            databeautykami.vw_distribuicao_item_pedidos ON vw_distribuicao_pedidos.cod_pedido = vw_distribuicao_item_pedidos.cod_pedido
        LEFT JOIN 
            databeautykami.vw_distribuicao_empresa_pedido ON vw_distribuicao_empresa_pedido.cod_pedido = vw_distribuicao_pedidos.cod_pedido
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