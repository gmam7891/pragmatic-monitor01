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
    try:
        img = cv2.imread(image_path)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        for template_name in os.listdir(TEMPLATES_DIR):
            template_path = os.path.join(TEMPLATES_DIR, template_name)
            template = cv2.imread(template_path, 0)
            if template is None:
                continue
            res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
            if np.any(res >= 0.8):
                return template_name.split('.')[0]
    except Exception as e:
        print(f"Erro no template matching: {e}")
    return None

# ------------------------------
# CAPTURA DE FRAME COM FFMPEG
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
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        return output_path if os.path.exists(output_path) else None
    except Exception as e:
        print(f"Erro ao capturar frame: {e}")
        return None

# Nova função para varredura de uma URL customizada com 24 FPS
def varrer_url_customizada(url):
    resultados = []
    for i in range(5):  # Captura 5 frames a 24 FPS (~0.04s entre frames)
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
        time.sleep(1/24)
    return resultados

# ------------------------------
# VERIFICAÇÃO DE LIVES
# ------------------------------
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
        try:
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
        except Exception as e:
            print(f"Erro ao buscar VODs: {e}")
    return resultados

# Continuação da lógica de exibição e outras funções... (mantida conforme necessidade)
