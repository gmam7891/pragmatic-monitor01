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

# (restante do código permanece igual)
