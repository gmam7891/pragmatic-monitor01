from datetime import datetime
import requests
import sqlite3
import streamlit as st
import pandas as pd
import pytz
import schedule
import time
import threading
import os

# ------------------------------
# CONFIGURAÇÕES INICIAIS
# ------------------------------
CLIENT_ID = '9qkw87yuzfolbyk3lva3n76qhucrxe'
ACCESS_TOKEN = '6qgrr9jy215szvksczidb8hslztux8'
YOUTUBE_API_KEY = 'AIzaSyB3r4wPR7B8y2JOl2JSpM-CbBUwvhqZm84'

HEADERS_TWITCH = {
    'Client-ID': CLIENT_ID,
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
BASE_URL_TWITCH = 'https://api.twitch.tv/helix/'
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'

# ------------------------------
# KEYWORDS DINÂMICAS
# ------------------------------
KEYWORDS_FILE = "keywords.txt"

def carregar_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
            f.write("Sweet Bonanza\nGates of Olympus\nSugar Rush\nStarlight Princess\nBig Bass Bonanza\n")
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

def adicionar_keyword(nova):
    with open(KEYWORDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{nova.strip()}\n")

PRAGMATIC_KEYWORDS = carregar_keywords()

# ------------------------------
# TWITCH
# ------------------------------
def buscar_lives_twitch():
    url = BASE_URL_TWITCH + 'streams?game_id=509577&first=100&language=pt'
    response = requests.get(url, headers=HEADERS_TWITCH)
    return response.json().get('data', [])

def filtrar_lives_twitch(lives):
    pragmatic_lives = []
    for live in lives:
        title = live['title'].lower()
        for keyword in PRAGMATIC_KEYWORDS:
            if keyword.lower() in title:
                started_at = datetime.strptime(live['started_at'], "%Y-%m-%dT%H:%M:%SZ")
                started_at = started_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("America/Sao_Paulo"))
                pragmatic_lives.append({
                    'plataforma': 'Twitch',
                    'streamer': live['user_name'],
                    'title': live['title'],
                    'viewer_count': live['viewer_count'],
                    'started_at': started_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'game': keyword,
                    'url': f"https://twitch.tv/{live['user_name']}",
                    'thumbnail': live['thumbnail_url'].replace('{width}', '320').replace('{height}', '180')
                })
    return pragmatic_lives

# ------------------------------
# YOUTUBE
# ------------------------------
def buscar_videos_youtube():
    lives = []
    for keyword in PRAGMATIC_KEYWORDS:
        params = {
            'part': 'snippet',
            'q': keyword,
            'type': 'video',
            'eventType': 'live',
            'regionCode': 'BR',
            'relevanceLanguage': 'pt',
            'key': YOUTUBE_API_KEY,
            'maxResults': 10
        }
        search_response = requests.get(YOUTUBE_SEARCH_URL, params=params)
        data = search_response.json()

        video_ids = [item['id']['videoId'] for item in data.get('items', [])]
        if not video_ids:
            continue

        video_details_url = 'https://www.googleapis.com/youtube/v3/videos'
        detail_params = {
            'part': 'snippet,liveStreamingDetails,statistics',
            'id': ','.join(video_ids),
            'key': YOUTUBE_API_KEY
        }
        detail_response = requests.get(video_details_url, params=detail_params)
        detail_data = detail_response.json()

        for item in detail_data.get('items', []):
            snippet = item['snippet']
            stats = item.get('statistics', {})
            live_details = item.get('liveStreamingDetails', {})

            lives.append({
                'plataforma': 'YouTube',
                'streamer': snippet['channelTitle'],
                'title': snippet['title'],
                'viewer_count': int(stats.get('concurrentViewers', 0)) if 'concurrentViewers' in stats else 0,
                'started_at': live_details.get('actualStartTime', snippet['publishedAt']).replace("T", " ").replace("Z", ""),
                'game': keyword,
                'url': f"https://www.youtube.com/watch?v={item['id']}",
                'thumbnail': snippet['thumbnails']['medium']['url']
            })
    return lives

# ------------------------------
# BANCO DE DADOS
# ------------------------------
def salvar_no_banco(dados):
    conn = sqlite3.connect('pragmatic_lives.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lives (
            plataforma TEXT,
            streamer TEXT,
            title TEXT,
            viewer_count INTEGER,
            started_at TEXT,
            game TEXT,
            url TEXT,
            thumbnail TEXT
        )
    """)
    for d in dados:
        cursor.execute('INSERT INTO lives VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (
            d['plataforma'], d['streamer'], d['title'], d['viewer_count'],
            d['started_at'], d['game'], d['url'], d['thumbnail']
        ))
    conn.commit()
    conn.close()

def carregar_dados():
    conn = sqlite3.connect('pragmatic_lives.db')
    try:
        df = pd.read_sql_query("SELECT * FROM lives", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def exportar_csv(df):
    df.to_csv("dados_pragmatic.csv", index=False)
    st.success("Arquivo CSV exportado com sucesso!")

# ------------------------------
# ROTINA AUTOMÁTICA
# ------------------------------
def rotina_agendada():
    global PRAGMATIC_KEYWORDS
    PRAGMATIC_KEYWORDS = carregar_keywords()
    twitch = buscar_lives_twitch()
    twitch_pragmatic = filtrar_lives_twitch(twitch)
    youtube_pragmatic = buscar_videos_youtube()
    todos = twitch_pragmatic + youtube_pragmatic
    salvar_no_banco(todos)

def iniciar_agendamento():
    schedule.every(2).minutes.do(rotina_agendada)
    while True:
        schedule.run_pending()
        time.sleep(1)

agendador = threading.Thread(target=iniciar_agendamento, daemon=True)
agendador.start()

# ------------------------------
# STREAMLIT DASHBOARD
# ------------------------------
st.set_page_config(page_title="Monitor Pragmatic - Twitch & YouTube", layout="wide")
st.title("🎰 Monitor de Jogos Pragmatic Play - Twitch & YouTube (BR)")

st.sidebar.subheader("➕ Adicionar nova palavra-chave")
nova_keyword = st.sidebar.text_input("Nova keyword")
if st.sidebar.button("Adicionar keyword"):
    adicionar_keyword(nova_keyword)
    st.sidebar.success(f"'{nova_keyword}' adicionada. Recarregue a página para atualizar.")

col1, col2 = st.columns(2)
if col1.button("🔍 Buscar agora"):
    rotina_agendada()
    st.success("Nova busca realizada.")

df = carregar_dados()

st.subheader("📊 Tabela de Transmissões Registradas")
if not df.empty:
    st.dataframe(df.sort_values(by="started_at", ascending=False), use_container_width=True)
else:
    st.info("Nenhum dado carregado ainda.")

if not df.empty and st.button("📁 Exportar CSV"):
    exportar_csv(df)

if not df.empty:
    st.subheader("📈 Estatísticas")
    col1, col2, col3 = st.columns(3)
    col1.metric("Streamers únicos", df["streamer"].nunique())
    col2.metric("Total de lives", len(df))
    col3.metric("Jogos monitorados", df["game"].nunique())

    if "plataforma" in df.columns:
        st.subheader("📊 Por Plataforma")
        st.bar_chart(df['plataforma'].value_counts())

    if "game" in df.columns:
        st.subheader("🎮 Distribuição por Jogo")
        st.bar_chart(df['game'].value_counts())

    st.subheader("🎬 Visualização com Thumbnails")
    for i, row in df.sort_values(by="started_at", ascending=False).head(10).iterrows():
        st.markdown(f"""
**{row['streamer']}** na **{row['plataforma']}** - *{row['game']}*

🔗 [Assistir agora]({row['url']})  
👥 **{row['viewer_count']}** espectadores  
🕒 Início: {row['started_at']}  
![]({row['thumbnail']})
---
""")
