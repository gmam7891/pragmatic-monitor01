# MVP de Monitoramento de Jogos da Pragmatic Play na Twitch com Dashboard Streamlit + Alertas

from datetime import datetime
import requests
import sqlite3
import streamlit as st
import pandas as pd
import pytz
import schedule
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ------------------------------
# CONFIGURAÇÕES INICIAIS
# ------------------------------
CLIENT_ID = 'SUA_CLIENT_ID_AQUI'
ACCESS_TOKEN = 'SEU_ACCESS_TOKEN_AQUI'
EMAIL_ALERTA = 'seuemail@gmail.com'  # substitua por seu e-mail
SENHA_EMAIL = 'sua_senha_de_aplicativo'  # use uma senha de app
EMAIL_DESTINO = 'destino@gmail.com'  # e-mail que receberá os alertas

HEADERS = {
    'Client-ID': CLIENT_ID,
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
BASE_URL = 'https://api.twitch.tv/helix/'
PRAGMATIC_KEYWORDS = [
    'Sweet Bonanza',
    'Gates of Olympus',
    'Sugar Rush',
    'Starlight Princess',
    'Big Bass Bonanza'
]

# ------------------------------
# FUNÇÕES DE COLETA DE DADOS
# ------------------------------
def buscar_lives_slots():
    url = BASE_URL + 'streams?game_id=509577&first=100'  # Categoria "Slots"
    response = requests.get(url, headers=HEADERS)
    return response.json().get('data', [])

def filtrar_lives_pragmatic(lives):
    pragmatic_lives = []
    for live in lives:
        title = live['title'].lower()
        for keyword in PRAGMATIC_KEYWORDS:
            if keyword.lower() in title:
                started_at = datetime.strptime(live['started_at'], "%Y-%m-%dT%H:%M:%SZ")
                started_at = started_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("America/Sao_Paulo"))
                pragmatic_lives.append({
                    'streamer': live['user_name'],
                    'title': live['title'],
                    'viewer_count': live['viewer_count'],
                    'started_at': started_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'game': keyword
                })
    return pragmatic_lives

def salvar_no_banco(dados):
    conn = sqlite3.connect('pragmatic_lives.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS lives (
        streamer TEXT,
        title TEXT,
        viewer_count INTEGER,
        started_at TEXT,
        game TEXT
    )''')
    for d in dados:
        cursor.execute('INSERT INTO lives VALUES (?, ?, ?, ?, ?)', (
            d['streamer'], d['title'], d['viewer_count'], d['started_at'], d['game']
        ))
    conn.commit()
    conn.close()

def carregar_dados():
    conn = sqlite3.connect('pragmatic_lives.db')
    df = pd.read_sql_query("SELECT * FROM lives", conn)
    conn.close()
    return df

def exportar_csv(df):
    df.to_csv("dados_pragmatic.csv", index=False)
    st.success("Arquivo CSV exportado com sucesso!")

# ------------------------------
# ALERTA POR EMAIL
# ------------------------------
def enviar_alerta_email(dados):
    if not dados:
        return
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ALERTA
    msg['To'] = EMAIL_DESTINO
    msg['Subject'] = '🚨 Streamers jogando Pragmatic Play AGORA'

    corpo = 'Novas transmissões encontradas:\n\n'
    for d in dados:
        corpo += f"Streamer: {d['streamer']}\nJogo: {d['game']}\nTítulo: {d['title']}\nViewers: {d['viewer_count']}\nInício: {d['started_at']}\n\n"

    msg.attach(MIMEText(corpo, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ALERTA, SENHA_EMAIL)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Erro ao enviar alerta de e-mail:", e)

# ------------------------------
# AGENDAMENTO AUTOMÁTICO
# ------------------------------
def rotina_agendada():
    lives = buscar_lives_slots()
    pragmatic_lives = filtrar_lives_pragmatic(lives)
    salvar_no_banco(pragmatic_lives)
    enviar_alerta_email(pragmatic_lives)

def iniciar_agendamento():
    schedule.every(1).hours.do(rotina_agendada)
    while True:
        schedule.run_pending()
        time.sleep(1)

agendador = threading.Thread(target=iniciar_agendamento, daemon=True)
agendador.start()

# ------------------------------
# DASHBOARD COM STREAMLIT
# ------------------------------
st.set_page_config(page_title="Pragmatic Play - Live Tracker", layout="wide")
st.title("🎰 Monitor de Jogos da Pragmatic Play na Twitch")

col1, col2 = st.columns(2)
if col1.button("🔍 Buscar novas lives agora"):
    rotina_agendada()
    st.success(f"Nova coleta realizada com sucesso.")

# Exibe os dados salvos no banco
df = carregar_dados()

st.subheader("📊 Tabela de Transmissões Registradas")
st.dataframe(df.sort_values(by="started_at", ascending=False), use_container_width=True)

# Exportação CSV
if st.button("📁 Exportar dados para CSV"):
    exportar_csv(df)

# Estatísticas
st.subheader("📈 Estatísticas Rápidas")
col1, col2, col3 = st.columns(3)
col1.metric("Streamers únicos", df["streamer"].nunique())
col2.metric("Total de lives", len(df))
col3.metric("Jogos monitorados", df["game"].nunique())

# Ranking de streamers
st.subheader("🏆 Ranking de Streamers por Visualizações Totais")
ranking_streamers = df.groupby('streamer')['viewer_count'].sum().sort_values(ascending=False).reset_index()
st.table(ranking_streamers)

# Gráfico por jogo
st.subheader("🎮 Distribuição por Jogo")
jogo_counts = df['game'].value_counts()
st.bar_chart(jogo_counts)

# Gráfico por visualizações totais por jogo
st.subheader("👀 Visualizações Totais por Jogo")
views_por_jogo = df.groupby('game')['viewer_count'].sum().sort_values(ascending=False)
st.bar_chart(views_por_jogo)

# Filtro por streamer
st.subheader("🔎 Filtrar por Streamer")
streamers = df['streamer'].unique()
streamer_selecionado = st.selectbox("Escolha um streamer", options=streamers)
df_filtrado = df[df['streamer'] == streamer_selecionado]
st.write(df_filtrado.sort_values(by="started_at", ascending=False))
