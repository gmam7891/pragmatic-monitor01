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

if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

def carregar_streamers():
    if not os.path.exists(STREAMERS_FILE):
        with open(STREAMERS_FILE, "w", encoding="utf-8") as f:
            f.write("jukes\n")
    with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

STREAMERS_INTERESSE = carregar_streamers()

def match_template_from_image(image_path):
    try:
        img = cv2.imread(image_path)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        template_path = os.path.join(TEMPLATES_DIR, "pragmaticplay.png")
        template = cv2.imread(template_path, 0)
        if template is not None:
            res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
            if np.any(res >= 0.8):
                return "pragmaticplay"
    except Exception as e:
        print(f"Erro no template matching: {e}")
    return None

def get_stream_m3u8_url(user_login):
    return f"https://usher.ttvnw.net/api/channel/hls/{user_login}.m3u8"

def get_vod_m3u8_url(vod_id):
    return f"https://vod-secure.twitch.tv/{vod_id}/chunked/index-dvr.m3u8"

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
        time.sleep(1/24)
    return resultados

def verificar_jogo_em_live(streamer):
    try:
        user_response = requests.get(BASE_URL_TWITCH + f'users?login={streamer}', headers=HEADERS_TWITCH)
        user_data = user_response.json().get('data', [])
        if not user_data:
            return None
        user_id = user_data[0]['id']
        stream_response = requests.get(BASE_URL_TWITCH + f'streams?user_id={user_id}', headers=HEADERS_TWITCH)
        stream_data = stream_response.json().get('data', [])
        if not stream_data:
            return None

        game_id = stream_data[0].get('game_id')
        game_name = "Desconhecida"
        if game_id:
            game_response = requests.get(BASE_URL_TWITCH + f'games?id={game_id}', headers=HEADERS_TWITCH)
            game_data = game_response.json().get("data", [])
            if game_data:
                game_name = game_data[0]['name']

        m3u8_url = get_stream_m3u8_url(streamer)
        temp_frame = f"{streamer}_frame.jpg"
        if capturar_frame_ffmpeg_imageio(m3u8_url, temp_frame):
            jogo = match_template_from_image(temp_frame)
            os.remove(temp_frame)
            return jogo, game_name
    except Exception as e:
        print(f"Erro ao verificar live de {streamer}: {e}")
    return None

def varrer_vods_com_template(data_inicio, data_fim):
    resultados = []
    for streamer in STREAMERS_INTERESSE:
        try:
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

                vod_url = vod['url']
                vod_id = vod_url.split('/')[-1]
                m3u8_url = f"https://vod-secure.twitch.tv/{vod_id}/chunked/index-dvr.m3u8"

                frame_path = f"vod_frame_{vod_id}.jpg"
                if capturar_frame_ffmpeg_imageio(m3u8_url, frame_path):
                    jogo = match_template_from_image(frame_path)
                    os.remove(frame_path)
                    if jogo:
                        resultados.append({
                            "streamer": streamer,
                            "jogo_detectado": jogo,
                            "timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            "fonte": "VOD",
                            "categoria": vod.get("game_name", "Desconhecida"),
                            "url": vod_url
                        })
        except Exception as e:
            print(f"Erro ao buscar e varrer VODs: {e}")
    return resultados

# Adicione o botão na interface Streamlit:
with st.sidebar:
    if st.button("🔎 Varrer VODs com detecção de imagem"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        dt_fim = datetime.combine(data_fim, datetime.max.time())
        st.session_state['dados_vods_template'] = varrer_vods_com_template(dt_inicio, dt_fim)

# Exibição dos resultados
if 'dados_vods_template' in st.session_state:
    df = pd.DataFrame(st.session_state['dados_vods_template'])
    st.subheader("🧠 Detecções por imagem nas VODs")
    st.dataframe(df, use_container_width=True)
