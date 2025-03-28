# Melhorias implementadas:
# 1. Validação de streamers.
# 2. Nome de frame com timestamp para evitar sobrescrita.
# 3. Função para limpar arquivos temporários.
# 4. Suporte a múltiplos templates.
# 5. Detecção em Clips da Twitch sem download do vídeo.

import os
import cv2
import numpy as np
import requests
from datetime import datetime, timedelta
import streamlit as st
import subprocess
import re
import pandas as pd
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image

TEMPLATES_DIR = "templates"
MODEL_DIR = "modelo"
MODEL_PATH = os.path.join(MODEL_DIR, "modelo_pragmatic.keras")

HEADERS_TWITCH = {
    'Client-ID': 'gp762nuuoqcoxypju8c569th9wz7q5',
    'Authorization': f'Bearer moila7dw5ejlk3eja6ne08arw0oexs'
}

# --------------------------
# Utilitários e funções auxiliares
# --------------------------

def nomear_frame_temp(prefixo="frame"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefixo}_{timestamp}.jpg"

def limpar_frames_temp(pasta=".", prefixo="frame"):
    for file in os.listdir(pasta):
        if file.startswith(prefixo) and file.endswith(".jpg"):
            try:
                os.remove(os.path.join(pasta, file))
            except Exception as e:
                print(f"Erro ao remover {file}: {e}")

def match_template_from_image_multi(image_path, templates_dir=TEMPLATES_DIR, threshold=0.7):
    try:
        img = cv2.imread(image_path)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        for template_file in os.listdir(templates_dir):
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path, 0)
            if template is None:
                continue
            res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            print(f"Template {template_file} - Similaridade: {max_val:.3f}")
            if max_val >= threshold:
                return os.path.splitext(template_file)[0]
    except Exception as e:
        print(f"Erro no template matching: {e}")
    return None

@st.cache_resource
def carregar_modelo():
    if os.path.exists(MODEL_PATH):
        return load_model(MODEL_PATH)
    return None

if "modelo_ml" not in st.session_state:
    st.session_state["modelo_ml"] = carregar_modelo()

def prever_jogo_em_frame(frame_path):
    modelo = st.session_state.get("modelo_ml")
    if modelo is None:
        return match_template_from_image_multi(frame_path)
    try:
        img = image.load_img(frame_path, target_size=(224, 224))
        x = image.img_to_array(img)
        x = np.expand_dims(x, axis=0) / 255.0
        pred = modelo.predict(x)[0][0]
        print(f"Probabilidade modelo ML: {pred:.3f}")
        return "pragmaticplay" if pred >= 0.5 else None
    except Exception as e:
        print(f"Erro ao prever com modelo ML: {e}")
        return None

# --------------------------
# Funções principais do app
# --------------------------

def verificar_jogo_em_live(streamer):
    try:
        response = requests.get(f"https://api.twitch.tv/helix/users?login={streamer}", headers=HEADERS_TWITCH)
        user_data = response.json().get("data", [])
        if not user_data:
            return None
        user_id = user_data[0]['id']

        stream_response = requests.get(f"https://api.twitch.tv/helix/streams?user_id={user_id}", headers=HEADERS_TWITCH)
        stream_data = stream_response.json().get("data", [])
        if not stream_data:
            return None

        m3u8_url = f"https://usher.ttvnw.net/api/channel/hls/{streamer}.m3u8"
        frame_path = nomear_frame_temp(streamer)

        cmd = ["ffmpeg", "-y", "-ss", "10", "-i", m3u8_url, "-vf", "scale=1280:720", "-vframes", "1", frame_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)

        if os.path.exists(frame_path):
            jogo = prever_jogo_em_frame(frame_path)
            os.remove(frame_path)
            return jogo, stream_data[0].get("game_name", "Desconhecida")
    except Exception as e:
        print(f"Erro: {e}")
    return None

def verificar_clip_twitch(clip_url):
    try:
        match = re.search(r"clip/([\w-]+)", clip_url)
        if not match:
            return None
        slug = match.group(1)
        response = requests.get(f"https://api.twitch.tv/helix/clips?id={slug}", headers=HEADERS_TWITCH)
        data = response.json().get("data", [])
        if not data:
            return None
        video_url = data[0].get("thumbnail_url", "").split("-preview")[0] + ".mp4"
        frame_path = nomear_frame_temp("clip")
        cmd = ["ffmpeg", "-y", "-ss", "1", "-i", video_url, "-vf", "scale=1280:720", "-vframes", "1", frame_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if os.path.exists(frame_path):
            jogo = prever_jogo_em_frame(frame_path)
            st.image(frame_path, caption="Frame do Clip", use_column_width=True)
            os.remove(frame_path)
            return jogo
    except Exception as e:
        print(f"Erro no clip: {e}")
    return None

def varrer_url_customizada(url):
    for segundo in range(0, 60, 5):
        frame_path = nomear_frame_temp("custom")
        cmd = ["ffmpeg", "-y", "-ss", str(segundo), "-i", url, "-vf", "scale=1280:720", "-vframes", "1", frame_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if os.path.exists(frame_path):
            jogo = prever_jogo_em_frame(frame_path)
            if jogo:
                st.image(frame_path, caption=f"Frame {segundo}s", use_column_width=True)
                os.remove(frame_path)
                return [{"jogo_detectado": jogo, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fonte": f"Custom URL ({segundo}s)"}]
            os.remove(frame_path)
    return []

# --------------------------
# Interface
# --------------------------

st.set_page_config(page_title="Monitor Cassino PP - Detecção", layout="wide")

st.title("🎰 Monitor Cassino Pragmatic Play")

st.sidebar.subheader("🎯 Filtros")
streamers_input = st.sidebar.text_input("Streamers (separados por vírgula)")
data_inicio = st.sidebar.date_input("Data de início", value=datetime.today() - timedelta(days=7))
data_fim = st.sidebar.date_input("Data de fim", value=datetime.today())
url_custom = st.sidebar.text_input("URL .m3u8 personalizada")
url_clip = st.sidebar.text_input("URL do Clip da Twitch")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("🔍 Verificar Live(s)"):
        streamers = [s.strip().lower() for s in streamers_input.split(",") if s.strip()]
        resultados = []
        for streamer in streamers:
            res = verificar_jogo_em_live(streamer)
            if res:
                jogo, categoria = res
                resultados.append({"streamer": streamer, "jogo_detectado": jogo, "timestamp": datetime.now(), "fonte": "Live", "categoria": categoria})
        if resultados:
            st.dataframe(pd.DataFrame(resultados))

with col2:
    if st.button("🌐 Verificar URL personalizada") and url_custom:
        res = varrer_url_customizada(url_custom)
        if res:
            st.dataframe(pd.DataFrame(res))

with col3:
    if st.button("🎬 Verificar Clip") and url_clip:
        res = verificar_clip_twitch(url_clip)
        if res:
            st.success(f"Jogo detectado: {res}")
        else:
            st.info("Nenhum jogo detectado no clip.")
