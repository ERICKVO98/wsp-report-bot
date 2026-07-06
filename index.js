const express = require('express');
const axios = require('axios');
const { google } = require('googleapis');

const app = express();
const PORT = process.env.PORT || 10000;

// --- CONFIGURACIÓN ---
// 1. Pon tu número de teléfono con código de país (ej: 51912345678)
const WSP_USER = "51907916500"; 
// 2. Pon la API Key que te dio CallMeBot por WhatsApp
const WSP_API_KEY = "6357921";
// 3. Escribe AQUÍ el nombre exacto de tu grupo (tal cual aparece en WhatsApp)
const NOMBRE_GRUPO = "MDP - COMPROMISO 3 2025";

// IDs DE TUS CARPETAS DE DRIVE
const ID_CARPETA_ORIGEN = "1gw5gnpC6vrf24JWcJXl4VbdyC5WAiVjJ";
const ID_CARPETA_DESTINO = "12XmKunZ06nXTgePl5Wb5ZlOZ_2C3hdT7";

const drive = google.drive({ version: 'v3', auth: new google.auth.GoogleAuth({
    keyFile: 'credentials.json',
    scopes: ['https://www.googleapis.com/auth/drive']
})});

async function enviarWhatsApp(archivoNombre, fotoUrl) {
    // Usamos el parámetro 'group' para enviar al grupo
    const grupoCodificado = encodeURIComponent(NOMBRE_GRUPO);
    const mensaje = `Nuevo reporte: ${archivoNombre}. Ver aquí: ${fotoUrl}`;
    
    // CallMeBot enviará este mensaje al grupo
    const url = `https://api.callmebot.com/whatsapp.php?group=${grupoCodificado}&text=${encodeURIComponent(mensaje)}&apikey=${WSP_API_KEY}`;
    await axios.get(url);
}

app.get('/', (req, res) => res.send("Bot de API Activo. Todo OK."));
app.listen(PORT, () => console.log(`Bot corriendo en puerto ${PORT}`));

// Bucle principal (Revisa cada 10 minutos)
setInterval(async () => {
    try {
        console.log("Escaneando carpeta de origen...");
        const res = await drive.files.list({
            q: `'${ID_CARPETA_ORIGEN}' in parents and mimeType contains 'image/' and trashed = false`,
            fields: 'files(id, name, webContentLink)'
        });

        const archivos = res.data.files || [];
        if (archivos.length > 0) {
            const archivo = archivos[0];
            console.log(`Encontrado: ${archivo.name}. Enviando al grupo...`);
            
            await enviarWhatsApp(archivo.name, archivo.webContentLink);
            
            // Mover archivo a la carpeta de destino para no enviarlo dos veces
            await drive.files.update({
                fileId: archivo.id,
                addParents: ID_CARPETA_DESTINO,
                removeParents: ID_CARPETA_ORIGEN,
                fields: 'id, parents'
            });
            console.log("Archivo movido con éxito.");
        }
    } catch (e) { 
        console.error("Error en el bucle:", e.message); 
    }
}, 600000);
