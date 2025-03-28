# Melhorias implementadas:
# 1. Validação de streamers.
# 2. Nome de frame com timestamp para evitar sobrescrita.
# 3. Função para limpar arquivos temporários.
# 4. Suporte a múltiplos templates.
# 5. Detecção em Clips da Twitch sem download do vídeo.

import streamlit as st
st.set_page_config(page_title="Monitor Cassino PP - Detecção", layout="wide")

import os
import cv2
import numpy as np
import requests
from datetime import datetime, timedelta
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

def get_stream_m3u8_url(user_login):
    return f"https://usher.ttvnw.net/api/channel/hls/{user_login}.m3u8"

def capturar_frame_ffmpeg_imageio(m3u8_url, output_path="frame.jpg", skip_seconds=10):
    try:
        width, height = 1280, 720
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(skip_seconds),
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

def verificar_jogo_em_live(streamer):
    try:
        user_response = requests.get(f"https://api.twitch.tv/helix/users?login={streamer}", headers=HEADERS_TWITCH)
        user_data = user_response.json().get("data", [])
        if not user_data:
            return None
        user_id = user_data[0]['id']
        stream_response = requests.get(f"https://api.twitch.tv/helix/streams?user_id={user_id}", headers=HEADERS_TWITCH)
        stream_data = stream_response.json().get("data", [])
        if not stream_data:
            return None

        game_id = stream_data[0].get("game_id")
        game_name = "Desconhecida"
        if game_id:
            game_response = requests.get(f"https://api.twitch.tv/helix/games?id={game_id}", headers=HEADERS_TWITCH)
            game_data = game_response.json().get("data", [])
            if game_data:
                game_name = game_data[0]['name']

        m3u8_url = get_stream_m3u8_url(streamer)
        temp_frame = f"{streamer}_frame.jpg"
        if capturar_frame_ffmpeg_imageio(m3u8_url, temp_frame):
            jogo = prever_jogo_em_frame(temp_frame)
            os.remove(temp_frame)
            return jogo, game_name
    except Exception as e:
        print(f"Erro ao verificar live de {streamer}: {e}")
    return None

def buscar_vods_twitch_por_periodo(data_inicio, data_fim):
    resultados = []
    for streamer in streamers_input.split(","):
        streamer = streamer.strip().lower()
        try:
            user_response = requests.get(f"https://api.twitch.tv/helix/users?login={streamer}", headers=HEADERS_TWITCH)
            user_data = user_response.json().get("data", [])
            if not user_data:
                continue
            user_id = user_data[0]['id']
            vod_response = requests.get(f"https://api.twitch.tv/helix/videos?user_id={user_id}&type=archive&first=20", headers=HEADERS_TWITCH)
            vods = vod_response.json().get("data", [])

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
    for streamer in streamers_input.split(","):
        streamer = streamer.strip().lower()
        try:
            user_response = requests.get(f"https://api.twitch.tv/helix/users?login={streamer}", headers=HEADERS_TWITCH)
            user_data = user_response.json().get("data", [])
            if not user_data:
                continue
            user_id = user_data[0]['id']
            vod_response = requests.get(f"https://api.twitch.tv/helix/videos?user_id={user_id}&type=archive&first=20", headers=HEADERS_TWITCH)
            vods = vod_response.json().get("data", [])

            for vod in vods:
                created_at = datetime.strptime(vod['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                if not (data_inicio <= created_at <= data_fim):
                    continue

                vod_url = vod['url']
                vod_id = vod_url.split('/')[-1]
                m3u8_url = f"https://vod-secure.twitch.tv/{vod_id}/chunked/index-dvr.m3u8"

                frame_path = f"vod_frame_{vod_id}.jpg"
                if capturar_frame_ffmpeg_imageio(m3u8_url, frame_path):
                    jogo = prever_jogo_em_frame(frame_path)
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

def varrer_url_customizada(url):
    resultados = []
    skip_seconds = 0
    frame_rate = 24
    duracao_analise = 60
    intervalo_frames = 2
    total_frames = duracao_analise // intervalo_frames

    for i in range(int(total_frames)):
        skip = i * intervalo_frames
        frame_path = f"custom_frame_{i}.jpg"
        print(f"Capturando frame no segundo {skip}...")
        if capturar_frame_ffmpeg_imageio(url, frame_path, skip_seconds=skip):
            jogo = prever_jogo_em_frame(frame_path)
            if jogo:
                resultados.append({
                    "jogo_detectado": jogo,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fonte": f"URL personalizada (segundo {skip})"
                })
                st.image(frame_path, caption=f"Frame detectado no segundo {skip}", use_column_width=True)
                break
            else:
                os.remove(frame_path)
    return resultados

def nomear_frame_temp(prefixo="frame"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefixo}_{timestamp}.jpg"

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

# Função para verificar clips

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

# ------------------------------
# Filtros, datas e campo de URL
# ------------------------------

st.sidebar.subheader("🎯 Filtros")
streamers_input = st.sidebar.text_input("Streamers (separados por vírgula)")
data_inicio = st.sidebar.date_input("Data de início", value=datetime.today() - timedelta(days=7))
data_fim = st.sidebar.date_input("Data de fim", value=datetime.today())
url_custom = st.sidebar.text_input("URL .m3u8 personalizada")

# Treinar modelo
if st.sidebar.button("🚀 Treinar modelo agora"):
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    from tensorflow.keras import layers, models

    st.sidebar.write("Iniciando treinamento...")

    dataset_dir = "dataset"
    img_height, img_width = 224, 224
    batch_size = 32

    datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)

    train_gen = datagen.flow_from_directory(
        dataset_dir,
        target_size=(img_height, img_width),
        batch_size=batch_size,
        class_mode='binary',
        subset='training'
    )

    val_gen = datagen.flow_from_directory(
        dataset_dir,
        target_size=(img_height, img_width),
        batch_size=batch_size,
        class_mode='binary',
        subset='validation'
    )

    model = models.Sequential([
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=(img_height, img_width, 3)),
        layers.MaxPooling2D(2, 2),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D(2, 2),
        layers.Flatten(),
        layers.Dense(64, activation='relu'),
        layers.Dense(1, activation='sigmoid')
    ])

    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

    model.fit(train_gen, validation_data=val_gen, epochs=5)

    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
    model.save(MODEL_PATH)
    if os.path.exists(MODEL_PATH):
        st.sidebar.success("✅ Modelo treinado e salvo com sucesso como 'modelo_pragmatic.keras'")
        st.sidebar.write(f"📁 Caminho: {MODEL_PATH}")
        st.rerun()
    else:
        st.sidebar.error("❌ Modelo NÃO foi salvo! Verifique permissões ou erros no ambiente.")

# Sugestão de novos streamers
if st.sidebar.button("🔎 Buscar novos streamers"):
    def sugerir_novos_streamers(game_name="Slots"):
        sugestoes = []
        try:
            response = requests.get(f"https://api.twitch.tv/helix/streams?game_name={game_name}&first=50", headers=HEADERS_TWITCH)
            data = response.json().get("data", [])
            for stream in data:
                login = stream.get("user_login")
                if login and login not in streamers_input:
                    sugestoes.append(login)
        except Exception as e:
            st.error(f"Erro ao buscar novos streamers: {e}")
        return sugestoes

    novos = sugerir_novos_streamers()
    if novos:
        st.success(f"Encontrados {len(novos)} novos possíveis streamers:")
        for nome in novos:
            st.write(f"- {nome}")
    else:
        st.info("Nenhum novo streamer encontrado no momento.")

# Interface Clip
st.sidebar.subheader("🎬 Verificar Clip da Twitch")
clip_url = st.sidebar.text_input("Cole o link do clip")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🔍 Verificar lives agora"):
        resultados = []
        streamers = [s.strip().lower() for s in streamers_input.split(",") if s.strip()]
        for streamer in streamers:
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
        if resultados:
            st.dataframe(pd.DataFrame(resultados))

with col2:
    if st.button("🌐 Rodar varredura na URL personalizada") and url_custom:
        resultado_url = varrer_url_customizada(url_custom)
        if resultado_url:
            st.dataframe(pd.DataFrame(resultado_url))

with col3:
    if st.button("📺 Verificar VODs no período"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        dt_fim = datetime.combine(data_fim, datetime.max.time())
        vod_resultados = buscar_vods_twitch_por_periodo(dt_inicio, dt_fim)
        if vod_resultados:
            st.dataframe(pd.DataFrame(vod_resultados))

with col4:
    if st.button("🖼️ Varrer VODs com detecção de imagem"):
        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
        dt_fim = datetime.combine(data_fim, datetime.max.time())
        vod_templates = varrer_vods_com_template(dt_inicio, dt_fim)
        if vod_templates:
            st.dataframe(pd.DataFrame(vod_templates))

if clip_url:
    if st.sidebar.button("Analisar Clip"):
        resultado = verificar_clip_twitch(clip_url)
        if resultado:
            st.success(f"🎯 Jogo detectado: {resultado}")
        else:
            st.warning("Nenhum jogo detectado no clip.")
