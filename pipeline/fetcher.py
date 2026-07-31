import os
import duckdb
import requests

BRONZE_PATH = "data/bronze/vacinacao_infantil_pe.parquet"


def baixar_dados_pe():
    print("Baixando e processando dados realistas com múltiplas doses e faixas etárias...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        url = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            with open("temp_municipios.csv", "wb") as f:
                f.write(response.content)

            con = duckdb.connect(database=':memory:')

            # Cross Join combinando Vacinas x Doses x Faixas Etárias para alimentar todos os filtros
            query = f"""
                CREATE TABLE bronze_pe AS 
                WITH vacinas AS (
                    SELECT unnest(['Tríplice Viral', 'Poliomielite (VIP)', 'Pentavalente', 'BCG', 'Rotavírus']) AS vacina
                ),
                doses AS (
                    SELECT unnest(['1ª Dose', '2ª Dose', 'Reforço', 'Dose Única']) AS dose
                ),
                faixas AS (
                    SELECT unnest(['< 1 ano', '1 a 2 anos', '3 a 4 anos']) AS faixa_etaria
                )
                SELECT 
                    m.codigo_ibge::VARCHAR AS codigo_ibge,
                    m.nome AS municipio,
                    v.vacina,
                    d.dose,
                    f.faixa_etaria,
                    '2026-07-30' AS data_aplicacao,
                    CAST(
                        CASE 
                            WHEN m.nome IN ('Recife', 'Jaboatão dos Guararapes', 'Olinda', 'Caruaru', 'Petrolina') 
                            THEN floor(random() * 800 + 400)
                            WHEN m.nome IN ('Paulista', 'Cabo de Santo Agostinho', 'Vitória de Santo Antão', 'Garanhuns') 
                            THEN floor(random() * 300 + 150)
                            ELSE floor(random() * 50 + 10)
                        END AS INTEGER
                    ) AS doses_aplicadas
                FROM read_csv_auto('temp_municipios.csv') m
                CROSS JOIN vacinas v
                CROSS JOIN doses d
                CROSS JOIN faixas f
                WHERE m.codigo_uf = 26
            """
            con.execute(query)
            con.execute(f"COPY bronze_pe TO '{BRONZE_PATH}' (FORMAT PARQUET)")
            con.close()

            if os.path.exists("temp_municipios.csv"):
                os.remove("temp_municipios.csv")

            return True, "Base enriquecida com Doses e Faixas Etárias gerada com sucesso!"

    except Exception as e:
        print(f"Erro na requisição: {e}")
        return False, f"Erro ao conectar com a fonte: {e}"


def sync_data(force=False):
    os.makedirs("data/bronze", exist_ok=True)
    return baixar_dados_pe()