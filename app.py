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
            f.write("ExemploStreamer\n")
    with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]


def adicionar_streamer(novo):
    with open(STREAMERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{novo.strip()}\n")


PRAGMATIC_KEYWORDS = carregar_keywords()
STREAMERS_INTERESSE = carregar_streamers()


def buscar_lives_twitch():
    url = BASE_URL_TWITCH + 'streams?game_id=509577&first=100&language=pt'
    response = requests.get(url, headers=HEADERS_TWITCH)
    return response.json().get('data', [])


def filtrar_lives_twitch(lives):
    pragmatic_lives = []
    for live in lives:
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
        response = requests.get(YOUTUBE_SEARCH_URL, params=params)
        data = response.json()
        video_ids = [item['id']['videoId'] for item in data.get('items', [])]
        if not video_ids:
            continue

        detail_params = {
            'part': 'snippet,liveStreamingDetails,statistics',
            'id': ','.join(video_ids),
            'key': YOUTUBE_API_KEY
        }
        detail_response = requests.get('https://www.googleapis.com/youtube/v3/videos', params=detail_params)
        detail_data = detail_response.json()

        for item in detail_data.get('items', []):
            snippet = item['snippet']
            if snippet['channelTitle'].lower() not in [s.lower() for s in STREAMERS_INTERESSE]:
                continue
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


def buscar_videos_youtube_vods():
    videos = []
    data_limite = (datetime.utcnow() - timedelta(days=30)).isoformat("T") + "Z"
    for keyword in PRAGMATIC_KEYWORDS:
        params = {
            'part': 'snippet',
            'q': keyword,
            'type': 'video',
            'publishedAfter': data_limite,
            'regionCode': 'BR',
            'relevanceLanguage': 'pt',
            'key': YOUTUBE_API_KEY,
            'maxResults': 10
        }
        response = requests.get(YOUTUBE_SEARCH_URL, params=params)
        data = response.json()
        for item in data.get('items', []):
            snippet = item['snippet']
            if snippet['channelTitle'].lower() not in [s.lower() for s in STREAMERS_INTERESSE]:
                continue
            videos.append({
                'streamer': snippet['channelTitle'],
                'title': snippet['title'],
                'published_at': snippet['publishedAt'].replace("T", " ").replace("Z", ""),
                'game': keyword,
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'thumbnail': snippet['thumbnails']['medium']['url']
            })
    return videos

# Adiciona ao painel lateral do Streamlit
st.sidebar.subheader("➕ Adicionar nova palavra-chave")
nova_keyword = st.sidebar.text_input("Nova keyword")
if st.sidebar.button("Adicionar keyword"):
    adicionar_keyword(nova_keyword)
    st.sidebar.success(f"'{nova_keyword}' adicionada. Recarregue a página para atualizar.")

st.sidebar.subheader("👤 Adicionar novo streamer")
novo_streamer = st.sidebar.text_input("Novo streamer")
if st.sidebar.button("Adicionar streamer"):
    adicionar_streamer(novo_streamer)
    st.sidebar.success(f"'{novo_streamer}' adicionado. Recarregue a página para atualizar.")

# Seção de busca manual para vídeos recentes
st.subheader("📅 Buscar vídeos do YouTube postados nos últimos 30 dias")
if st.button("📥 Buscar vídeos recentes"):
    vods = buscar_videos_youtube_vods()
    if vods:
        for v in vods:
            st.markdown(f"""
**{v['streamer']}** postou:

🎮 *{v['game']}*  
📅 Publicado: {v['published_at']}  
🔗 [Assistir agora]({v['url']})  
![]({v['thumbnail']})
---
""")
    else:
        st.info("Nenhum vídeo recente encontrado com as palavras-chave.")
