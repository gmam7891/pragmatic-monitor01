# Monitor Cassino PP - Código Compacto Completo

from datetime import datetime, timedelta
import requests
import streamlit as st
import pandas as pd
import os
import cv2
import numpy as np
from PIL import Image
import subprocess
import logging
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

st.set_page_config(page_title="Monitor Cassino PP - Detecção", layout="wide")

# Configurações iniciais
logging.basicConfig(filename='monitor.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
CLIENT_ID = st.secrets["twitch"]["client_id"]
ACCESS_TOKEN = st.secrets["twitch"]["access_token"]
HEADERS_TWITCH = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {ACCESS_TOKEN}'}
BASE_URL_TWITCH = 'https://api.twitch.tv/helix/'
STREAMERS_FILE = "streamers.txt"
TEMPLATES_DIR = "templates/"
MODEL_DIR = "modelo"
MODEL_PATH = os.path.join(MODEL_DIR, "modelo_pragmatic.keras")

if not os.path.exists(TEMPLATES_DIR): os.makedirs(TEMPLATES_DIR)

# Funções auxiliares
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
        res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return "pragmaticplay" if max_val >= 0.7 else None
    except Exception as e:
        logging.exception(f"Erro no template matching: {e}")
        return None

def get_stream_m3u8_url(user_login):
    return f"https://usher.ttvnw.net/api/channel/hls/{user_login}.m3u8"

def capturar_frame_ffmpeg_imageio(m3u8_url, output_path="frame.jpg", skip_seconds=10):
    try:
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(skip_seconds), "-i", m3u8_url,
            "-vf", "scale=1280:720", "-vframes", "1", "-q:v", "2", output_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        return output_path if os.path.exists(output_path) else None
    except Exception as e:
        logging.exception(f"Erro ao capturar frame: {e}")
        return None

def varrer_url_customizada(url):
    resultados = []
    for i in range(12):
        skip = i * 5
        frame_path = f"custom_frame_{i}.jpg"
        if capturar_frame_ffmpeg_imageio(url, frame_path, skip_seconds=skip):
            jogo = prever_jogo_em_frame(frame_path)
            if jogo:
                resultados.append({"jogo_detectado": jogo, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fonte": f"URL personalizada (segundo {skip})"})
                st.image(frame_path, caption=f"Frame detectado no segundo {skip}", use_column_width=True)
                break
            else:
                os.remove(frame_path)
    return resultados

@st.cache_resource
def carregar_modelo():
    if os.path.exists(MODEL_PATH): return load_model(MODEL_PATH)
    else: st.warning("Modelo de ML não treinado."); return None

if "modelo_ml" not in st.session_state and os.path.exists(MODEL_PATH):
    st.session_state["modelo_ml"] = load_model(MODEL_PATH)

def prever_jogo_em_frame(frame_path):
    modelo = st.session_state.get("modelo_ml")
    if modelo is None: return match_template_from_image(frame_path)
    try:
        img = image.load_img(frame_path, target_size=(224, 224))
        x = image.img_to_array(img); x = np.expand_dims(x, axis=0) / 255.0
        pred = modelo.predict(x)[0][0]
        return "pragmaticplay" if pred >= 0.5 else None
    except Exception as e:
        logging.exception(f"Erro modelo ML: {e}")
        return None

# Interface Streamlit
st.sidebar.subheader("🎯 Filtros")
streamers_input = st.sidebar.text_input("Streamers (separados por vírgula)")
data_inicio = st.sidebar.date_input("Data de início", value=datetime.today() - timedelta(days=7))
data_fim = st.sidebar.date_input("Data de fim", value=datetime.today())
url_custom = st.sidebar.text_input("URL .m3u8 personalizada")

if st.sidebar.button("🚀 Treinar modelo agora"):
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    from tensorflow.keras import layers, models
    st.sidebar.write("📦 Preparando dados...")
    datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)
    train_gen = datagen.flow_from_directory("dataset", target_size=(224, 224), batch_size=32, class_mode='binary', subset='training')
    val_gen = datagen.flow_from_directory("dataset", target_size=(224, 224), batch_size=32, class_mode='binary', subset='validation')
    model = models.Sequential([
        layers.Conv2D(32, (3,3), activation='relu', input_shape=(224,224,3)),
        layers.MaxPooling2D(2,2),
        layers.Conv2D(64, (3,3), activation='relu'),
        layers.MaxPooling2D(2,2),
        layers.Flatten(),
        layers.Dense(64, activation='relu'),
        layers.Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    st.sidebar.write("⚙️ Iniciando treinamento...")
    model.fit(train_gen, validation_data=val_gen, epochs=5, callbacks=[EarlyStopping(patience=2), ModelCheckpoint(MODEL_PATH, save_best_only=True)])
    if os.path.exists(MODEL_PATH): st.sidebar.success("✅ Modelo salvo com sucesso."); st.rerun()

streamers_filtrados = [s.strip().lower() for s in streamers_input.split(",") if s.strip()] if streamers_input else []

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🔍 Verificar lives agora"):
        resultados = []
        for streamer in STREAMERS_INTERESSE:
            try:
                user_id = requests.get(BASE_URL_TWITCH + f'users?login={streamer}', headers=HEADERS_TWITCH).json()["data"][0]["id"]
                live = requests.get(BASE_URL_TWITCH + f'streams?user_id={user_id}', headers=HEADERS_TWITCH).json()["data"]
                if live:
                    categoria = live[0].get("game_name", "Desconhecida")
                    m3u8_url = get_stream_m3u8_url(streamer)
                    frame = capturar_frame_ffmpeg_imageio(m3u8_url, f"{streamer}.jpg")
                    jogo = prever_jogo_em_frame(frame) if frame else None
                    if frame: os.remove(frame)
                    if jogo:
                        resultados.append({"streamer": streamer, "jogo_detectado": jogo, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fonte": "Live", "categoria": categoria})
            except Exception as e:
                logging.exception(f"Erro live {streamer}: {e}")
        st.session_state['dados_lives'] = resultados

with col2:
    if st.button("📺 Verificar VODs no período"):
        # (opcional: adicionar função buscar_vods_twitch_por_periodo aqui)
        pass

with col3:
    if st.button("🌐 Rodar varredura na URL personalizada") and url_custom:
        resultado_url = varrer_url_customizada(url_custom)
        if resultado_url: st.session_state['dados_url'] = resultado_url

with col4:
    if st.button("🖼️ Varrer VODs com detecção de imagem"):
        # (opcional: adicionar varredura completa em VODs)
        pass

abas = st.tabs(["📡 Lives", "🎞️ VODs", "🖼️ VODs com Template", "🌐 URL personalizada"])

with abas[0]:
    if 'dados_lives' in st.session_state:
        df = pd.DataFrame(st.session_state['dados_lives'])
        if streamers_filtrados:
            df = df[df['streamer'].str.lower().isin(streamers_filtrados)]
        st.dataframe(df, use_container_width=True)

with abas[3]:
    if 'dados_url' in st.session_state:
        df = pd.DataFrame(st.session_state['dados_url'])
        st.dataframe(df, use_container_width=True)

if not any(k in st.session_state for k in ['dados_lives', 'dados_vods', 'dados_url', 'dados_vods_template']):
    st.info("Nenhuma detecção encontrada ainda.")
