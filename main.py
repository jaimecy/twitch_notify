import os
import json
import logging
import asyncio
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# Configura el log
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DATA_FILE = "data.json"
CHECK_INTERVAL = 60  # segundos

# Carga datos desde el archivo JSON
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

# Guarda datos en el archivo JSON
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Llama a la API de Twitch para obtener información del stream
async def get_stream_data(session, client_id, token, channel):
    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}"
    }
    url = f"https://api.twitch.tv/helix/streams?user_login={channel}"
    try:
        response = await session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["data"]:
            return data["data"][0]
    except Exception as e:
        logging.error(f"Error consultando canal {channel}: {e}")
    return None

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenido. Usa /add [canal] para añadir un canal de Twitch.\n"
        "Usa /list para ver tus canales.\n"
        "Usa /remove [canal] para eliminar uno.\n"
        "Ejemplo: /add auronplay"
    )

# Comando /add canal
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usa /add nombre_canal")
        return

    channel = context.args[0].lower()
    user_id = str(update.effective_chat.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = []

    if channel not in data[user_id]:
        data[user_id].append(channel)
        save_data(data)
        await update.message.reply_text(f"✅ Canal añadido: {channel}")
    else:
        await update.message.reply_text("⚠️ Ya estás siguiendo ese canal.")

# Comando /remove canal
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usa /remove nombre_canal")
        return

    channel = context.args[0].lower()
    user_id = str(update.effective_chat.id)
    data = load_data()

    if user_id in data and channel in data[user_id]:
        data[user_id].remove(channel)
        save_data(data)
        await update.message.reply_text(f"🗑️ Canal eliminado: {channel}")
    else:
        await update.message.reply_text("⚠️ No estás siguiendo ese canal.")

# Comando /list
async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    data = load_data()
    channels = data.get(user_id, [])
    if channels:
        text = "📺 Canales que estás siguiendo:\n" + "\n".join(f"* - {c}" for c in channels)
    else:
        text = "❗ No estás siguiendo ningún canal.\nUsa /add canal para empezar."
    await update.message.reply_text(text)

# Verifica si hay directos nuevos
async def check_streams(app):
    data = load_data()
    live_status = {}

    twitch_id = os.getenv("TWITCH_CLIENT_ID")
    twitch_secret = os.getenv("TWITCH_CLIENT_SECRET")

    async with httpx.AsyncClient() as client:
        auth_resp = await client.post(
            f"https://id.twitch.tv/oauth2/token",
            params={
                "client_id": twitch_id,
                "client_secret": twitch_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        access_token = auth_resp.json().get("access_token")
        if not access_token:
            logging.error("No se pudo obtener el token de acceso.")
            return

        while True:
            for user_id, channels in data.items():
                for channel in channels:
                    stream = await get_stream_data(client, twitch_id, access_token, channel)
                    key = f"{user_id}:{channel}"
                    if stream and not live_status.get(key):
                        live_status[key] = True
                        title = stream["title"]
                        await app.bot.send_message(
                            chat_id=int(user_id),
                            text=f"🔴 ¡{channel} está en directo!\n🎮 {title}\nhttps://twitch.tv/{channel}"
                        )
                    elif not stream:
                        live_status[key] = False
            await asyncio.sleep(CHECK_INTERVAL)

# Función principal
async def main():
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_channel))
    app.add_handler(CommandHandler("remove", remove_channel))
    app.add_handler(CommandHandler("list", list_channels))

    # Inicia la verificación de streams en segundo plano
    asyncio.create_task(check_streams(app))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
