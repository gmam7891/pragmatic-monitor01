from datetime import datetime, timedelta
import requests
import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from PIL import Image
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

if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

def carregar_streamers():
    if not os.path.exists(STREAMERS_FILE):
        with open(STREAMERS_FILE, "w", encoding="utf-8") as f:
            f.write("jukes\n")
    with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

STREAMERS_INTERESSE = carregar_streamers()

def match_template_from_image(image_path, template_path="templates/pragmaticplay.png"):
    try:
        img = cv2.imread(image_path)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        template = cv2.imread(template_path, 0)
        if template is not None:
            res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
            if np.any(res >= 0.7):  # Limiar ajustado
                return "pragmaticplay"
    except Exception as e:
        print(f"Erro no template matching: {e}")
    return None

def get_stream_m3u8_url(user_login):
    return f"https://usher.ttvnw.net/api/channel/hls/{user_login}.m3u8"

def capturar_frame_ffmpeg_imageio(m3u8_url, output_path="frame.jpg"):
    try:
        width, height = 1280, 720
        cmd = [
            "ffmpeg",
            "-y",
            "-i", m3u8_url,
            "-vf", f"scale={width}:{height}",
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        return output_path if os.path.exists(output_path) else None
    except Exception as e:
        print(f"Erro ao capturar frame: {e}")
        return None

def varrer_url_customizada(url):
    resultados = []
    for i in range(5):
        frame_path = f"custom_frame_{i}.jpg"
        if capturar_frame_ffmpeg_imageio(url, frame_path):
            jogo = match_template_from_image(frame_path)
            os.remove(frame_path)
            if jogo:
                resultados.append({
                    "jogo_detectado": jogo,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fonte": "URL personalizada"
                })
                break
    return resultados

# ------------------------------
# INTERFACE STREAMLIT
# ------------------------------
st.set_page_config(page_title="Monitor Cassino PP - Detecção", layout="wide")
st.title("🌀 Monitor Cassino Pragmatic Play")

st.sidebar.subheader("🎯 Filtros")
url_custom = st.sidebar.text_input("URL .m3u8 personalizada")

col1 = st.columns(1)[0]
with col1:
    if st.button("🌐 Rodar varredura na URL personalizada") and url_custom:
        resultado_url = varrer_url_customizada(url_custom)
        if resultado_url:
            st.session_state['dados_url'] = resultado_url

if 'dados_url' in st.session_state:
    df = pd.DataFrame(st.session_state['dados_url'])
    st.subheader("🌐 Detecção em URL personalizada")
    st.dataframe(df, use_container_width=True)

if not 'dados_url' in st.session_state:
    st.info("Nenhuma detecção encontrada.")
