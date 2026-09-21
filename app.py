import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from io import BytesIO

# Configuração da página do Streamlit
st.set_page_config(page_title="Mapa de Calor de Clientes", layout="wide")
st.title("🗺️ Mapa de Calor - Referência vs. Colmeias (6 Rotas Simultâneas)")

# COORDENADAS FIXAS E DEFINITIVAS DOS MUNICÍPIOS DO AMAPÁ (Evita bloqueios de internet)
@st.cache_data
def obter_coordenadas_fixas():
    return {
        'macapá': (0.0389, -51.0664),
        'santana': (-0.0164, -51.1817),
        'tartarugalzinho': (1.5044, -50.9103),
        'oiapoque': (3.8431, -51.8356),
        'calçoene': (2.4975, -50.9511),
        'pracuúba': (1.7431, -50.7914),
        'amapá': (2.0539, -50.7967),
        'porto grande': (0.7128, -51.4131),
        'pedra branca do amapari': (0.7761, -51.9486),
        'serra do navio': (0.8961, -52.0014),
        'mazagão': (-0.1153, -51.2894),
        'cutias': (0.8686, -50.8019),
        'itaubal': (0.6558, -50.6844),
        'vitória do jari': (-1.1128, -52.4164),
        'vítoria do jari': (-1.1128, -52.4164),
        'laranjal do jari': (-0.8425, -52.5161),
        'ferreira gomes': (0.8578, -51.1803)
    }

# Função para carregar e limpar os dados das planilhas
@st.cache_data
def carregar_dados():
    df_ref = pd.read_excel("seus_dados.xlsx", engine="openpyxl")
    df_colmeias = pd.read_excel("convertidos.xlsx", engine="openpyxl")
    
    # Função para limpar colunas duplicadas
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
    df_colmeias = renomear_duplicados(df_colmeias)
    
    return df_ref, df_colmeias

try:
    df_ref, df_colmeias = carregar_dados()
except FileNotFoundError:
    st.error("Erro: Não encontrei os arquivos Excel. Garanta que os nomes sejam exatamente 'seus_dados.xlsx' e 'convertidos.xlsx'.")
    st.stop()

# --- MAPEAMENTO DE COLUNAS ---
def encontrar_coluna_real(lista_colunas, alvo):
    for col in lista_colunas:
        if col.lower().strip() == alvo or col.lower().strip().startswith(f"{alvo}_"):
            return col
    return None

col_muni_ref = encontrar_coluna_real(df_ref.columns, 'municipio')
col_clie_ref = encontrar_coluna_real(df_ref.columns, 'cliente')
col_aten_ref = encontrar_coluna_real(df_ref.columns, 'atendente')
col_apon_ref = encontrar_coluna_real(df_ref.columns, 'apontador')

col_muni_colmeias = encontrar_coluna_real(df_colmeias.columns, 'municipio')
col_aten_colmeias = encontrar_coluna_real(df_colmeias.columns, 'atendente')
col_apon_colmeias = encontrar_coluna_real(df_colmeias.columns, 'apontador')

# Limpeza rigorosa de textos (remove espaços extras no início e fim de tudo)
for df, col in [(df_ref, col_muni_ref), (df_ref, col_clie_ref), (df_ref, col_aten_ref), (df_ref, col_apon_ref),
                (df_colmeias, col_muni_colmeias), (df_colmeias, col_aten_colmeias), (df_colmeias, col_apon_colmeias)]:
    if col:
        df[col] = df[col].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)

coords_dict = obter_coordenadas_fixas()

# --- BARRA LATERAL: FILTROS UNIFICADOS ---
st.sidebar.header("Filtros de Visão")

# Municípios
muni_ref_set = set(df_ref[col_muni_ref].str.lower().unique()) if col_muni_ref else set()
muni_colmeias_set = set(df_colmeias[col_muni_colmeias].str.lower().unique()) if col_muni_colmeias else set()
municipios_disponiveis = sorted(list(muni_ref_set.union(muni_colmeias_set).intersection(set(coords_dict.keys()))))
municipio_selecionado = st.sidebar.multiselect("Selecione o Município:", options=municipios_disponiveis, default=municipios_disponiveis)

# Atendentes
aten_ref_set = set(df_ref[col_aten_ref].unique()) if col_aten_ref else set()
aten_colmeias_set = set(df_colmeias[col_aten_colmeias].unique()) if col_aten_colmeias else set()
atendentes_disponiveis = sorted([a for a in aten_ref_set.union(aten_colmeias_set) if str(a).lower() != 'nan' and str(a) != ''])
atendente_selecionado = st.sidebar.multiselect("Selecione o Atendente:", options=atendentes_disponiveis, default=atendentes_disponiveis)

# Apontadores
apon_ref_set = set(df_ref[col_apon_ref].unique()) if col_apon_ref else set()
apon_colmeias_set = set(df_colmeias[col_apon_colmeias].unique()) if col_apon_colmeias else set()
apontadores_disponiveis = sorted([p for p in apon_ref_set.union(apon_colmeias_set) if str(p).lower() != 'nan' and str(p) != ''])
apontador_selecionado = st.sidebar.multiselect("Selecione o parceiro:", options=apontadores_disponiveis, default=apontadores_disponiveis)

# --- FILTRAGEM DOS DADOS ---
df_ref_filtrado = df_ref[
    (df_ref[col_muni_ref].str.lower().isin(municipio_selecionado)) &
    (df_ref[col_aten_ref].isin(atendente_selecionado) if col_aten_ref else True) &
    (df_ref[col_apon_ref].isin(apontador_selecionado) if col_apon_ref else True)
]

df_colmeias_filtrado = df_colmeias[
    (df_colmeias[col_muni_colmeias].str.lower().isin(municipio_selecionado)) &
    (df_colmeias[col_aten_colmeias].isin(atendente_selecionado)) &
    (df_colmeias[col_apon_colmeias].isin(apontador_selecionado))
]

# --- PREPARAÇÃO DOS DADOS DO MAPA ---
dados_calor_vermelho = [] 
dados_calor_azul = []     

for _, row in df_ref_filtrado.iterrows():
    muni = str(row[col_muni_ref]).strip().lower()
    if muni in coords_dict:
        lat, lon = coords_dict[muni]
        dados_calor_vermelho.append([lat, lon, 1])

for _, row in df_colmeias_filtrado.iterrows():
    muni = str(row[col_muni_colmeias]).strip().lower()
    if muni in coords_dict:
        lat, lon = coords_dict[muni]
        dados_calor_azul.append([lat, lon, 1])

# --- CRIAÇÃO DO MAPA ---
mapa = folium.Map(location=[1.41, -51.77], zoom_start=7, tiles="OpenStreetMap")

if dados_calor_vermelho:
    camada_ref = folium.FeatureGroup(name='Mancha Vermelha (Referência)')
    HeatMap(dados_calor_vermelho, radius=25, blur=15, gradient={0.4: 'yellow', 0.8: 'orange', 1.0: 'red'}).add_to(camada_ref)
    camada_ref.add_to(mapa)

if dados_calor_azul:
    camada_colmeias = folium.FeatureGroup(name='Mancha Azul (Colmeias)')
    HeatMap(dados_calor_azul, radius=20, blur=15, gradient={0.4: 'lightblue', 0.8: 'blue', 1.0: 'darkblue'}).add_to(camada_colmeias)
    camada_colmeias.add_to(mapa)

# --- INCLUSÃO DAS 6 ROTAS LOGÍSTICAS ---
camada_rotas = folium.FeatureGroup(name='📍 Linhas das 6 Rotas Logísticas (Atendentes)')

def congenital_linha_rota(lista_cidades, cor_linha, nome_rota):
    pontos_linha = []
    for cidade in lista_cidades:
        cidade_limpa = cidade.strip().lower()
        if cidade_limpa in coords_dict:
            pontos_linha.append(coords_dict[cidade_limpa])
            folium.Marker(
                location=coords_dict[cidade_limpa],
                popup=f"<b>{cidade}</b><br>{nome_rota}",
                icon=folium.Icon(color=cor_linha, icon='info-sign')
            ).add_to(camada_rotas)
            
    if len(pontos_linha) > 1:
        folium.PolyLine(pontos_linha, color=cor_linha, weight=5, opacity=0.85, tooltip=nome_rota).add_to(camada_rotas)

# Traçando as 6 rotas logísticas simultâneas
congenital_linha_rota(['Macapá', 'Calçoene', 'Oiapoque'], 'red', 'Atendente 1 - Rota Norte Extremo')
congenital_linha_rota(['Macapá', 'Tartarugalzinho', 'Pracuúba', 'Amapá'], 'orange', 'Atendente 2 - Rota Norte Central')
congenital_linha_rota(['Macapá', 'Porto Grande', 'Pedra Branca do Amapari', 'Serra do Navio'], 'purple', 'Atendente 3 - Rota Centro-Oeste')
congenital_linha_rota(['Macapá', 'Santana', 'Mazagão', 'Cutias'], 'green', 'Atendente 4 - Rota Sul Metropolitano')
congenital_linha_rota(['Macapá', 'Laranjal do Jari', 'Vitória do Jari'], 'darkblue', 'Atendente 5 - Rota Vale do Jari')
congenital_linha_rota(['Macapá', 'Itaubal', 'Ferreira Gomes'], 'pink', 'Atendente 6 - Rota Transversal Leste-Centro')

camada_rotas.add_to(mapa)
folium.LayerControl().add_to(mapa)

# --- 📥 IMPLEMENTAÇÃO: EXPORTAÇÃO DO MAPA OFFLINE ---
# Converte a visualização atual do Folium em bytes HTML na memória
mapa_html_bytes = BytesIO()
mapa.save(mapa_html_bytes, close_file=False)
mapa_html_bytes.seek(0)

# Criando a seção de download na barra lateral do Streamlit
st.sidebar.markdown("---")
st.sidebar.subheader("📱 Uso Offline no iPad")
st.sidebar.download_button(
    label="📥 Baixar Mapa Interativo (HTML)",
    data=mapa_html_bytes,
    file_name="mapa_calor_offline.html",
    mime="text/html",
    help="Clique para baixar o mapa atualizado com os filtros selecionados para usar sem internet."
)
st.sidebar.caption("💡 Dica: No iPad, abra o arquivo usando aplicativos como 'Documents' ou 'Koder' para que a interatividade funcione 100% offline.")

# Renderiza o mapa na tela do Streamlit normalmente
st_folium(mapa, width=1000, height=600)

# Painel de Indicadores
col1, col2 = st.columns(2)
col1.metric("Clientes na Referência (Filtrados)", len(df_ref_filtrado))
col2.metric("Colmeias (Filtradas)", len(df_colmeias_filtrado))

# Quadro Resumo das 6 Equipes
st.info("""
### 🚚 Painel de Controle de Deslocamento das Equipes (6 Rotas Simultâneas)
* **Atendente 1 (Linha Vermelha):** Rota Norte Extremo (Macapá ➔ Calçoene ➔ Oiapoque)
* **Atendente 2 (Linha Laranja):** Rota Norte Central (Macapá ➔ Tartarugalzinho ➔ Pracuúba ➔ Amapá)
* **Atendente 3 (Linha Roxa):** Rota Centro-Oeste (Macapá ➔ Porto Grande ➔ Pedra Branca do Amapari ➔ Serra do Navio)
* **Atendente 4 (Linha Verde):** Rota Sul Metropolitano (Macapá ➔ Santana ➔ Mazagão ➔ Cutias)
* **Atendente 5 (Linha Azul Escuro):** Rota Vale do Jari (Macapá ➔ Laranjal do Jari ➔ Vitória do Jari)
* **Atendente 6 (Linha Rosa):** Rota Transversal Leste-Centro (Macapá ➔ Itaubal ➔ Ferreira Gomes)
""")
