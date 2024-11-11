import requests
import pandas as pd
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pyathena import connect
from pyathena.pandas.cursor import PandasCursor


# Parâmetros de conexão
athena_region = "us-east-1"
database_name = "databeautykami"
query = """
WITH paginated_data AS (
    SELECT distinct
        ROW_NUMBER() OVER (ORDER BY tbl_distribuicao_cliente_pedido.cod_cliente) AS row_num,
        tbl_distribuicao_cliente_pedido.cod_cliente,
        cnpj_cliente, 
        endereco, 
        numero, 
        bairro, 
        cep, 
        cidade, 
        uf_cliente
    FROM databeautykami.tbl_distribuicao_cliente_pedido 
    INNER JOIN databeautykami.vw_distribuicao_pedidos ON cod_pedido = nr_ped_compra_cli
    WHERE dt_faturamento BETWEEN date('2024-01-01') AND date('2024-10-30')
    group by 2,3,4,5,6,7,8,9
)
SELECT distinct
    cod_cliente,
    cnpj_cliente, 
    endereco, 
    numero, 
    bairro, 
    cep, 
    cidade, 
    uf_cliente as estado
FROM paginated_data
WHERE row_num > 5000
"""

# Parâmetros da API de Geocodificação (OpenCage)
API_KEY = '9fab6a74ca0247beb1c794f68ef4129b'

# Função para geocodificar um endereço
def geocode_address(address):
    try:
        response = requests.get(
            'https://api.opencagedata.com/geocode/v1/json',
            params={'q': address, 'key': API_KEY}
        )
        if response.status_code == 200:
            data = response.json()
            if data['results']:
                location = data['results'][0]['geometry']
                return {'lat': location['lat'], 'lng': location['lng']}
            else:
                print(f"No results found for address: {address}")
                return None
        else:
            print(f"Error {response.status_code} for address: {address}")
            return None
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
        return None

# Conectar ao Athena e ler a tabela de endereços
def fetch_addresses_from_athena():
    conn = connect(s3_staging_dir="s3://databeautykamico/athena",
                   region_name=athena_region,
                   cursor_class=PandasCursor)
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Processar DataFrame e adicionar coordenadas
def process_addresses(df):
    df['endereco_completo'] = df.apply(lambda row: f"{row['endereco']}, {row['bairro']}, {row['cidade']}, {row['estado']}, {row['cep']}, Brasil", axis=1)
    coordinates = []
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(geocode_address, df['endereco_completo']))
        for result in results:
            if result:
                coordinates.append(result)
            else:
                coordinates.append({'lat': None, 'lng': None})
    
    df['latitude'] = [coord['lat'] for coord in coordinates]
    df['longitude'] = [coord['lng'] for coord in coordinates]
    return df[['cod_cliente', 'latitude', 'longitude']]

# Armazenar os resultados no SQLite
def store_in_sqlite(df):
    conn = sqlite3.connect('enderecos_geocodificados_02.db')
    df.to_sql('coordenadas', conn, if_exists='replace', index=False)
    conn.close()

# Armazenar os resultados em CSV
def store_in_csv(df):
    df.to_csv('enderecos_geocodificados_02.csv', index=False)

# Execução do fluxo
if __name__ == "__main__":
    # 1. Buscar endereços do Athena
    df_enderecos = fetch_addresses_from_athena()
    # 2. Processar e obter coordenadas
    df_coordenadas = process_addresses(df_enderecos)
    # 3. Armazenar em SQLite
    store_in_sqlite(df_coordenadas)
    # 4. Armazenar em CSV (opcional)
    store_in_csv(df_coordenadas)
    print("Processo concluído com sucesso!")
