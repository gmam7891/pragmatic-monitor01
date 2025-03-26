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
import imageio_ffmpeg as ffmpeg
import threading
import schedule
import time
import subprocess

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
STREAMERS_FILE = "streamers.txt"
TEMPLATES_DIR = "templates/"
MAIN_TEMPLATE_NAME = "botao"

# ------------------------------
# GARANTIR QUE A PASTA TEMPLATES EXISTA
# ------------------------------
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

# ------------------------------
# UTILITÁRIOS
# ------------------------------
def carregar_streamers():
    if not os.path.exists(STREAMERS_FILE):
        with open(STREAMERS_FILE, "w", encoding="utf-8") as f:
            f.write("jukes\n")
    with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

STREAMERS_INTERESSE = carregar_streamers()

# ------------------------------
# TEMPLATE MATCHING
# ------------------------------
def match_template_from_image(image_path):
    img = cv2.imread(image_path)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    template_path = os.path.join(TEMPLATES_DIR, f"{MAIN_TEMPLATE_NAME}.png")
    if not os.path.exists(template_path):
        template_path = os.path.join(TEMPLATES_DIR, f"{MAIN_TEMPLATE_NAME}.jpg")
    if not os.path.exists(template_path):
        return None

    template = cv2.imread(template_path, 0)
    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    if np.any(res >= 0.8):
        return MAIN_TEMPLATE_NAME
    return None

# ------------------------------
# CAPTURA DE FRAME COM IMAGEIO_FFMPEG
# ------------------------------
def get_stream_m3u8_url(user_login):
    return f"https://usher.ttvnw.net/api/channel/hls/{user_login}.m3u8"

def capturar_frame_ffmpeg_imageio(m3u8_url, output_path="frame.jpg"):
    try:
        width, height = 640, 360
        cmd = [
            "ffmpeg",
            "-y",
            "-i", m3u8_url,
            "-vf", f"scale={width}:{height}",
            "-frames:v", "1",
            "-q:v", "2",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        return output_path if os.path.exists(output_path) else None
    except Exception:
        return None

def verificar_jogo_em_live(streamer):
    m3u8_url = get_stream_m3u8_url(streamer)
    temp_frame = f"{streamer}_frame.jpg"
    if capturar_frame_ffmpeg_imageio(m3u8_url, temp_frame):
        jogo = match_template_from_image(temp_frame)
        os.remove(temp_frame)
        return jogo
    return None

# ------------------------------
# ANÁLISE DE VODs
# ------------------------------
def buscar_vods_twitch_por_periodo(data_inicio, data_fim):
    resultados = []
    for streamer in STREAMERS_INTERESSE:
        user_response = requests.get(BASE_URL_TWITCH + f'users?login={streamer}', headers=HEADERS_TWITCH)
        user_data = user_response.json().get('data', [])
        if not user_data:
            continue
        user_id = user_data[0]['id']
        vod_response = requests.get(BASE_URL_TWITCH + f'videos?user_id={user_id}&type=archive&first=10', headers=HEADERS_TWITCH)
        vods = vod_response.json().get('data', [])
        for vod in vods:
            created_at = datetime.strptime(vod['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if not (data_inicio <= created_at <= data_fim):
                continue
            m3u8_url = f"https://vod-secure.twitch.tv/{vod['thumbnail_url'].split('%')[0].split('/')[-1]}.m3u8"
            temp_frame = f"vod_{vod['id']}_frame.jpg"
            if capturar_frame_ffmpeg_imageio(m3u8_url, temp_frame):
                jogo = match_template_from_image(temp_frame)
                os.remove(temp_frame)
                if jogo:
                    resultados.append({
                        "streamer": streamer,
                        "jogo_detectado": jogo,
                        "timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "fonte": "Twitch VOD",
                        "url": vod['url']
                    })
    return resultados

def buscar_todos_vods_por_periodo(data_inicio, data_fim):
    resultados = []
    for streamer in STREAMERS_INTERESSE:
        user_response = requests.get(BASE_URL_TWITCH + f'users?login={streamer}', headers=HEADERS_TWITCH)
        user_data = user_response.json().get('data', [])
        if not user_data:
            continue
        user_id = user_data[0]['id']
        vod_response = requests.get(BASE_URL_TWITCH + f'videos?user_id={user_id}&type=archive&first=20', headers=HEADERS_TWITCH)
        vods = vod_response.json().get('data', [])
        for vod in vods:
            created_at = datetime.strptime(vod['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if not (data_inicio <= created_at <= data_fim):
                continue
            resultados.append({
                "streamer": vod["user_name"],
                "title": vod["title"],
                "timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "jogo_detectado": "-",
                "fonte": "VOD bruto",
                "url": vod["url"]
            })
    return resultados

# ------------------------------
# AGENDAMENTO AUTOMÁTICO
# ------------------------------
def rotina_agendada():
    resultados = []
    for streamer in STREAMERS_INTERESSE:
        jogo = verificar_jogo_em_live(streamer)
        if jogo:
            resultados.append({
                "streamer": streamer,
                "jogo_detectado": jogo,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "fonte": "Live"
            })
    st.session_state['dados_lives'] = resultados

def iniciar_agendamento():
    schedule.every(10).minutes.do(rotina_agendada)
    while True:
        schedule.run_pending()
        time.sleep(1)

agendador = threading.Thread(target=iniciar_agendamento, daemon=True)
agendador.start()

# ------------------------------
# INTERFACE STREAMLIT
# ------------------------------
st.set_page_config(page_title="Monitor Cassino PP - Detecção ao vivo", layout="wide")
st.title("🎰 Monitor de Jogos da Pragmatic Play - Detecção por Imagem")

st.sidebar.subheader("🎯 Filtrar por streamer")
streamers_input = st.sidebar.text_input("Digite os nomes separados por vírgula", "")
data_inicio = st.sidebar.date_input("Data de início", value=datetime.today() - timedelta(days=7))
data_fim = st.sidebar.date_input("Data de fim", value=datetime.today())

streamers_filtrados = [s.strip().lower() for s in streamers_input.split(",") if s.strip()] if streamers_input else []

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔍 Verificar lives agora"):
        rotina_agendada()

with col2:
    if st.button("📺 Verificar VODs no período"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        dt_fim = datetime.combine(data_fim, datetime.max.time())
        vod_resultados = buscar_vods_twitch_por_periodo(dt_inicio, dt_fim)
        if vod_resultados:
            st.session_state['dados_vods'] = vod_resultados

with col3:
    if st.button("📂 Exibir todos os VODs (sem filtro por imagem)"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        dt_fim = datetime.combine(data_fim, datetime.max.time())
        todos_vods = buscar_todos_vods_por_periodo(dt_inicio, dt_fim)
        if todos_vods:
            st.session_state['todos_vods'] = todos_vods

# Mostrar resultados
if 'dados_lives' in st.session_state and st.session_state['dados_lives']:
    df = pd.DataFrame(st.session_state['dados_lives'])
    if streamers_filtrados:
        df = df[df['streamer'].str.lower().isin(streamers_filtrados)]
    st.subheader("📡 Detecções em Lives Ao Vivo")
    st.dataframe(df, use_container_width=True)
    st.download_button("📁 Exportar CSV - Lives", data=df.to_csv(index=False).encode('utf-8'), file_name="detecao_lives.csv", mime="text/csv")

if 'dados_vods' in st.session_state and st.session_state['dados_vods']:
    df_vod = pd.DataFrame(st.session_state['dados_vods'])
    if streamers_filtrados:
        df_vod = df_vod[df_vod['streamer'].str.lower().isin(streamers_filtrados)]
    st.subheader("📼 Detecções em VODs")
    st.dataframe(df_vod, use_container_width=True)
    st.download_button("📁 Exportar CSV - VODs", data=df_vod.to_csv(index=False).encode('utf-8'), file_name="detecao_vods.csv", mime="text/csv")

if 'todos_vods' in st.session_state and st.session_state['todos_vods']:
    df_todos = pd.DataFrame(st.session_state['todos_vods'])
    if streamers_filtrados:
        df_todos = df_todos[df_todos['streamer'].str.lower().isin(streamers_filtrados)]
    st.subheader("📁 Todos os VODs (sem verificação de imagem)")
    st.dataframe(df_todos, use_container_width=True)
    st.download_button("📁 Exportar CSV - VODs brutos", data=df_todos.to_csv(index=False).encode('utf-8'), file_name="vods_brutos.csv", mime="text/csv")

if not st.session_state.get('dados_lives') and not st.session_state.get('dados_vods') and not st.session_state.get('todos_vods'):
    st.info("Nenhuma detecção encontrada nas lives ou VODs.")
