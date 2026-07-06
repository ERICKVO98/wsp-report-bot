# -*- coding: utf-8 -*-
import os
import time
import random
import shutil
import threading
from datetime import datetime
from flask import Flask, send_file, render_template_string

# Librerías para conectar con la API de Google Drive
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

# Librerías de Selenium para controlar WhatsApp Web en la nube
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# =====================================================================
# CONFIGURACIÓN PERSONALIZADA DEL BOT
# =====================================================================
# 1. ESCRIBE EL NOMBRE EXACTO DE TU GRUPO ENTRE LAS COMILLAS (Tal cual se lee en tu celular)
GRUPO_ID = "MDP - COMPROMISO 3 2025"     

# 2. IDs de tus carpetas de Google Drive (los que ya conseguiste)
ID_CARPETA_DRIVE_ORIGEN = "1gw5gnpC6vrf24JWcJXl4VbdyC5WAiVjJ"    # Carpeta "Reportes_Hoy"
ID_CARPETA_DRIVE_DESTINO = "12XmKunZ06nXTgePl5Wb5ZlOZ_2C3hdT7"  # Carpeta "Reportes_Enviados"

# 3. Horarios y tiempos de envío
HORA_INICIO = 19                         # Empieza a las 7:00 PM (hora militar)
HORA_FIN = 2                             # Termina a las 2:00 AM del día siguiente (Actualizado 🚀)
INTERVALO_MEDIO = 35                     # Espera promedio de 35 minutos entre fotos
# =====================================================================

CARPETA_TEMPORAL = "temp_fotos"
os.makedirs(CARPETA_TEMPORAL, exist_ok=True)

app = Flask(__name__)
QR_PATH = "qr_session.png"
BOT_STATUS = "Iniciando..."
global_driver = None  

@app.route('/')
def home():
    """Página de control web para escanear el código QR desde tu celular"""
    html_template = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Panel de WhatsApp Cloud Bot</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0b141a; color: white; text-align: center; padding: 50px; }
            .card { background-color: #111b21; padding: 40px; border-radius: 20px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.6); max-width: 500px; }
            h1 { color: #25D366; margin-bottom: 10px; }
            .status { font-weight: bold; margin: 20px 0; font-size: 1.25em; color: #34b7f1; }
            img { border: 6px solid white; border-radius: 12px; max-width: 280px; margin-top: 20px; background-color: white; }
            .footer { margin-top: 30px; font-size: 0.85em; color: #8696a0; }
            .btn-debug { background-color: #202c33; color: #00a884; border: 1px solid #00a884; padding: 8px 15px; border-radius: 8px; text-decoration: none; display: inline-block; margin-top: 15px; font-size: 0.9em; font-weight: bold; }
            .btn-debug:hover { background-color: #00a884; color: white; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🤖 Bot de Reportes de WhatsApp</h1>
            <p>Control de sesión en la nube</p>
            <p class="status">Estado: <span>{{ status }}</span></p>
            
            {% if qr_exists %}
                <p>Abre WhatsApp en tu celular -> Dispositivos vinculados -> Vincular un dispositivo y escanea este código QR:</p>
                <img src="/qr" alt="Código QR de WhatsApp">
            {% else %}
                <div style="background-color: #005c4b; padding: 15px; border-radius: 10px; margin-top: 20px;">
                    <p style="margin: 0; font-size: 1.2em; font-weight: bold;">✅ ¡Sesión Activa!</p>
                    <p style="margin: 5px 0 0 0; font-size: 0.9em;">El bot ya está conectado a tu WhatsApp y enviará los reportes programados.</p>
                </div>
            {% endif %}
            <br>
            <a href="/screenshot" target="_blank" class="btn-debug">📷 Ver Pantalla del Navegador (Soporte)</a>
            <div class="footer">La página se actualizará automáticamente cada 5 segundos.</div>
        </div>
        <script>
            setTimeout(function(){ location.reload(); }, 5000);
        </script>
    </body>
    </html>
    """
    qr_exists = os.path.exists(QR_PATH)
    return render_template_string(html_template, status=BOT_STATUS, qr_exists=qr_exists)

@app.route('/qr')
def get_qr():
    if os.path.exists(QR_PATH):
        return send_file(QR_PATH, mimetype='image/png')
    return "No hay QR activo en este momento.", 404

@app.route('/screenshot')
def get_screenshot():
    global global_driver
    if global_driver:
        try:
            global_driver.save_screenshot("live_view.png")
            return send_file("live_view.png", mimetype='image/png')
        except Exception as e:
            return f"No se pudo tomar la captura: {e}", 500
    return "El navegador no ha iniciado.", 404


# =====================================================================
# MOTOR DE AUTOMATIZACIÓN
# =====================================================================
def iniciar_controlador_chrome():
    global global_driver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--user-data-dir=./wsp_user_session') 
    options.add_argument('--window-size=1280,800')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
    if chromedriver_path:
        service = Service(chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=options)
    global_driver = driver
    return driver

def descargar_fotos_de_google_drive(creds):
    try:
        service = build('drive', 'v3', credentials=creds)
        query = f"'{ID_CARPETA_DRIVE_ORIGEN}' in parents and mimeType contains 'image/' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        files.sort(key=lambda x: x['name'].lower())
        
        descargadas = []
        for file in files:
            file_id = file['id']
            file_name = file['name']
            ruta_local = os.path.join(CARPETA_TEMPORAL, file_name)
            
            request = service.files().get_media(fileId=file_id)
            with open(ruta_local, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            descargadas.append({"id": file_id, "name": file_name, "path": ruta_local})
        
        return descargadas
    except Exception as e:
        print(f"❌ Error al conectar con Google Drive: {e}")
        return []

def mover_archivo_en_drive(creds, file_id, file_name):
    try:
        service = build('drive', 'v3', credentials=creds)
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        service.files().update(
            fileId=file_id,
            removeParents=previous_parents,
            addParents=ID_CARPETA_DRIVE_DESTINO,
            fields='id, parents'
        ).execute()
        print(f"✅ Archivo '{file_name}' archivado en Google Drive.")
    except Exception as e:
        print(f"❌ Error al mover archivo en Google Drive: {e}")

def enviar_foto_por_whatsapp(driver, ruta_foto):
    """Regla 2: Busca el grupo por su nombre y envía la foto limpia (sin textos)"""
    if driver.current_url != "https://web.whatsapp.com/":
        driver.get("https://web.whatsapp.com")
    
    wait = WebDriverWait(driver, 45)
    
    # 1. Buscar la caja de búsqueda de chats de WhatsApp
    caja_busqueda = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')))
    caja_busqueda.click()
    time.sleep(1)
    
    # Limpiar el buscador e inyectar el nombre exacto del grupo
    caja_busqueda.send_keys(Keys.CONTROL + "a")
    caja_busqueda.send_keys(Keys.DELETE)
    caja_busqueda.send_keys(GRUPO_ID)
    time.sleep(2)
    
    # Presionar Enter para abrir el chat del grupo
    caja_busqueda.send_keys(Keys.ENTER)
    time.sleep(2)
    
    # 2. Esperar y dar clic al botón de adjuntar (+)
    btn_adjuntar = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@title="Adjuntar"] | //span[@data-icon="plus"]')))
    btn_adjuntar.click()
    time.sleep(1.5)
    
    # 3. Seleccionar el campo de archivo invisible e inyectar la foto
    input_archivo = driver.find_element(By.XPATH, '//input[@type="file"]')
    input_archivo.send_keys(os.path.abspath(ruta_foto))
    time.sleep(3)
    
    # 4. Dar clic al botón de enviar (sin escribir nada en la caja de texto)
    btn_enviar = wait.until(EC.presence_of_element_located((By.XPATH, '//span[@data-icon="send"] | //div[@aria-label="Enviar"]')))
    btn_enviar.click()
    time.sleep(6) 

def bucle_principal_bot():
    """El motor principal del robot que vigila los horarios y envía los reportes"""
    global BOT_STATUS
    driver = None
    
    creds = None
    if os.path.exists("credentials.json"):
        creds = service_account.Credentials.from_service_account_file(
            "credentials.json", 
            scopes=['https://www.googleapis.com/auth/drive']
        )
    else:
        print("⚠️ credentials.json ausente.")
        BOT_STATUS = "Falta credentials.json"
    
    print("🚀 Iniciando navegador en segundo plano...")
    BOT_STATUS = "Iniciando navegador..."
    driver = iniciar_controlador_chrome()
    driver.get("https://web.whatsapp.com")
    
    while True:
        try:
            driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            BOT_STATUS = "Conectado. Esperando horario activo..."
            if os.path.exists(QR_PATH):
                os.remove(QR_PATH)
            break
        except:
            try:
                qr_canvas = driver.find_element(By.XPATH, '//canvas[@role="img"]')
                qr_canvas.screenshot(QR_PATH)
                BOT_STATUS = "Esperando escaneo de código QR..."
            except:
                try:
                    driver.save_screenshot(QR_PATH)
                    BOT_STATUS = "Esperando QR (Captura completa)..."
                except:
                    BOT_STATUS = "Cargando WhatsApp Web..."
            time.sleep(4)

    while True:
        ahora = datetime.now()
        hora_actual = ahora.hour
        dia_semana = ahora.weekday() 

        if dia_semana == 6:
            BOT_STATUS = "Domingo de descanso"
            time.sleep(3600)
            continue

        # Ventana de horario inactivo (Entre las 2:00 AM y las 7:00 PM)
        if HORA_FIN <= hora_actual < HORA_INICIO:
            BOT_STATUS = "Fuera de horario (7 PM - 2 AM)"
            time.sleep(900)
            continue

        if not creds:
            time.sleep(300)
            continue

        if os.path.exists(CARPETA_TEMPORAL):
            shutil.rmtree(CARPETA_TEMPORAL)
        os.makedirs(CARPETA_TEMPORAL, exist_ok=True)
        
        BOT_STATUS = "Escaneando Google Drive..."
        reportes = descargar_fotos_de_google_drive(creds)

        if not reportes:
            BOT_STATUS = "Esperando reportes en Drive..."
            time.sleep(300)
            continue

        reporte_actual = reportes[0]
        BOT_STATUS = f"Enviando: {reporte_actual['name']}"

        try:
            enviar_foto_por_whatsapp(driver, reporte_actual['path'])
            mover_archivo_en_drive(creds, reporte_actual['id'], reporte_actual['name'])
            
        except Exception as e:
            BOT_STATUS = "Error de envío. Reintentando en 5 min..."
            time.sleep(300)
            continue

        variacion = random.randint(-5, 5)
        espera_minutos = max(5, INTERVALO_MEDIO + variacion)
        BOT_STATUS = f"En espera por {espera_minutos} min..."
        time.sleep(espera_minutos * 60)

thread = threading.Thread(target=bucle_principal_bot)
thread.daemon = True
thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
