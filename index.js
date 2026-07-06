const express = require('express');
const axios = require('axios');
const { google } = require('googleapis');

const app = express();
const PORT = process.env.PORT || 10000;

// CONFIGURACIÓN: Rellena estos dos datos con los que te dio CallMeBot
const WSP_USER = "51907916500"; 
const WSP_API_KEY = "6357921";

// IDs DE TUS CARPETAS
const ID_CARPETA_ORIGEN = "1gw5gnpC6vrf24JWcJXl4VbdyC5WAiVjJ";
const ID_CARPETA_DESTINO = "12XmKunZ06nXTgePl5Wb5ZlOZ_2C3hdT7";

const drive = google.drive({ version: 'v3', auth: new google.auth.GoogleAuth({
    keyFile: 'credentials.json',
    scopes: ['https://www.googleapis.com/auth/drive']
})});

async function enviarWhatsApp(archivoNombre, fotoUrl) {
    const mensaje = `Nuevo reporte listo: ${archivoNombre}. Puedes verlo aquí: ${fotoUrl}`;
    const url = `https://api.callmebot.com/whatsapp.php?phone=${WSP_USER}&text=${encodeURIComponent(mensaje)}&apikey=${WSP_API_KEY}`;
    await axios.get(url);
}

app.get('/', (req, res) => res.send("Bot de API Activo. Estado: OK."));
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
            console.log(`Encontrado: ${archivo.name}. Enviando...`);
            
            await enviarWhatsApp(archivo.name, archivo.webContentLink);
            
            // Mover archivo a la carpeta de destino
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
