from datetime import datetime, timedelta
import requests
import streamlit as st
import pandas as pd
import pytz
import os
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import tempfile
import schedule
import threading

# ------------------------------
# CONFIGURAÇÕES INICIAIS
# ------------------------------
CLIENT_ID = 'gp762nuuoqcoxypju8c569th9wz7q5'
ACCESS_TOKEN = 'moila7dw5ejlk3eja6ne08arw0oexs'
HEADERS_TWITCH = {
    'Client-ID': CLIENT_ID,
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
BASE_URL_TWITCH = 'https://api.twitch.tv/helix/'
YOUTUBE_API_KEY = 'AIzaSyB3r4wPR7B8y2JOl2JSpM-CbBUwvhqZm84'
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
YOUTUBE_VIDEO_URL = 'https://www.googleapis.com/youtube/v3/videos'

STREAMERS_FILE = "streamers.txt"
JOGOS_FILE = "jogos_pragmatic.txt"
TEMPLATES_DIR = "templates/"

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


def match_template_from_frame(frame_url):
    try:
        response = requests.get(frame_url)
        img = Image.open(BytesIO(response.content)).convert('RGB')
        img_np = np.array(img)
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        for template_name in os.listdir(TEMPLATES_DIR):
            template_path = os.path.join(TEMPLATES_DIR, template_name)
            template = cv2.imread(template_path, 0)
            if template is None:
                continue
            res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
            if np.any(res >= 0.8):
                return template_name.split('.')[0]  # nome do jogo detectado
    except:
        return None
    return None

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
        streamer_name = live['user_name'].lower()
        if streamer_name not in [s.lower() for s in STREAMERS_INTERESSE]:
            continue

        thumbnail_url = live['thumbnail_url'].replace('{width}', '1920').replace('{height}', '1080')
        jogo_detectado = match_template_from_frame(thumbnail_url)
        if not jogo_detectado:
            continue

        game_name = buscar_game_name(game_id)
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
            'jogo_detectado': jogo_detectado,
            'game': game_name,
            'url': f"https://twitch.tv/{live['user_name']}"
        })
    return pragmatic_lives

# ------------------------------
# AGENDAMENTO AUTOMÁTICO
# ------------------------------
def rotina_agendada():
    twitch_lives = buscar_lives_twitch()
    lives_filtradas = filtrar_lives_twitch(twitch_lives)
    st.session_state['dados'] = lives_filtradas

def iniciar_agendamento():
    schedule.every(10).minutes.do(rotina_agendada)
    while True:
        schedule.run_pending()
        time.sleep(1)

agendador = threading.Thread(target=iniciar_agendamento, daemon=True)
agendador.start()

# ------------------------------
# STREAMLIT - INTERFACE COMPLETA
# ------------------------------
st.set_page_config(page_title="Monitor Cassino PP - Twitch & YouTube", layout="wide")

st.sidebar.subheader("➕ Adicionar novo streamer")
nome_novo_streamer = st.sidebar.text_input("Nome do streamer")
if st.sidebar.button("Adicionar streamer"):
    adicionar_streamer(nome_novo_streamer)
    st.sidebar.success(f"'{nome_novo_streamer}' adicionado. Recarregue a página para atualizar.")

st.subheader("📅 Escolha o período para buscar vídeos do YouTube")
data_inicio = st.date_input("Data de início", value=datetime.today() - timedelta(days=30))
data_fim = st.date_input("Data de fim", value=datetime.today())

if st.button("🔍 Buscar agora"):
    rotina_agendada()

if 'dados' in st.session_state and st.session_state['dados']:
    df = pd.DataFrame(st.session_state['dados'])
    st.dataframe(df.sort_values(by="started_at", ascending=False), use_container_width=True)

    if st.download_button("📁 Exportar para CSV", data=df.to_csv(index=False).encode('utf-8'),
                          file_name="lives_pragmatic.csv", mime="text/csv"):
        st.success("Arquivo exportado com sucesso!")
else:
    st.info("Nenhuma live encontrada com jogos da Pragmatic Play (imagem detectada).")
