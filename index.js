const express = require('express');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const { google } = require('googleapis');
const fs = require('fs');
const path = require('path');

// =====================================================================
// CONFIGURACIÓN PERSONALIZADA DEL BOT
// =====================================================================
const GRUPO_NOMBRE = "MDP - COMPROMISO 3 2025"; 
const ID_CARPETA_ORIGEN = "1gw5gnpC6vrf24JWcJXl4VbdyC5WAiVjJ";     // Carpeta "Reportes_Hoy"
const ID_CARPETA_DESTINO = "12XmKunZ06nXTgePl5Wb5ZlOZ_2C3hdT7";   // Carpeta "Reportes_Enviados"

const HORA_INICIO = 19; // 7:00 PM
const HORA_FIN = 2;    // 2:00 AM
const INTERVALO_MEDIO_MINUTOS = 35;
// =====================================================================

const app = express();
const port = process.env.PORT || 10000;
let botStatus = "Iniciando...";
let qrCodeImage = null;

// Servidor Web para ver el QR
app.get('/', (req, res) => {
    res.send(`
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Panel Node WhatsApp Bot</title>
            <style>
                body { font-family: 'Segoe UI', sans-serif; background-color: #0b141a; color: white; text-align: center; padding: 50px; }
                .card { background-color: #111b21; padding: 40px; border-radius: 20px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.6); max-width: 500px; }
                h1 { color: #25D366; }
                .status { font-weight: bold; font-size: 1.2em; color: #34b7f1; margin: 20px 0; }
                img { border: 6px solid white; border-radius: 12px; background-color: white; margin-top: 15px; max-width: 250px; }
                .success { background-color: #005c4b; padding: 15px; border-radius: 10px; font-weight: bold; }
            </style>
            <script>setTimeout(() => { location.reload(); }, 5000);</script>
        </head>
        <body>
            <div class="card">
                <h1>🤖 Bot de Reportes (Versión Ligera)</h1>
                <p class="status">Estado: ${botStatus}</p>
                ${qrCodeImage ? `
                    <p>Escanea este código QR con tu WhatsApp:</p>
                    <img src="${qrCodeImage}" alt="QR Code">
                ` : `
                    <div class="success">
                        <p>✅ ¡Sesión lista o esperando activación de horario!</p>
                    </div>
                `}
            </div>
        </body>
        </html>
    `);
});

app.listen(port, () => console.log(`💻 Servidor web corriendo en puerto ${port}`));

// Inicializar WhatsApp Client
const client = new Client({
    authStrategy: new LocalAuth({ dataPath: '/tmp/wsp_auth' }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ],
        executablePath: '/usr/bin/chromium'
    }
});

client.on('qr', (qr) => {
    // Convertir el QR a imagen para mostrarlo en la web
    qrCodeImage = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(qr)}`;
    botStatus = "Esperando escaneo de código QR...";
    console.log('👉 QR Generado, listo para escanear en la web.');
});

client.on('ready', () => {
    qrCodeImage = null;
    botStatus = "Conectado a WhatsApp. Vigilando reportes...";
    console.log('✅ ¡Cliente de WhatsApp listo!');
    iniciarBucleBot();
});

client.on('auth_failure', (msg) => {
    botStatus = `Error de autenticación: ${msg}`;
    console.error(msg);
});

client.initialize();

// Conexión con Google Drive
let driveService = null;
if (fs.existsSync('credentials.json')) {
    const auth = new google.auth.GoogleAuth({
        keyFile: 'credentials.json',
        scopes: ['https://www.googleapis.com/auth/drive']
    });
    driveService = google.drive({ version: 'v3', auth });
    console.log('🔑 Credenciales de Google Drive cargadas con éxito.');
}

async function iniciarBucleBot() {
    while (true) {
        try {
            const ahora = new Date();
            const horaActual = ahora.getHours();
            const diaSemana = ahora.getDay(); // 0 es Domingo, 6 Sabado

            if (diaSemana === 0) {
                botStatus = "Domingo de descanso";
                await new Promise(r => setTimeout(r, 3600000));
                continue;
            }

            // Validar ventana de tiempo (7 PM a 2 AM)
            const dentroHorario = (horaActual >= HORA_INICIO || horaActual < HORA_FIN);
            if (!dentroHorario) {
                botStatus = "Fuera de horario (7 PM - 2 AM)";
                await new Promise(r => setTimeout(r, 900000)); // Esperar 15 min
                continue;
            }

            if (!driveService) {
                botStatus = "Error: Falta credentials.json en Render";
                await new Promise(r => setTimeout(r, 60000));
                continue;
            }

            botStatus = "Escaneando Google Drive...";
            const res = await driveService.files.list({
                q: `'${ID_CARPETA_ORIGEN}' in parents and mimeType contains 'image/' and trashed = false`,
                fields: 'files(id, name)',
                pageSize: 10
            });

            const files = res.data.files || [];
            if (files.length === 0) {
                botStatus = "Esperando reportes en Drive...";
                await new Promise(r => setTimeout(r, 300000)); // Esperar 5 min
                continue;
            }

            // Ordenar alfabéticamente por nombre
            files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
            const archivoEnTurno = files[0];

            botStatus = `Procesando envío: ${archivoEnTurno.name}`;
            
            // Descargar foto a memoria
            const driveRes = await driveService.files.get(
                { fileId: archivoEnTurno.id, alt: 'media' },
                { responseType: 'arraybuffer' }
            );
            
            const base64Data = Buffer.from(driveRes.data).toString('base64');
            const media = new MessageMedia('image/jpeg', base64Data, archivoEnTurno.name);

            // Buscar el grupo por nombre
            const chats = await client.getChats();
            const miGrupo = chats.find(chat => chat.name === GRUPO_NOMBRE);

            if (miGrupo) {
                // Enviar la foto limpia de forma nativa (Sin textos ni leyendas)
                await miGrupo.sendMessage(media);
                console.log(`📸 Foto ${archivoEnTurno.name} enviada con éxito al grupo.`);

                // Mover archivo a la carpeta de Enviados en Drive
                await driveService.files.update({
                    fileId: archivoEnTurno.id,
                    addParents: ID_CARPETA_DESTINO,
                    removeParents: ID_CARPETA_ORIGEN,
                    fields: 'id, parents'
                });
                console.log(`✅ Archivo archivado en Drive.`);
            } else {
                console.error(`❌ No encontré ningún grupo llamado "${GRUPO_NOMBRE}"`);
                botStatus = `Error: No se halló el grupo en tu WhatsApp`;
                await new Promise(r => setTimeout(r, 60000));
                continue;
            }

            // Tiempo de espera aleatorio entre envíos
            const variacion = Math.floor(Math.random() * 11) - 5; // -5 a +5
            const minutosEspera = Math.max(5, INTERVALO_MEDIO_MINUTOS + variacion);
            botStatus = `En espera por ${minutosEspera} min...`;
            await new Promise(r => setTimeout(r, minutosEspera * 60 * 1000));

        } catch (error) {
            console.error('Error en el bucle del bot:', error);
            botStatus = "Error en proceso. Reintentando en 5 min...";
            await new Promise(r => setTimeout(r, 300000));
        }
    }
}
