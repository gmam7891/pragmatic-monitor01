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
import subprocess
import re
import schedule
import time

# ------------------------------
# CONFIGURAÇÕES INICIAIS
# ------------------------------
CLIENT_ID = '9qkw87yuzfolbyk3lva3n76qhucrxe'
ACCESS_TOKEN = '6qgrr9jy215szvksczidb8hslztux8'
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

    template_path_png = os.path.join(TEMPLATES_DIR, f"{MAIN_TEMPLATE_NAME}.png")
    template_path_jpg = os.path.join(TEMPLATES_DIR, f"{MAIN_TEMPLATE_NAME}.jpg")

    if os.path.exists(template_path_png):
        template = cv2.imread(template_path_png, 0)
    elif os.path.exists(template_path_jpg):
        template = cv2.imread(template_path_jpg, 0)
    else:
        return None

    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    if np.any(res >= 0.8):
        return MAIN_TEMPLATE_NAME
    return None

# ------------------------------
# CAPTURA DE MULTIPLOS FRAMES COM IMAGEIO_FFMPEG
# ------------------------------
def capturar_multiplos_frames(m3u8_url, total_frames=25, output_dir="frames"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    width, height = 640, 360
    cmd = [
        "ffmpeg",
        "-y",
        "-i", m3u8_url,
        "-vf", f"fps=5,scale={width}:{height}",
        "-vframes", str(total_frames),
        f"{output_dir}/frame_%03d.jpg"
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".jpg")]
    except Exception:
        return []

# ------------------------------
# VERIFICAR LIVE STREAMER
# ------------------------------
def verificar_jogo_em_live(streamer):
    m3u8_url = f"https://usher.ttvnw.net/api/channel/hls/{streamer}.m3u8"
    frame_paths = capturar_multiplos_frames(m3u8_url)
    for path in frame_paths:
        jogo = match_template_from_image(path)
        os.remove(path)
        if jogo:
            return jogo
    return None

# ------------------------------
# VERIFICAÇÃO POR URL COLADA
# ------------------------------
def url_para_m3u8(url):
    match_vod = re.search(r'twitch\\.tv/videos/(\\d+)', url)
    if match_vod:
        video_id = match_vod.group(1)
        return f"https://vod-secure.twitch.tv/{video_id}/{video_id}.m3u8"

    match_live = re.search(r'twitch\\.tv/([\\w\\d_]+)', url)
    if match_live:
        user_login = match_live.group(1)
        return f"https://usher.ttvnw.net/api/channel/hls/{user_login}.m3u8"

    return None

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
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
st.set_page_config(page_title="Monitor de Jogos Pragmatic Play - Verificação ao Vivo", layout="wide")
st.title("🎰 Monitor de Jogos Pragmatic Play - Verificação ao Vivo")

st.sidebar.subheader("🔗 Verificar jogo via URL direta")
url_direta = st.sidebar.text_input("Cole o link da Twitch (live ou VOD)")
if st.sidebar.button("🚀 Verificar URL") and url_direta:
    m3u8 = url_para_m3u8(url_direta)
    if m3u8:
        frame_paths = capturar_multiplos_frames(m3u8)
        detectado = False
        for path in frame_paths:
            jogo = match_template_from_image(path)
            os.remove(path)
            if jogo:
                st.success(f"Jogo da Pragmatic detectado: {jogo}")
                detectado = True
                break
        if not detectado:
            st.warning("Nenhum jogo da Pragmatic foi detectado.")
    else:
        st.error("URL inválida ou não reconhecida.")

# ------------------------------
# VERIFICAÇÃO DE TODOS STREAMERS
# ------------------------------
st.write("Clique abaixo para verificar os streamers configurados.")

if st.button("🎯 Verificar lives ao vivo via ffmpeg"):
    resultados = []
    for streamer in STREAMERS_INTERESSE:
        jogo = verificar_jogo_em_live(streamer)
        if jogo:
            resultados.append({
                "streamer": streamer,
                "jogo_detectado": jogo,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    if resultados:
        df = pd.DataFrame(resultados)
        st.dataframe(df)
        st.download_button("📁 Exportar CSV - Detecções", data=df.to_csv(index=False).encode('utf-8'), file_name="detecoes_pragmatic.csv", mime="text/csv")
    else:
        st.info("Nenhum jogo da Pragmatic detectado em tempo real.")
