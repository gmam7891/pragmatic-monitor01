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

# (continua... o restante do código foi omitido aqui por espaço)
