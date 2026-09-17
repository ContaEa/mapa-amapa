import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import time
from io import BytesIO

# Configuração da página do Streamlit
st.set_page_config(page_title="Mapa de Calor de Clientes", layout="wide")
st.title("🗺️ Mapa de Calor - Referência vs. Convertidos")

# Função para carregar os dados das planilhas do Excel (.xlsx)
@st.cache_data
def carregar_dados():
    df_ref = pd.read_excel("seus_dados.xlsx", engine="openpyxl")
    df_conv = pd.read_excel("convertidos.xlsx", engine="openpyxl")
    
    # CORREÇÃO PARA COLUNAS DUPLICADAS: Renomeia se houver nomes repetidos no Excel
    def renomear_duplicados(df):
        cols = []
        counts = {}
        for col in df.columns:
            c = str(col).strip()
            if c in counts:
                counts[c] += 1
                cols.append(f"{c}_{counts[c]}")
            else:
                counts[c] = 1
                cols.append(c)
        df.columns = cols
        return df

    df_ref = renomear_duplicados(df_ref)
    df_conv = renomear_duplicados(df_conv)
    
    return df_ref, df_conv

try:
    df_ref, df_conv = carregar_dados()
except FileNotFoundError:
    st.error("Erro: Não encontrei os arquivos Excel. Garanta que os nomes sejam exatamente 'seus_dados.xlsx' e 'convertidos.xlsx' e que estejam na mesma pasta.")
    st.stop()

# --- DIAGNÓSTICO E MAPEAMENTO DE COLUNAS ---
colunas_ref_minusculo = [c.lower() for c in df_ref.columns]
colunas_conv_minusculo = [c.lower() for c in df_conv.columns]

# Encontra a primeira coluna que dá correspondência com o que precisamos (mesmo se renomeada)
def encontrar_coluna_real(lista_colunas, alvo):
    for col in lista_colunas:
        if col.lower() == alvo or col.lower().startswith(f"{alvo}_"):
            return col
    return None

col_muni_ref = encontrar_coluna_real(df_ref.columns, 'municipio')
col_clie_ref = encontrar_coluna_real(df_ref.columns, 'cliente')

col_muni_conv = encontrar_coluna_real(df_conv.columns, 'municipio')
col_aten_conv = encontrar_coluna_real(df_conv.columns, 'atendente')
col_apon_conv = encontrar_coluna_real(df_conv.columns, 'apontador')

# Verifica erros de colunas em falta nas planilhas
erros_colunas = []
if not col_muni_ref: erros_colunas.append("municipio (na planilha seus_dados)")
if not col_clie_ref: erros_colunas.append("cliente (na planilha seus_dados)")
if not col_muni_conv: erros_colunas.append("municipio (na planilha convertidos)")
if not col_aten_conv: erros_colunas.append("atendente (na planilha convertidos)")
if not col_apon_conv: erros_colunas.append("apontador (na planilha convertidos)")

if erros_colunas:
    st.error(f"🛑 Erro de correspondência! O Python não encontrou as seguintes colunas: {erros_colunas}")
    st.write("---")
    st.write("### 🔍 Colunas lidas nos seus arquivos atuais:")
    col1, col2 = st.columns(2)
    col1.write("**Colunas em 'seus_dados.xlsx':**")
    col1.write(list(df_ref.columns))
    col2.write("**Colunas em 'convertidos.xlsx':**")
    col2.write(list(df_conv.columns))
    st.stop()

# --- BUSCA DE COORDENADAS ---
@st.cache_resource
def obter_coordenadas(municipios_lista):
    geolocator = Nominatim(user_agent="mapa_calor_final_v17")
    coordenadas = {}
    for municipio in municipios_lista:
        if pd.isna(municipio) or str(municipio).strip() == "" or str(municipio).lower() == 'nan':
            continue
        muni_nome = str(municipio).strip()
        try:
            location = geolocator.geocode(f"{muni_nome}, Amapá, Brasil")
            if location:
                coordenadas[muni_nome.lower()] = (location.latitude, location.longitude)
            time.sleep(1)
        except:
            pass
    return coordenadas

# Força a conversão para string e limpeza de espaços garantindo o tratamento coluna por coluna
df_ref[col_muni_ref] = df_ref[col_muni_ref].astype(str).str.strip()
df_conv[col_muni_conv] = df_conv[col_muni_conv].astype(str).str.strip()
df_conv[col_aten_conv] = df_conv[col_aten_conv].astype(str).str.strip()
df_conv[col_apon_conv] = df_conv[col_apon_conv].astype(str).str.strip()
df_ref[col_clie_ref] = df_ref[col_clie_ref].astype(str).str.strip()

# Garante que Macapá e as outras bases de rotas estejam no mapa mesmo se não listadas explicitamente
municipios_base = ['macapá', 'calçoene', 'oiapoque', 'tartarugalzinho', 'pracuúba', 'amapá', 'porto grande', 'pedra branca do amapari', 'serra do navio', 'santana', 'mazagão', 'cutias']

todos_municipios = set(df_ref[col_muni_ref].str.lower().unique()).union(
    set(df_conv[col_muni_conv].str.lower().unique())
).union(set(municipios_base))
todos_municipios.discard('nan')

coords_dict = obter_coordenadas(list(todos_municipios))

# --- BARRA LATERAL: FILTROS ---
st.sidebar.header("Filtros de Visão")

municipios_disponiveis = sorted(list(df_ref[col_muni_ref].str.lower().unique()))
municipio_selecionado = st.sidebar.multiselect("Selecione o Município:", options=municipios_disponiveis, default=municipios_disponiveis)

atendentes_disponiveis = sorted([a for a in df_conv[col_aten_conv].unique() if a.lower() != 'nan'])
atendente_selecionado = st.sidebar.multiselect("Selecione o Atendente:", options=atendentes_disponiveis, default=atendentes_disponiveis)

apontadores_disponiveis = sorted([p for p in df_conv[col_apon_conv].unique() if p.lower() != 'nan'])
apontador_selecionado = st.sidebar.multiselect("Selecione o parceiro:", options=apontadores_disponiveis, default=apontadores_disponiveis)

# --- FILTRAGEM DOS DADOS ---
df_conv_filtrado = df_conv[
    (df_conv[col_muni_conv].str.lower().isin(municipio_selecionado)) &
    (df_conv[col_aten_conv].isin(atendente_selecionado)) &
    (df_conv[col_apon_conv].isin(apontador_selecionado))
]

df_ref_filtrado = df_ref[df_ref[col_muni_ref].str.lower().isin(municipio_selecionado)]

# --- PREPARAÇÃO DOS DADOS DO MAPA ---
dados_calor_vermelho = [] 
dados_calor_azul = []     

for _, row in df_ref_filtrado.iterrows():
    muni = str(row[col_muni_ref]).strip().lower()
    if muni in coords_dict:
        lat, lon = coords_dict[muni]
        dados_calor_vermelho.append([lat, lon, 1])

for _, row in df_conv_filtrado.iterrows():
    muni = str(row[col_muni_conv]).strip().lower()
    if muni in coords_dict:
        lat, lon = coords_dict[muni]
        dados_calor_azul.append([lat, lon, 1])

# --- CRIAÇÃO DO MAPA INTERATIVO COM CAMADAS ---
mapa = folium.Map(location=[1.41, -51.77], zoom_start=7, tiles="OpenStreetMap")

if dados_calor_vermelho:
    camada_ref = folium.FeatureGroup(name='Mancha Vermelha (Referência)')
    HeatMap(dados_calor_vermelho, radius=25, blur=15, gradient={0.4: 'yellow', 0.8: 'orange', 1.0: 'red'}).add_to(camada_ref)
    camada_ref.add_to(mapa)

if dados_calor_azul:
    camada_conv = folium.FeatureGroup(name='Mancha Azul (Convertidos)')
    HeatMap(dados_calor_azul, radius=20, blur=15, gradient={0.4: 'lightblue', 0.8: 'blue', 1.0: 'darkblue'}).add_to(camada_conv)
    camada_conv.add_to(mapa)

# --- INCLUSÃO DAS 4 ROTAS SIMULTÂNEAS DE ATENDIMENTO ---
camada_rotas = folium.FeatureGroup(name='📍 Linhas das 4 Rotas Logísticas (Atendentes)')

def tracar_linha_rota(lista_cidades, cor_linha, nome_rota):
    pontos_linha = []
    for cidade in lista_cidades:
        cidade_limpa = cidade.strip().lower()
        if cidade_limpa in coords_dict:
            pontos_linha.append(coords_dict[cidade_limpa])
            # Coloca um pino em cada parada da rota
            folium.Marker(
                location=coords_dict[cidade_limpa],
                popup=f"<b>{cidade}</b><br>{nome_rota}",
                icon=folium.Icon(color=cor_linha, icon='info-sign')
            ).add_to(camada_rotas)
            
    if len(pontos_linha) > 1:
        folium.PolyLine(pontos_linha, color=cor_linha, weight=5, opacity=0.85, tooltip=nome_rota).add_to(camada_rotas)

# Traçando os itinerários logísticos conectando os clientes convertidos por região
tracar_linha_rota(['Macapá', 'Calçoene', 'Oiapoque'], 'red', 'Atendente 1 - Rota Norte Extremo (560 km)')
tracar_linha_rota(['Macapá', 'Tartarugalzinho', 'Pracuúba', 'Amapá'], 'orange', 'Atendente 2 - Rota Norte Central (305 km)')
tracar_linha_rota(['Macapá', 'Porto Grande', 'Pedra Branca do Amapari', 'Serra do Navio'], 'purple', 'Atendente 3 - Rota Centro-Oeste (210 km)')
tracar_linha_rota(['Macapá', 'Santana', 'Mazagão', 'Cutias'], 'green', 'Atendente 4 - Rota Sul Metropolitano (160 km)')

camada_rotas.add_to(mapa)

# Ativa o alternador de visualização no canto do mapa
folium.LayerControl().add_to(mapa)
st_folium(mapa, width=1000, height=600)

# Painel de Indicadores Logísticos e Quantitativos
col1, col2 = st.columns(2)
col1.metric("Clientes na Referência (Filtrados)", len(df_ref_filtrado))
col2.metric("Clientes Convertidos (Filtrados)", len(df_conv_filtrado))

# Quadro Resumo de Quilometragem das Equipes
st.info("""
### 🚚 Painel de Controle de Deslocamento das Equipes (Simultâneo)
* **Atendente 1 (Linha Vermelha):** Rota Norte Extremo (Macapá ➔ Calçoene ➔ Oiapoque) — **560 km estimados**
* **Atendente 2 (Linha Laranja):** Rota Norte Central (Macapá ➔ Tartarugalzinho ➔ Pracuúba ➔ Amapá) — **305 km estimados**
* **Atendente 3 (Linha Roxa):** Rota Centro-Oeste (Macapá ➔ Porto Grande ➔ Pedra Branca do Amapari ➔ Serra do Navio) — **210 km estimados**
* **Atendente 4 (Linha Verde):** Rota Sul Metropolitano (Macapá ➔ Santana ➔ Mazagão ➔ Cutias) — **160 km estimados**
""")

# --- LISTA ANALÍTICA (SEUS_DADOS) ---
st.write("---")
st.write("### 📋 Lista Analítica de Clientes (Planilha Referência)")

df_analitico_ref = df_ref_filtrado.copy()

if not df_analitico_ref.empty:
    def para_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Clientes_Referencia')
        dados_processados = output.getvalue()
        return dados_processados

    excel_data = para_excel(df_analitico_ref)
    
