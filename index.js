const express = require('express');
const axios = require('axios');
const { google } = require('googleapis');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 10000;

// TUS DATOS DE CALLMEBOT
const WSP_USER = "TU_NUMERO_CON_CODIGO_PAIS"; 
const WSP_API_KEY = "TU_API_KEY_AQUI";

const drive = google.drive({ version: 'v3', auth: new google.auth.GoogleAuth({
    keyFile: 'credentials.json',
    scopes: ['https://www.googleapis.com/auth/drive']
})});

async function enviarWhatsApp(fotoUrl) {
    const url = `https://api.callmebot.com/whatsapp.php?phone=${WSP_USER}&text=Nuevo+reporte+disponible:+${encodeURIComponent(fotoUrl)}&apikey=${WSP_API_KEY}`;
    await axios.get(url);
}

app.get('/', (req, res) => res.send("Bot de API Activo y Ligero"));
app.listen(PORT);

// Bucle simple sin Chrome
setInterval(async () => {
    try {
        const res = await drive.files.list({ q: `'ID_CARPETA_ORIGEN' in parents`, fields: 'files(id, name, webContentLink)' });
        if (res.data.files.length > 0) {
            const archivo = res.data.files[0];
            await enviarWhatsApp(archivo.webContentLink);
            // Mover archivo (logic similar a la anterior)
            console.log("Reporte enviado por API");
        }
    } catch (e) { console.error(e); }
}, 600000); // Revisa cada 10 min
