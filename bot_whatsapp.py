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
from webdriver_manager.chrome import ChromeDriverManager

# =====================================================================
# CONFIGURACIÓN PERSONALIZADA DEL BOT
# =====================================================================
# 1. ID de tu grupo de WhatsApp (obtenlo del enlace de invitación)
GRUPO_ID = "TU_ID_DE_GRUPO_O_ENLACE"     

# 2. IDs de tus carpetas de Google Drive (búscalos en la URL de tu navegador)
ID_CARPETA_DRIVE_ORIGEN = "ID_CARPETA_ORIGEN"    # Carpeta donde subes las fotos
ID_CARPETA_DRIVE_DESTINO = "ID_CARPETA_DESTINO"  # Carpeta donde el bot guardará las enviadas

# 3. Horarios y tiempos de envío
HORA_INICIO = 19                         # Empieza a las 7:00 PM (hora militar)
HORA_FIN = 1                             # Termina a las 1:00 AM del día siguiente
INTERVALO_MEDIO = 35                     # Espera promedio de 35 minutos entre fotos
# =====================================================================

CARPETA_TEMPORAL = "temp_fotos"
os.makedirs(CARPETA_TEMPORAL, exist_ok=True)

app = Flask(__name__)
QR_PATH = "qr_session.png"
BOT_STATUS = "Iniciando..."

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
    """Sirve la imagen del código QR"""
    if os.path.exists(QR_PATH):
        return send_file(QR_PATH, mimetype='image/png')
    return "No hay QR activo en este momento.", 404


# =====================================================================
# PROCESOS EN SEGUNDO PLANO
# =====================================================================
def iniciar_controlador_chrome():
    """Configura e inicia Chrome Headless compatible con la nube (Docker en Render)"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # Ejecución invisible
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--user-data-dir=./wsp_user_session') # Guarda la sesión para evitar escanear siempre
    options.add_argument('--window-size=1280,800')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # Rutas automáticas para el entorno de Render (Docker)
    chrome_bin = os.environ.get('CHROME_BIN')
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
    if chromedriver_path:
        service = Service(chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def descargar_fotos_de_google_drive(creds):
    """Descarga las fotos de tu Google Drive en orden alfabético estricto"""
    try:
        service = build('drive', 'v3', credentials=creds)
        query = f"'{ID_CARPETA_DRIVE_ORIGEN}' in parents and mimeType contains 'image/' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        # Regla 1: Ordenar estrictamente por orden alfabético
        files.sort(key=lambda x: x['name'].lower())
        
        descargadas = []
        for file in files:
            file_id = file['id']
            file_name = file['name']
            ruta_local = os.path.join(CARPETA_TEMPORAL, file_name)
            
            # Descargar archivo físico al almacenamiento temporal del bot
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
    """Regla 3: Mueve la foto enviada a la carpeta 'Reportes_Enviados' en tu Drive"""
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
        print(f"✅ Archivo '{file_name}' archivado con éxito en Google Drive.")
    except Exception as e:
        print(f"❌ Error al mover archivo en Google Drive: {e}")

def enviar_foto_por_whatsapp(driver, ruta_foto):
    """Regla 2: Envía solo la foto limpia (sin textos) en WhatsApp Web"""
    url_chat = f"https://web.whatsapp.com/accept?code={GRUPO_ID}" if len(GRUPO_ID) > 15 else f"https://web.whatsapp.com/send?phone={GRUPO_ID}"
    driver.get(url_chat)
    
    wait = WebDriverWait(driver, 40)
    
    # 1. Esperar y dar clic al botón de adjuntar (+)
    btn_adjuntar = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@title="Adjuntar"] | //span[@data-icon="plus"]')))
    btn_adjuntar.click()
    time.sleep(1)
    
    # 2. Seleccionar el campo de archivo invisible e inyectar la foto
    input_archivo = driver.find_element(By.XPATH, '//input[@type="file"]')
    input_archivo.send_keys(os.path.abspath(ruta_foto))
    time.sleep(3)
    
    # 3. Dar clic al botón de enviar (sin escribir nada en la caja de texto)
    btn_enviar = wait.until(EC.presence_of_element_located((By.XPATH, '//span[@data-icon="send"] | //div[@aria-label="Enviar"]')))
    btn_enviar.click()
    time.sleep(5) # Margen de espera para asegurar que la subida finalice

def bucle_principal_bot():
    """El motor principal del robot que vigila los horarios y envía los reportes"""
    global BOT_STATUS
    driver = None
    
    # Autenticación segura con Google Drive (usando tu credentials.json privado)
    creds = None
    if os.path.exists("credentials.json"):
        creds = service_account.Credentials.from_service_account_file(
            "credentials.json", 
            scopes=['https://www.googleapis.com/auth/drive']
        )
    else:
        print("⚠️ credentials.json ausente. Google Drive no podrá conectarse.")
        BOT_STATUS = "Falta credentials.json"
    
    print("🚀 Iniciando navegador en segundo plano...")
    BOT_STATUS = "Iniciando navegador..."
    driver = iniciar_controlador_chrome()
    driver.get("https://web.whatsapp.com")
    
    # Monitoreo de QR y de Inicio de Sesión
    while True:
        try:
            # Si vemos el buscador de chats es porque ya estamos adentro
            driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            BOT_STATUS = "Conectado. Esperando horario activo..."
            if os.path.exists(QR_PATH):
                os.remove(QR_PATH)
            break
        except:
            # Si no, tomamos captura al QR para que lo escanees desde la web
            try:
                qr_canvas = driver.find_element(By.XPATH, '//canvas[@role="img"]')
                qr_canvas.screenshot(QR_PATH)
                BOT_STATUS = "Esperando escaneo de código QR..."
            except:
                BOT_STATUS = "Cargando WhatsApp Web..."
            time.sleep(3)

    # Bucle eterno de envíos diarios
    while True:
        ahora = datetime.now()
        hora_actual = ahora.hour
        dia_semana = ahora.weekday() # Lunes = 0, Sábado = 5, Domingo = 6

        # Regla 5: Trabajar de Lunes a Sábado (El Domingo no hace nada)
        if dia_semana == 6:
            print("Hoy es Domingo. El bot descansará hoy...")
            BOT_STATUS = "Domingo de descanso"
            time.sleep(3600)
            continue

        # Regla del horario: Solo activo de 7:00 PM a 1:00 AM
        if hora_actual >= HORA_FIN and hora_actual < HORA_INICIO:
            print("Fuera de horario activo (7 PM - 1 AM). Esperando...")
            BOT_STATUS = "Fuera de horario (7 PM - 1 AM)"
            time.sleep(900)
            continue

        if not creds:
            print("Esperando a que subas tus credenciales de Google Drive...")
            time.sleep(300)
            continue

        # Limpiar residuos anteriores
        if os.path.exists(CARPETA_TEMPORAL):
            shutil.rmtree(CARPETA_TEMPORAL)
        os.makedirs(CARPETA_TEMPORAL, exist_ok=True)
        
        print("🔎 Escaneando Google Drive para enviar reportes...")
        BOT_STATUS = "Escaneando Google Drive..."
        reportes = descargar_fotos_de_google_drive(creds)

        if not reportes:
            print("Sin reportes listos en Google Drive. Reintentando en 5 minutos...")
            BOT_STATUS = "Esperando reportes en Drive..."
            time.sleep(300)
            continue

        # Procesar la foto más antigua de la lista en orden alfabético
        reporte_actual = reportes[0]
        print(f"Preparando envío de: {reporte_actual['name']}")
        BOT_STATUS = f"Enviando: {reporte_actual['name']}"

        try:
            # Enviar foto limpia por WhatsApp Web
            enviar_foto_por_whatsapp(driver, reporte_actual['path'])
            print(f"✅ ¡Reporte '{reporte_actual['name']}' enviado!")
            
            # Mover la foto a "Enviados" en tu Google Drive
            mover_archivo_en_drive(creds, reporte_actual['id'], reporte_actual['name'])
            
        except Exception as e:
            # Regla 4: Reintentar a los 5 minutos en caso de fallo
            print(f"❌ Error de envío: {e}. Reintentando en 5 minutos...")
            BOT_STATUS = "Error de envío. Reintentando en 5 min..."
            time.sleep(300)
            continue

        # Espera de ~35 minutos (+-5 minutos aleatorios para simular comportamiento humano)
        variacion = random.randint(-5, 5)
        espera_minutos = max(5, INTERVALO_MEDIO + variacion)
        print(f"Esperando {espera_minutos} minutos de forma aleatoria para simular acción humana...")
        BOT_STATUS = f"En espera por {espera_minutos} min..."
        time.sleep(espera_minutos * 60)

# Lanzar el proceso de automatización en un hilo secundario para no bloquear a Flask
thread = threading.Thread(target=bucle_principal_bot)
thread.daemon = True
thread.start()

if __name__ == '__main__':
    # El bot corre en el puerto 10000, estándar para Render
    app.run(host='0.0.0.0', port=10000)
