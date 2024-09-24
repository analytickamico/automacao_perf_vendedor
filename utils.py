import os
import logging
from pyathena import connect
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pyathena.pandas.util import as_pandas
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta
from streamlit_plotly_events import plotly_events
import numpy as np



# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Carregar variáveis de ambiente
load_dotenv()

# Configurações de conexão Athena
ATHENA_S3_STAGING_DIR = os.environ.get('ATHENA_S3_STAGING_DIR', 's3://databeautykamico/Athena/')
ATHENA_REGION = os.environ.get('ATHENA_REGION', 'us-east-1')

logging.info(f"Usando ATHENA_S3_STAGING_DIR: {ATHENA_S3_STAGING_DIR}")
logging.info(f"Usando ATHENA_REGION: {ATHENA_REGION}")

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
    
def get_monthly_revenue(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_brands,selected_nome_colaborador):
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
    if cod_colaborador:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'"
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
    nome_filter = ""
    if selected_nome_colaborador:
        nome_str = "', '".join(selected_nome_colaborador)
        nome_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"

    
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
                upper(pedidos."desc_abrev_cfop") LIKE '%BONIFICA%'
                AND pedidos.operacoes_internas = 'N'
                {colaborador_filter}
                {channel_filter}
                {uf_filter}
                {brand_filter}
                {nome_filter}
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
        {colaborador_filter}
        {channel_filter}
        {uf_filter}
        {brand_filter}
        {nome_filter}
    group by {group_by_cols_acum}
    ) f
    LEFT JOIN bonificacao b ON f.mes_ref = b.mes_ref {' AND f.cod_colaborador = b.cod_colaborador' if cod_colaborador else ''}
    ORDER BY f.mes_ref{', f.vendedor' if cod_colaborador else ''}
    """
    
    logging.info(f"Query executada: {query}")
    
    df = query_athena(query)
    return df

def get_brand_data(cod_colaborador, start_date, end_date, selected_channels, selected_ufs, selected_nome_colaborador):
    try:
        colaborador_filter = f"AND empresa_pedido.cod_colaborador_atual = '{cod_colaborador}'" if cod_colaborador else ""

        channel_filter = ""
        if selected_channels:
            channels_str = "', '".join(selected_channels)
            channel_filter = f"AND pedidos.canal_venda IN ('{channels_str}')"
        
        uf_filter = ""
        if selected_ufs:
            ufs_str = "', '".join(selected_ufs)
            uf_filter = f"AND empresa_pedido.uf_empresa_faturamento IN ('{ufs_str}')"

        nome_filter = ""
        if selected_nome_colaborador:
            nome_str = "', '".join(selected_nome_colaborador)
            nome_filter = f"AND empresa_pedido.nome_colaborador_atual IN ('{nome_str}')"            
        
        query = f"""
        SELECT
        f.marca,
        f.faturamento_liquido AS faturamento,
        f.positivacao AS clientes_unicos,
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
                item_pedidos.marca,
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
                {colaborador_filter}
                {channel_filter}
                {uf_filter}
                {nome_filter}
                GROUP BY 1
            ) f
            ORDER BY f.faturamento_liquido DESC
       
        """
        logging.info(f"Executando query para dados de marca: {query}")
        df = query_athena(query)
        logging.info(f"Query para dados de marca executada com sucesso. Retornando DataFrame com {len(df)} linhas.")
        logging.info(f"Colunas retornadas: {df.columns.tolist()}")
        logging.info(f"Tipos de dados das colunas:\n{df.dtypes}")
        logging.info(f"Primeiras linhas do DataFrame:\n{df.head().to_string()}")
        return df
    except Exception as e:
        logging.error(f"Erro ao obter dados de marca: {str(e)}", exc_info=True)
        return pd.DataFrame()
    
def get_rfm_summary(cod_colaborador, start_date, end_date, selected_channels, selected_ufs):
    colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'" if cod_colaborador else ""
    
    channel_filter = ""
    if selected_channels:
        channels_str = "', '".join(selected_channels)
        channel_filter = f"AND a.Canal_Venda IN ('{channels_str}')"
    
    uf_filter = ""
    if selected_ufs:
        ufs_str = "', '".join(selected_ufs)
        uf_filter = f"AND a.uf_empresa IN ('{ufs_str}')"

    query = f"""
    WITH rfm_base AS (
        SELECT
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
                WHEN R_Score = 5 AND F_Score = 5  THEN 'Campeões'
                WHEN R_Score >= 4 AND F_Score >= 4  THEN 'Clientes fiéis'
                WHEN R_Score = 5 AND F_Score <= 2 THEN 'Novos clientes'
                WHEN R_Score <= 2 AND F_Score <= 3 THEN 'Em risco'
                WHEN R_Score = 1 AND F_Score = 1 THEN 'Perdidos'
                WHEN R_Score = 3 AND F_Score = 1  THEN 'Atenção'
                ELSE 'Outros'
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
        AVG(R_Score) AS R_Score_Medio,
        AVG(F_Score) AS F_Score_Medio,
        AVG(M_Score) AS M_Score_Medio
    FROM
        rfm_segments
    GROUP BY
        Segmento, Canal_Venda, uf_empresa
    ORDER BY
        Valor_Total DESC, Canal_Venda;
    """
    return query_athena(query)

def get_rfm_segment_clients(cod_colaborador, start_date, end_date, segment, selected_channels, selected_ufs):
    colaborador_filter = f"AND b.cod_colaborador_atual = '{cod_colaborador}'" if cod_colaborador else ""
    channel_filter = f"AND a.Canal_Venda IN ('{','.join(selected_channels)}')" if selected_channels else ""
    uf_filter = f"AND a.uf_empresa IN ('{','.join(selected_ufs)}')" if selected_ufs else ""

    query = f"""
    WITH rfm_base AS (
        SELECT
            a.Cod_Cliente,
            a.Nome_Cliente,
            a.uf_empresa,
            a.Canal_Venda,
            a.Recencia,
            a.Positivacao AS Frequencia,
            a.Monetario,
            a.ticket_medio_posit,
            b.cod_colaborador_atual,
            a.Maior_Mes as Mes_Ultima_Compra,
            a.Ciclo_Vida as Life_Time
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
                WHEN R_Score = 5 AND F_Score = 5  THEN 'Campeões'
                WHEN R_Score >= 3 AND F_Score >= 3  THEN 'Clientes fiéis'
                WHEN R_Score = 5 AND F_Score <= 2 THEN 'Novos clientes'
                WHEN R_Score <= 2 AND F_Score <= 3 THEN 'Em risco'
                WHEN R_Score = 1 AND F_Score = 1 THEN 'Perdidos'
                WHEN R_Score = 3 AND F_Score = 1  THEN 'Atenção'
                ELSE 'Outros'
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
        Frequencia,
        Monetario,
        ticket_medio_posit,
        R_Score,
        F_Score,
        M_Score,
        Mes_Ultima_Compra,
        Life_time,
        Segmento
    FROM
        rfm_segments
    WHERE
        Segmento = '{segment}'
    ORDER BY
        Monetario DESC, Canal_Venda;
    """
    return query_athena(query)

def create_rfm_heatmap(rfm_summary):
    #st.write("Dados do RFM Summary:")
    #st.write(rfm_summary)

    # Verificar se as colunas necessárias existem
    required_columns = ['R_Score_Medio', 'F_Score_Medio', 'Numero_Clientes']
    missing_columns = [col for col in required_columns if col not in rfm_summary.columns]
    if missing_columns:
        st.error(f"Colunas ausentes no DataFrame: {', '.join(missing_columns)}")
        return None

    # Criando a matriz de contagem
    heatmap_data = pd.DataFrame(index=range(1, 6), columns=range(1, 6))
    heatmap_data = heatmap_data.fillna(0)

    try:
        for _, row in rfm_summary.iterrows():
            r_score = int(round(row['R_Score_Medio']))
            f_score = int(round(row['F_Score_Medio']))
            num_clients = row['Numero_Clientes']
            
            # Garantir que os scores estão dentro do intervalo 1-5
            r_score = max(1, min(5, r_score))
            f_score = max(1, min(5, f_score))
            
            heatmap_data.at[r_score, f_score] += num_clients

        #st.write("Mapa de calor gerado:")
        #st.write(heatmap_data)

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
            xaxis=dict(tickmode='array', tickvals=list(range(1, 6)), ticktext=[str(i) for i in range(1, 6)]),
            yaxis=dict(tickmode='array', tickvals=list(range(1, 6)), ticktext=[str(i) for i in range(1, 6)])
        )

        return fig
    except Exception as e:
        st.error(f"Erro ao criar o mapa de calor: {str(e)}")
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