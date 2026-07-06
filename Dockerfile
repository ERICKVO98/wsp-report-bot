FROM python:3.10-slim

# Instalar Google Chrome (Chromium) y dependencias de sistema para que Selenium funcione en Render
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    chromium \
    chromium-driver \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Definir variables de entorno de sistema para que Selenium encuentre Chrome sin fallar
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# =====================================================================
# TRUCO MAESTRO: Forzar a Chromium y a su manejador de caídas (Crashpad)
# a usar carpetas temporales de escritura libre en Render
# =====================================================================
ENV XDG_CONFIG_HOME=/tmp/.chromium
ENV XDG_CACHE_HOME=/tmp/.chromium

WORKDIR /app

# Instalar requerimientos de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del bot
COPY . .

# Exponer el puerto de Render
EXPOSE 10000

# Arrancar el script
CMD ["python", "bot_whatsapp.py"]
