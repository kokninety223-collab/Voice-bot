import os
import asyncio
import threading
import tempfile
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

HF_SPACE = "karikatura13/my-voxcpm2-voice"
TOKEN = "8822502239:AAGRyjwDPm46Pl-ZGPqlE1BhM8MtjE9LXW4"

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()

def extract_audio(data):
    if not data: return None
    if isinstance(data, dict):
        for k in ["path", "name", "url", "video", "file_path"]:
            if k in data and data[k]:
                res = extract_audio(data[k])
                if res: return res
        for v in data.values():
            if isinstance(v, (dict, list, str)):
                res = extract_audio(v)
                if res: return res
    elif isinstance(data, (list, tuple)):
        for i in data:
            res = extract_audio(i)
            if res: return res
    elif isinstance(data, str):
        if os.path.exists(data): return data
        if data.startswith("http"):
            path = tempfile.mktemp(suffix=".wav")
            urllib.request.urlretrieve(data, path)
            return path
        if any(data.lower().endswith(x) for x in [".wav", ".mp3", ".ogg", ".flac", ".m4a"]):
            return data
    return None

def get_audio_from_hf(text):
    c = Client(HF_SPACE)
    prompt = f"(A warm, gentle young female voice, clear storytelling tone) ... {text}"
    
    payloads = [
        (text,),
        (prompt,),
        (None, "", text, 2.0, 10, 42),
        (None, "", prompt, 2.0, 10, 42),
        (prompt, 2.0, 10, 42),
        (text, 2.0, 10, 42)
    ]
    
    for fn_idx in range(5):
        for p in payloads:
            try:
                res = c.predict(*p, fn_index=fn_idx)
                audio = extract_audio(res)
                if audio: return audio
            except:
                continue

    raise Exception("AI Model မှ အသံဖိုင် ပြန်လည်ထုတ်ပေးခြင်း မရှိပါ။ API Parameter လွဲမှားနေပါသည်။")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! အသံထုတ်ချင်သော စာသားကို တိုက်ရိုက် ပို့ပေးပါ။")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text: return
        
    status = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်... (ခဏစောင့်ပါ)")
    
    try:
        loop = asyncio.get_running_loop()
        audio_path = await loop.run_in_executor(None, lambda: get_audio_from_hf(text))
        
        with open(audio_path, 'rb') as f:
            await update.message.reply_voice(voice=f, caption=text[:40])
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Error တက်သွားပါသည်:\n{str(e)}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
