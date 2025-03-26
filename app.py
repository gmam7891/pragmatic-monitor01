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
import re

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
# INTERFACE STREAMLIT (EXTRA: VERIFICAR URL DIRETA)
# ------------------------------
st.sidebar.subheader("🔗 Verificar jogo via URL direta")
url_direta = st.sidebar.text_input("Cole o link da Twitch (live ou VOD)")
if st.sidebar.button("🚀 Verificar URL") and url_direta:
    m3u8 = url_para_m3u8(url_direta)
    if m3u8:
        temp_path = "frame_url.jpg"
        frame_ok = capturar_frame_ffmpeg_imageio(m3u8, temp_path)
        if frame_ok:
            jogo = match_template_from_image(temp_path)
            os.remove(temp_path)
            if jogo:
                st.success(f"Jogo da Pragmatic detectado: {jogo}")
            else:
                st.warning("Nenhum jogo da Pragmatic foi detectado.")
        else:
            st.error("Erro ao capturar frame da URL fornecida.")
    else:
        st.error("URL inválida ou não reconhecida.")
