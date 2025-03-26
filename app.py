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
            "-i", m3u8_url,
            "-vf", f"scale={width}:{height}",
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-"
        ]
        process = ffmpeg.get_ffmpeg_exe()
        pipe = ffmpeg.read_frames(cmd, pix_fmt='rgb24', output_resolution=(width, height))
        with open(output_path, "wb") as f:
            f.write(pipe.read())
        return output_path
    except Exception as e:
        return None

def verificar_jogo_em_live(streamer):
    m3u8_url = get_stream_m3u8_url(streamer)
    temp_frame = f"{streamer}_frame.jpg"
    if capturar_frame_ffmpeg_imageio(m3u8_url, temp_frame) and os.path.exists(temp_frame):
        jogo = match_template_from_image(temp_frame)
        os.remove(temp_frame)
        return jogo
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
st.set_page_config(page_title="Monitor Cassino PP - Detecção ao vivo", layout="wide")
st.title("🎰 Monitor de Jogos da Pragmatic Play - Detecção por Imagem em Lives")

st.sidebar.subheader("🎯 Filtrar por streamer")
streamers_input = st.sidebar.text_input("Digite os nomes separados por vírgula", "")

streamers_filtrados = [s.strip().lower() for s in streamers_input.split(",") if s.strip()] if streamers_input else []

if st.button("🔍 Verificar lives agora"):
    rotina_agendada()

if 'dados_lives' in st.session_state and st.session_state['dados_lives']:
    df = pd.DataFrame(st.session_state['dados_lives'])
    if streamers_filtrados:
        df = df[df['streamer'].str.lower().isin(streamers_filtrados)]
    st.dataframe(df, use_container_width=True)
    st.download_button("📁 Exportar CSV", data=df.to_csv(index=False).encode('utf-8'), file_name="detecao_pragmatic.csv", mime="text/csv")
else:
    st.info("Nenhuma detecção encontrada nas lives neste momento.")
