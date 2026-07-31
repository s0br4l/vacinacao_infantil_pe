from fastapi import FastAPI, HTTPException
import pandas as pd
import os

app = FastAPI(
    title="API de Vigilância Vacinal Infantil - PE",
    description="API REST para consumo de dados agregados da camada Gold do pipeline Medallion.",
    version="1.0.0"
)

GOLD_PATH = "data/gold/vacinacao_pe_agregado.parquet"


def load_gold_data():
    """Função utilitária para carregar os dados da camada Gold."""
    if not os.path.exists(GOLD_PATH):
        raise HTTPException(
            status_code=404,
            detail="Dados da camada Gold ainda não foram gerados. Rode o pipeline de ETL primeiro."
        )
    return pd.read_parquet(GOLD_PATH)


@app.get("/")
def home():
    return {
        "status": "online",
        "mensagem": "API de Vigilância Vacinal Infantil de Pernambuco",
        "endpoints": ["/api/v1/indicadores", "/api/v1/municipios", "/api/v1/municipio/{codigo_ibge}"]
    }


@app.get("/api/v1/indicadores")
def get_indicadores_gerais():
    """Retorna métricas gerais/consolidadas do estado de Pernambuco."""
    df = load_gold_data()
    total_doses = int(df['total_doses'].sum())
    total_municipios = int(df['municipio'].nunique())

    return {
        "estado": "PE",
        "total_doses_aplicadas": total_doses,
        "municipios_cobertos": total_municipios,
        "ultima_atualizacao": str(df['ultima_atualizacao'].max())
    }


@app.get("/api/v1/municipios")
def get_todos_municipios():
    """Retorna a lista completa de municípios e suas respectivas doses aplicadas."""
    df = load_gold_data()
    # Converte o DataFrame para lista de dicionários (JSON)
    dados = df.to_dict(orient="records")
    return {"quantidade": len(dados), "dados": dados}


@app.get("/api/v1/municipio/{codigo_ibge}")
def get_municipio_por_ibge(codigo_ibge: str):
    """Retorna os dados filtrados por um código IBGE específico."""
    df = load_gold_data()
    df_filtrado = df[df['codigo_ibge'] == codigo_ibge]

    if df_filtrado.empty:
        raise HTTPException(status_code=404, detail=f"Município com código IBGE '{codigo_ibge}' não encontrado.")

    return df_filtrado.to_dict(orient="records")