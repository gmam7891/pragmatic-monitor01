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
ACCESS_TOKEN = 'moila7dw5ejlk3eja6ne08arw0oexs'
YOUTUBE_API_KEY = 'AIzaSyB3r4wPR7B8y2JOl2JSpM-CbBUwvhqZm84'

HEADERS_TWITCH = {
    'Client-ID': CLIENT_ID,
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
BASE_URL_TWITCH = 'https://api.twitch.tv/helix/'
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
YOUTUBE_VIDEO_URL = 'https://www.googleapis.com/youtube/v3/videos'

STREAMERS_FILE = "streamers.txt"
JOGOS_FILE = "jogos_pragmatic.txt"
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

def carregar_jogos_pragmatic():
    if not os.path.exists(JOGOS_FILE):
        with open(JOGOS_FILE, "w", encoding="utf-8") as f:
            f.write("Sweet Bonanza\nGates of Olympus\nSugar Rush\n")
    with open(JOGOS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip().lower() for linha in f if linha.strip()]

JOGOS_PRAGMATIC = carregar_jogos_pragmatic()

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
        title_lower = live['title'].lower()
        if not any(jogo in title_lower or jogo in (game_name or '').lower() for jogo in JOGOS_PRAGMATIC):
            continue
        streamer_name = live['user_name'].lower()
        if streamer_name not in [s.lower() for s in STREAMERS_INTERESSE]:
            continue
        started_at = datetime.strptime(live['started_at'], "%Y-%m-%dT%H:%M:%SZ")
        started_at = started_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("America/Sao_Paulo"))
        tempo_online = datetime.now(pytz.timezone("America/Sao_Paulo")) - started_at
        pragmatic_lives.append({
            'plataforma': 'Twitch (ao vivo)',
            'streamer': live['user_name'],
            'title': live['title'],
            'viewer_count': live['viewer_count'],
            'started_at': started_at.strftime('%Y-%m-%d %H:%M:%S'),
            'tempo_online': str(tempo_online).split('.')[0],
            'game': game_name,
            'url': f"https://twitch.tv/{live['user_name']}"
        })
    return pragmatic_lives

# ------------------------------
# STREAMLIT - EDIÇÃO JOGOS
# ------------------------------
st.sidebar.subheader("🎰 Jogos da Pragmatic Play")
jogos_atuais = carregar_jogos_pragmatic()
st.sidebar.write("Jogos monitorados:")
st.sidebar.write("\n".join(jogos_atuais))
novo_jogo = st.sidebar.text_input("Adicionar novo jogo")
if st.sidebar.button("Adicionar jogo"):
    if novo_jogo.strip():
        with open(JOGOS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{novo_jogo.strip()}\n")
        st.sidebar.success(f"'{novo_jogo}' adicionado. Recarregue a página para atualizar.")
