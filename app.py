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
CLIENT_ID = '9qkw87yuzfolbyk3lva3n76qhucrxe'
ACCESS_TOKEN = '6qgrr9jy215szvksczidb8hslztux8'
YOUTUBE_API_KEY = 'AIzaSyB3r4wPR7B8y2JOl2JSpM-CbBUwvhqZm84'

HEADERS_TWITCH = {
    'Client-ID': CLIENT_ID,
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
BASE_URL_TWITCH = 'https://api.twitch.tv/helix/'
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'

KEYWORDS_FILE = "keywords.txt"
STREAMERS_FILE = "streamers.txt"

# ------------------------------
# UTILITÁRIOS
# ------------------------------
def carregar_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
            f.write("Sweet Bonanza\nGates of Olympus\nSugar Rush\nStarlight Princess\nBig Bass Bonanza\n")
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

def adicionar_keyword(nova):
    with open(KEYWORDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{nova.strip()}\n")

def carregar_streamers():
    if not os.path.exists(STREAMERS_FILE):
        with open(STREAMERS_FILE, "w", encoding="utf-8") as f:
            f.write("jukes\n")
    with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

def adicionar_streamer(novo):
    with open(STREAMERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{novo.strip()}\n")

PRAGMATIC_KEYWORDS = carregar_keywords()
STREAMERS_INTERESSE = carregar_streamers()

# ------------------------------
# TWITCH
# ------------------------------
def buscar_lives_twitch():
    url = BASE_URL_TWITCH + 'streams?first=100&language=pt'
    response = requests.get(url, headers=HEADERS_TWITCH)
    return response.json().get('data', [])

def filtrar_lives_twitch(lives):
    pragmatic_lives = []
    for live in lives:
        if live.get('game_id') != '509577':
            continue
        title = live['title'].lower()
        streamer_name = live['user_name'].lower()
        if streamer_name not in [s.lower() for s in STREAMERS_INTERESSE]:
            continue
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

def buscar_vods_twitch():
    vods = []
    for streamer in STREAMERS_INTERESSE:
        user_response = requests.get(BASE_URL_TWITCH + f'users?login={streamer}', headers=HEADERS_TWITCH)
        user_data = user_response.json().get('data', [])
        if not user_data:
            continue
        user_id = user_data[0]['id']
        params = {
            'user_id': user_id,
            'first': 20,
            'type': 'archive'
        }
        vod_response = requests.get(BASE_URL_TWITCH + 'videos', headers=HEADERS_TWITCH, params=params)
        vod_data = vod_response.json().get('data', [])
        for video in vod_data:
            created_at = datetime.strptime(video['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if created_at < datetime.utcnow() - timedelta(days=30):
                continue
            for keyword in PRAGMATIC_KEYWORDS:
                if keyword.lower() in video['title'].lower():
                    vods.append({
                        'plataforma': 'Twitch VOD',
                        'streamer': video['user_name'],
                        'title': video['title'],
                        'viewer_count': video.get('view_count', 0),
                        'started_at': created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'game': keyword,
                        'url': video['url'],
                        'thumbnail': video['thumbnail_url']
                    })
    return vods

def exportar_vods_csv(vods):
    df = pd.DataFrame(vods)
    df.to_csv("vods_twitch.csv", index=False)
    st.success("Arquivo CSV de VODs exportado com sucesso!")

# ------------------------------
# STREAMLIT DASHBOARD
# ------------------------------
st.set_page_config(page_title="Monitor Pragmatic - Twitch & YouTube", layout="wide")
st.title("🎰 Monitor de Jogos Pragmatic Play - Twitch & YouTube (BR)")

if st.button("📥 Buscar VODs Twitch últimos 30 dias"):
    vods = buscar_vods_twitch()
    if vods:
        st.subheader("🎞️ VODs recentes da Twitch (últimos 30 dias)")
        for v in vods:
            st.markdown(f"""
**{v['streamer']}** postou:

🎮 *{v['game']}*  
👁️ {v['viewer_count']} views  
📅 Publicado: {v['started_at']}  
🔗 [Assistir agora]({v['url']})  
![]({v['thumbnail']})
---
""")

        if st.button("📁 Exportar VODs para CSV"):
            exportar_vods_csv(vods)
    else:
        st.info("Nenhum VOD recente encontrado para os streamers selecionados.")
