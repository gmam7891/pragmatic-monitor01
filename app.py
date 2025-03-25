from datetime import datetime, timedelta
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
CLIENT_ID = 'gp762nuuoqcoxypju8c569th9wz7q5'
ACCESS_TOKEN = '5gtwi4j62m9w4dmj3k1oe72947e5axpozxyhkgnvrv3vw4cf5e'
YOUTUBE_API_KEY = 'AIzaSyB3r4wPR7B8y2JOl2JSpM-CbBUwvhqZm84'

HEADERS_TWITCH = {
    'Client-ID': CLIENT_ID,
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
BASE_URL_TWITCH = 'https://api.twitch.tv/helix/'
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'

STREAMERS_FILE = "streamers.txt"
GAME_NAME_TARGET = 'Virtual Casino'

# ------------------------------
# UTILITÁRIOS
# ------------------------------
def carregar_streamers():
    if not os.path.exists(STREAMERS_FILE):
        with open(STREAMERS_FILE, "w", encoding="utf-8") as f:
            f.write("jukes\n")
    with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

def adicionar_streamer(novo):
    with open(STREAMERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{novo.strip()}\n")

STREAMERS_INTERESSE = carregar_streamers()

# ------------------------------
# TWITCH
# ------------------------------
def buscar_lives_twitch():
    url = BASE_URL_TWITCH + 'streams?first=100&language=pt'
    response = requests.get(url, headers=HEADERS_TWITCH)
    return response.json().get('data', [])

def buscar_game_name(game_id):
    response = requests.get(BASE_URL_TWITCH + f'games?id={game_id}', headers=HEADERS_TWITCH)
    data = response.json().get('data', [])
    if data:
        return data[0]['name']
    return None

def filtrar_lives_twitch(lives):
    pragmatic_lives = []
    for live in lives:
        game_id = live.get('game_id')
        if not game_id:
            continue
        game_name = buscar_game_name(game_id)
        if game_name and game_name.lower() != GAME_NAME_TARGET.lower():
            continue
        streamer_name = live['user_name'].lower()
        if streamer_name not in [s.lower() for s in STREAMERS_INTERESSE]:
            continue
        started_at = datetime.strptime(live['started_at'], "%Y-%m-%dT%H:%M:%SZ")
        started_at = started_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("America/Sao_Paulo"))
        pragmatic_lives.append({
            'plataforma': 'Twitch (ao vivo)',
            'streamer': live['user_name'],
            'title': live['title'],
            'viewer_count': live['viewer_count'],
            'started_at': started_at.strftime('%Y-%m-%d %H:%M:%S'),
            'game': game_name,
            'url': f"https://twitch.tv/{live['user_name']}",
            'thumbnail': live['thumbnail_url'].replace('{width}', '320').replace('{height}', '180')
        })
    return pragmatic_lives

def buscar_vods_twitch_por_periodo(data_inicio, data_fim):
    vods = []
    for streamer in STREAMERS_INTERESSE:
        user_response = requests.get(BASE_URL_TWITCH + f'users?login={streamer}', headers=HEADERS_TWITCH)
        user_data = user_response.json().get('data', [])
        if not user_data:
            continue
        user_id = user_data[0]['id']
        params = {
            'user_id': user_id,
            'first': 100,
            'type': 'archive'
        }
        vod_response = requests.get(BASE_URL_TWITCH + 'videos', headers=HEADERS_TWITCH, params=params)
        vod_data = vod_response.json().get('data', [])
        for video in vod_data:
            created_at = datetime.strptime(video['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if not (data_inicio <= created_at <= data_fim):
                continue
            vods.append({
                'plataforma': 'Twitch (VOD)',
                'streamer': video['user_name'],
                'title': video['title'],
                'viewer_count': video.get('view_count', 0),
                'started_at': created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'game': video.get('game_name', 'Desconhecido'),
                'url': video['url'],
                'thumbnail': video['thumbnail_url']
            })
    return vods

# ------------------------------
# YOUTUBE
# ------------------------------
def buscar_youtube_videos_por_periodo(data_inicio, data_fim):
    videos = []
    published_after = data_inicio.isoformat("T") + "Z"
    published_before = data_fim.isoformat("T") + "Z"
    for streamer in STREAMERS_INTERESSE:
        params = {
            'part': 'snippet',
            'channelType': 'any',
            'q': streamer,
            'type': 'video',
            'publishedAfter': published_after,
            'publishedBefore': published_before,
            'regionCode': 'BR',
            'relevanceLanguage': 'pt',
            'key': YOUTUBE_API_KEY,
            'maxResults': 10
        }
        response = requests.get(YOUTUBE_SEARCH_URL, params=params)
        data = response.json()
        for item in data.get('items', []):
            snippet = item['snippet']
            videos.append({
                'plataforma': 'YouTube',
                'streamer': snippet['channelTitle'],
                'title': snippet['title'],
                'viewer_count': 0,
                'started_at': snippet['publishedAt'].replace("T", " ").replace("Z", ""),
                'game': 'Cassino (palavra-chave)',
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'thumbnail': snippet['thumbnails']['medium']['url']
            })
    return videos

# ------------------------------
# STREAMLIT DASHBOARD
# ------------------------------
st.set_page_config(page_title="Monitor Cassino - Twitch & YouTube", layout="wide")
st.title("🎰 Monitor de Conteúdo de Cassino - Twitch & YouTube (BR)")

st.sidebar.subheader("➕ Adicionar novo streamer")
nome_novo_streamer = st.sidebar.text_input("Nome do streamer")
if st.sidebar.button("Adicionar streamer"):
    adicionar_streamer(nome_novo_streamer)
    st.sidebar.success(f"'{nome_novo_streamer}' adicionado. Recarregue a página para atualizar.")

st.subheader("📅 Escolha o período para busca de VODs")
data_inicio = st.date_input("Data de início", value=datetime.today() - timedelta(days=30))
data_fim = st.date_input("Data de fim", value=datetime.today())

if st.button("📥 Buscar conteúdo Cassino"):
    dt_inicio = datetime.combine(data_inicio, datetime.min.time())
    dt_fim = datetime.combine(data_fim, datetime.max.time())

    twitch_lives = buscar_lives_twitch()
    twitch_cassino = filtrar_lives_twitch(twitch_lives)
    twitch_vods = buscar_vods_twitch_por_periodo(dt_inicio, dt_fim)
    youtube_videos = buscar_youtube_videos_por_periodo(dt_inicio, dt_fim)
    todos = twitch_cassino + twitch_vods + youtube_videos

    if todos:
        st.subheader(f"🎞️ Conteúdo de Cassino de {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")
        df = pd.DataFrame(todos)
        st.dataframe(df.sort_values(by="started_at", ascending=False), use_container_width=True)

        if st.download_button("📁 Exportar para CSV", data=df.to_csv(index=False).encode('utf-8'), file_name="conteudo_cassino.csv", mime="text/csv"):
            st.success("Arquivo CSV exportado com sucesso!")
    else:
        st.info("Nenhum conteúdo encontrado para os streamers selecionados no período definido.")
