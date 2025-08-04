import os
import json
import requests
import threading
import time
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("8196163951:AAEgMDURdYS3cQDM9mu8Gdzp6gL7vdl0MFg")
TWITCH_CLIENT_ID = os.getenv("tmm98rywp6vdwles6gtlbbe4iit5sv")
TWITCH_CLIENT_SECRET = os.getenv("q18ju74j3d5lqsrnn29okk1pwyh87q")

DATA_FILE = "data.json"
CHECK_INTERVAL = 60  # segundos
STREAM_STATUS = {}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_twitch_token():
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    r = requests.post(url, params=params)
    return r.json().get("access_token", "")

def get_stream_info(channel, token):
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }
    url = f"https://api.twitch.tv/helix/streams?user_login={channel}"
    r = requests.get(url, headers=headers)
    data = r.json().get("data", [])
    return data[0] if data else None

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    data = load_data()
    channel = context.args[0].lower() if context.args else None
    if not channel:
        await update.message.reply_text("❌ Especifica un canal: /add canal")
        return
    data.setdefault(user_id, [])
    if channel in data[user_id]:
        await update.message.reply_text("⚠️ Ya estás siguiendo ese canal.")
    else:
        data[user_id].append(channel)
        save_data(data)
        await update.message.reply_text(f"✅ Canal **{channel}** añadido.")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    data = load_data()
    channel = context.args[0].lower() if context.args else None
    if not channel:
        await update.message.reply_text("❌ Especifica un canal: /remove canal")
        return
    if user_id in data and channel in data[user_id]:
        data[user_id].remove(channel)
        save_data(data)
        await update.message.reply_text(f"🗑 Canal **{channel}** eliminado.")
    else:
        await update.message.reply_text("⚠️ No estás siguiendo ese canal.")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    data = load_data()
    channels = data.get(user_id, [])
    if channels:
        text = "📺 Canales que estás siguiendo:"
text = "\n".join(f"* - {c}" for c in channels)
    else:
        text = "❗ No estás siguiendo ningún canal.
Usa /add canal para empezar."
    await update.message.reply_text(text)

def check_streams():
    bot = Bot(token=TELEGRAM_TOKEN)
    access_token = get_twitch_token()
    while True:
        data = load_data()
        user_map = {}
        for user_id, channels in data.items():
            for channel in channels:
                user_map.setdefault(channel, []).append(user_id)
        for channel, user_ids in user_map.items():
            info = get_stream_info(channel, access_token)
            was_live = STREAM_STATUS.get(channel, False)
            is_live = info is not None
            if is_live and not was_live:
                title = info["title"]
                url = f"https://twitch.tv/{channel}"
                text = f"🔴 **{channel}** ha comenzado directo:
📌 *{title}*
👉 {url}"
                for uid in user_ids:
                    try:
                        bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
                    except Exception as e:
                        print(f"Error enviando a {uid}: {e}")
            STREAM_STATUS[channel] = is_live
        time.sleep(CHECK_INTERVAL)

def main():
    thread = threading.Thread(target=check_streams, daemon=True)
    thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("list", list_channels))
    app.run_polling()

if __name__ == "__main__":
    main()
