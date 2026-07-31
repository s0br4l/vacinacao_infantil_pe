import pandas as pd


def run_medallion_pipeline():
    # 1. Carrega Bronze
    df_bronze = pd.read_parquet("data/bronze/vacinacao_infantil_pe.parquet")

    # 2. Camada SILVER: Limpeza e formatação
    df_silver = df_bronze.copy()
    df_silver['data_aplicacao'] = pd.to_datetime(df_silver['data_aplicacao'])
    df_silver['municipio'] = df_silver['municipio'].str.strip()
    df_silver.to_parquet("data/silver/vacinacao_infantil_pe.parquet", index=False)

    # 3. Camada GOLD: Agregação mantendo as dimensões dos Filtros (Vacina, Dose, Faixa Etária)
    df_gold = df_silver.groupby(['codigo_ibge', 'municipio', 'vacina', 'dose', 'faixa_etaria']).agg(
        total_doses=('doses_aplicadas', 'sum'),
        ultima_atualizacao=('data_aplicacao', 'max')
    ).reset_index()

    df_gold.to_parquet("data/gold/vacinacao_pe_agregado.parquet", index=False)
    return df_gold