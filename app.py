import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os
import json
from datetime import datetime
from pipeline.fetcher import sync_data
from pipeline.etl import run_medallion_pipeline

st.set_page_config(page_title="Vigilância Vacinal Infantil - PE", layout="wide")

st.title("💉 Monitoramento de Vacinação Infantil em Pernambuco")
st.markdown("Plataforma interativa para análise de cobertura vacinal e vigilância municipal.")

# --- SIDEBAR: Painel de Controle e Filtros ---
st.sidebar.header("⚙️ Painel de Controle")

gold_path = "data/gold/vacinacao_pe_agregado.parquet"
if os.path.exists(gold_path):
    mod_time = datetime.fromtimestamp(os.path.getmtime(gold_path)).strftime('%d/%m/%Y às %H:%M')
    st.sidebar.info(f"📅 **Última atualização local:**\n{mod_time}")

if st.sidebar.button("🔄 Atualizar Dados Agora"):
    with st.spinner("Atualizando base de dados de Pernambuco..."):
        updated, msg = sync_data(force=True)
        if updated:
            run_medallion_pipeline()
            st.sidebar.success(msg)
            st.rerun()
        else:
            st.sidebar.info(msg)

st.sidebar.divider()
st.sidebar.header("🔍 Filtros de Análise")

if os.path.exists(gold_path):
    df_gold = pd.read_parquet(gold_path)
    df_gold['codigo_ibge'] = df_gold['codigo_ibge'].astype(str)

    # 1. Filtro de Vacinas
    vacinas_opts = sorted(df_gold['vacina'].unique().tolist()) if 'vacina' in df_gold.columns else []
    vacinas_sel = st.sidebar.multiselect("Vacina(s):", options=vacinas_opts, default=vacinas_opts)

    # 2. Filtro de Dose
    doses_opts = sorted(df_gold['dose'].unique().tolist()) if 'dose' in df_gold.columns else []
    doses_sel = st.sidebar.multiselect("Dose / Esquema:", options=doses_opts, default=doses_opts)

    # 3. Filtro de Faixa Etária
    faixas_opts = sorted(df_gold['faixa_etaria'].unique().tolist()) if 'faixa_etaria' in df_gold.columns else []
    faixas_sel = st.sidebar.multiselect("Faixa Etária:", options=faixas_opts, default=faixas_opts)

    # Aplicação Combinada dos Filtros
    df_filtrado = df_gold.copy()
    if vacinas_sel:
        df_filtrado = df_filtrado[df_filtrado['vacina'].isin(vacinas_sel)]
    if doses_sel:
        df_filtrado = df_filtrado[df_filtrado['dose'].isin(doses_sel)]
    if faixas_sel:
        df_filtrado = df_filtrado[df_filtrado['faixa_etaria'].isin(faixas_sel)]

    # Agrupamento Totais por Município
    df_totais = df_filtrado.groupby(['codigo_ibge', 'municipio'])['total_doses'].sum().reset_index()

    # --- CORPO PRINCIPAL: KPIs ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Doses Aplicadas", f"{df_filtrado['total_doses'].sum():,}")
    col2.metric("Municípios Exibidos", df_totais['municipio'].nunique())
    vacina_top = df_filtrado.groupby('vacina')['total_doses'].sum().idxmax() if not df_filtrado.empty else "N/A"
    col3.metric("Vacina Destaque no Filtro", vacina_top)

    st.subheader("🗺️ Distribuição Geográfica e Detalhamento Municipal")

    # Mapa Folium
    m = folium.Map(location=[-8.3833, -37.8647], zoom_start=7, tiles="cartodbpositron")

    geojson_path = "geo/pe_municipios.json"
    if os.path.exists(geojson_path):
        with open(geojson_path, "r", encoding="utf-8") as f:
            geo_data = json.load(f)

        # Prepara a discriminação por vacina em formato HTML para o Popup de cada município
        popup_dict = {}
        totais_dict = dict(zip(df_totais['codigo_ibge'], df_totais['total_doses']))

        for ibge_id, group in df_filtrado.groupby('codigo_ibge'):
            nome_mun = group['municipio'].iloc[0]
            total_mun = totais_dict.get(ibge_id, 0)

            # Monta lista de vacinas e quantidades
            vacinas_detalhe = group.groupby('vacina')['total_doses'].sum().reset_index()
            html_vacinas = "".join(
                [f"<li><b>{r['vacina']}:</b> {r['total_doses']:,}</li>" for _, r in vacinas_detalhe.iterrows()])

            # HTML bonito formatado para o Popup
            html_popup = f"""
            <div style="font-family: Arial; width: 220px;">
                <h4 style="margin-bottom: 2px;">{nome_mun}</h4>
                <p style="margin-top:0; color: #555;"><b>Total Geral:</b> {total_mun:,} doses</p>
                <hr style="border: 0.5px solid #ccc;"/>
                <b style="font-size: 12px;">Discriminação por Vacina:</b>
                <ul style="padding-left: 15px; margin-top: 5px; font-size: 12px;">
                    {html_vacinas}
                </ul>
            </div>
            """
            popup_dict[ibge_id] = html_popup

        # Injeta as propriedades diretamente nas features do GeoJSON
        for feature in geo_data['features']:
            mun_id = str(feature['properties']['id'])
            feature['properties']['total_doses'] = totais_dict.get(mun_id, 0)
            feature['properties']['html_popup'] = popup_dict.get(
                mun_id,
                f"<b>{feature['properties']['name']}</b><br>Sem dados para os filtros selecionados."
            )

        # Camada do Mapa Coroplético
        folium.Choropleth(
            geo_data=geo_data,
            name="choropleth",
            data=df_totais,
            columns=["codigo_ibge", "total_doses"],
            key_on="feature.properties.id",
            fill_color="YlOrRd",
            fill_opacity=0.7,
            line_opacity=0.3,
            legend_name="Total de Doses Aplicadas",
            nan_fill_color="gray",
            nan_fill_opacity=0.2
        ).add_to(m)

        # Adiciona Interatividade com Tooltip e Popup HTML discriminado
        geojson_layer = folium.GeoJson(
            geo_data,
            style_function=lambda x: {'color': 'transparent', 'fillColor': 'transparent'},
            tooltip=folium.GeoJsonTooltip(
                fields=['name', 'total_doses'],
                aliases=['Município:', 'Total Doses:'],
                localize=True
            )
        )
        # Adiciona o Popup dinâmico baseado no campo HTML de cada município
        geojson_layer.add_child(folium.features.GeoJsonPopup(fields=['html_popup'], labels=False))
        geojson_layer.add_to(m)

    st_folium(m, width=1100, height=520)

    # --- GRÁFICO TOP 10 ---
    st.divider()
    st.subheader("📊 Top 10 Municípios com Maior Volume de Doses")
    top_10 = df_totais.sort_values(by="total_doses", ascending=False).head(10)

    fig = px.bar(
        top_10,
        x="municipio",
        y="total_doses",
        text_auto=',.0f',
        labels={'municipio': 'Município', 'total_doses': 'Total de Doses'},
        color='total_doses',
        color_continuous_scale='Reds'
    )
    fig.update_layout(
        xaxis_title="",
        yaxis_title="Doses Aplicadas",
        yaxis=dict(range=[0, top_10['total_doses'].max() * 1.15]),
        coloraxis_showscale=False
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Clique no botão 'Atualizar Dados Agora' na barra lateral para carregar a base.")