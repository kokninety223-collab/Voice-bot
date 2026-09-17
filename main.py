import os
import asyncio
import threading
import urllib.request
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Hugging Face Space ချိတ်ဆက်ခြင်း
HF_SPACE = "karikatura13/my-voxcpm2-voice"
TOKEN = "8822502239:AAGTJq5g8QbcslgNz-5P89_RqZk4IC46b_I"

client = None

def get_client():
    global client
    if client is None:
        client = Client(HF_SPACE)
    return client

# Render Web Service အိပ်မသွားစေရန် Dummy Server
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! အသံထုတ်ချင်သော စာသားကို ပို့ပေးလိုက်ပါခင်ဗျာ။")

def find_audio_file(data):
    """Gradio ပြန်ပေးသော Data ပုံစံအမျိုးမျိုး (dict, list, url, string) ထဲမှ အသံဖိုင်လမ်းကြောင်းကို ရှာဖွေထုတ်ယူခြင်း"""
    if isinstance(data, dict):
        for key in ["path", "name", "url", "file_path"]:
            if key in data and data[key]:
                res = find_audio_file(data[key])
                if res:
                    return res
        for val in data.values():
            res = find_audio_file(val)
            if res:
                return res

    elif isinstance(data, (list, tuple)):
        for item in data:
            res = find_audio_file(item)
            if res:
                return res

    elif isinstance(data, str):
        # Local file ဖြစ်နေပါက
        if os.path.exists(data):
            return data
        # Web URL ဖြစ်နေပါက ဖုန်းထဲသို့ ဒေါင်းလုဒ်ဆွဲယူခြင်း
        if data.startswith("http://") or data.startswith("https://"):
            temp_path = tempfile.mktemp(suffix=".wav")
            urllib.request.urlretrieve(data, temp_path)
            return temp_path
        # Audio extension စစ်ဆေးခြင်း
        if any(data.lower().endswith(ext) for ext in [".wav", ".mp3", ".ogg", ".flac", ".m4a"]):
            return data

    return None

def generate_voice(text):
    c = get_client()
    # fn_index=0 ဖြင့် စတင်ခေါ်ယူခြင်း
    try:
        raw_result = c.predict(text, fn_index=0)
    except Exception:
        raw_result = c.predict(text)
    
    audio_path = find_audio_file(raw_result)
    if not audio_path:
        raise ValueError(f"အသံဖိုင် မတွေ့ရှိပါ: {raw_result}")
    return audio_path

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_to_speak = update.message.text.strip()
    status_msg = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်၊ ခဏစောင့်ပေးပါ...")

    try:
        input_text = f"... {text_to_speak}"
        loop = asyncio.get_running_loop()
        
        # Hugging Face Space သို့ လှမ်းခေါ်ခြင်း
        audio_file_path = await loop.run_in_executor(None, lambda: generate_voice(input_text))

        # Telegram သို့ Voice note အဖြစ် ပို့ဆောင်ခြင်း
        with open(audio_file_path, "rb") as voice_file:
            await update.message.reply_voice(
                voice=voice_file,
                caption=text_to_speak[:50]
            )

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"Error တက်သွားပါသည်: {str(e)}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot polling is running...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        while True:
            await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
