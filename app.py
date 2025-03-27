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
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            print(f"Similaridade máxima: {max_val:.3f}")
            if max_val >= 0.7:
                return "pragmaticplay"
            else:
                print("Logo não encontrado no frame. Similaridade abaixo do limiar.")
        else:
            print("Template não foi carregado corretamente.")
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

def buscar_vods_twitch_por_periodo(data_inicio, data_fim):
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
                resultados.append({
                    "streamer": streamer,
                    "jogo_detectado": "-",
                    "timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "fonte": "Twitch VOD",
                    "categoria": vod.get("game_name", "Desconhecida"),
                    "url": vod['url']
                })
        except Exception as e:
            print(f"Erro ao buscar VODs: {e}")
    return resultados

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

# ------------------------------
# INTERFACE STREAMLIT
# ------------------------------
st.set_page_config(page_title="Monitor Cassino PP - Detecção", layout="wide")
st.title("🌀 Monitor Cassino Pragmatic Play")

st.sidebar.subheader("🎯 Filtros")
streamers_input = st.sidebar.text_input("Streamers (separados por vírgula)")
data_inicio = st.sidebar.date_input("Data de início", value=datetime.today() - timedelta(days=7))
data_fim = st.sidebar.date_input("Data de fim", value=datetime.today())
url_custom = st.sidebar.text_input("URL .m3u8 personalizada")

streamers_filtrados = [s.strip().lower() for s in streamers_input.split(",") if s.strip()] if streamers_input else []

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🔍 Verificar lives agora"):
        resultados = []
        for streamer in STREAMERS_INTERESSE:
            resultado_live = verificar_jogo_em_live(streamer)
            if resultado_live:
                jogo, categoria = resultado_live
                resultados.append({
                    "streamer": streamer,
                    "jogo_detectado": jogo,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fonte": "Live",
                    "categoria": categoria
                })
        st.session_state['dados_lives'] = resultados

with col2:
    if st.button("📺 Verificar VODs no período"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        dt_fim = datetime.combine(data_fim, datetime.max.time())
        vod_resultados = buscar_vods_twitch_por_periodo(dt_inicio, dt_fim)
        if vod_resultados:
            st.session_state['dados_vods'] = vod_resultados

with col3:
    if st.button("🌐 Rodar varredura na URL personalizada") and url_custom:
        resultado_url = varrer_url_customizada(url_custom)
        if resultado_url:
            st.session_state['dados_url'] = resultado_url

with col4:
    if st.button("🖼️ Varrer VODs com detecção de imagem"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        dt_fim = datetime.combine(data_fim, datetime.max.time())
        st.session_state['dados_vods_template'] = varrer_vods_com_template(dt_inicio, dt_fim)

if 'dados_lives' in st.session_state:
    df = pd.DataFrame(st.session_state['dados_lives'])
    if streamers_filtrados and 'streamer' in df.columns:
        df = df[df['streamer'].str.lower().isin(streamers_filtrados)]
    st.subheader("📱 Detecções em Lives")
    for col in ['categoria']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"🎯 {x}")
    st.dataframe(df, use_container_width=True)

if 'dados_vods' in st.session_state:
    df = pd.DataFrame(st.session_state['dados_vods'])
    if streamers_filtrados and 'streamer' in df.columns:
        df = df[df['streamer'].str.lower().isin(streamers_filtrados)]
    st.subheader("📌 Detecções em VODs")
    st.dataframe(df, use_container_width=True)

if 'dados_vods_template' in st.session_state:
    df = pd.DataFrame(st.session_state['dados_vods_template'])
    st.subheader("🧐 Detecções por imagem nas VODs")
    st.dataframe(df, use_container_width=True)

if 'dados_url' in st.session_state:
    df = pd.DataFrame(st.session_state['dados_url'])
    st.subheader("🌐 Detecção em URL personalizada")
    st.dataframe(df, use_container_width=True)

if not any(k in st.session_state for k in ['dados_lives', 'dados_vods', 'dados_url', 'dados_vods_template']):
    st.info("Nenhuma detecção encontrada.")
