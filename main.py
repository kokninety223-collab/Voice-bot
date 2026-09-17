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

# Render ကို 24/7 အလုပ်လုပ်စေရန်
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

def get_audio_from_hf(text):
    c = Client(HF_SPACE)
    style = "(A warm, gentle young female voice, clear storytelling tone)"
    
    # AI ဆီမှ စာသားသက်သက်ဖြင့်သာ အသံတောင်းယူခြင်း (Parameter Error မဖြစ်စေရန်)
    try:
        res = c.predict(text, style, 2.0, 10, 42, fn_index=0)
    except:
        try:
            res = c.predict(style, text, 2.0, 10, 42, fn_index=0)
        except:
            res = c.predict(text, 2.0, 10, 42, fn_index=0)
    
    # ပြန်ကျလာသော Data ထဲမှ အသံဖိုင်ကို အလိုအလျောက် ရှာဖွေခြင်း
    def find_audio(data):
        if isinstance(data, dict):
            for k in ["path", "name", "url"]:
                if k in data and data[k]: return find_audio(data[k])
            for v in data.values():
                if isinstance(v, (dict, list, str)): return find_audio(v)
        elif isinstance(data, (list, tuple)) and len(data) > 0:
            return find_audio(data[0])
        elif isinstance(data, str) and (os.path.exists(data) or data.startswith("http")):
            return data
        return None
        
    audio = find_audio(res)
    if not audio: raise Exception("အသံဖိုင် ပြန်မကျလာပါ။")
    
    if audio.startswith("http"):
        path = tempfile.mktemp(suffix=".wav")
        urllib.request.urlretrieve(audio, path)
        return path
    return audio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ အစ်ကို! အသံထုတ်ချင်သော စာသားကို တိုက်ရိုက် ပို့ပေးပါ။")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    status = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်... (ခဏစောင့်ပါ)")
    
    try:
        loop = asyncio.get_running_loop()
        audio_path = await loop.run_in_executor(None, lambda: get_audio_from_hf(text))
        
        with open(audio_path, 'rb') as f:
            await update.message.reply_voice(voice=f, caption=text[:40])
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Error တက်သွားပါသည်:\n{str(e)[:200]}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running...")
    async with app:
        await app.start()
        # drop_pending_updates=True ထည့်ထားသဖြင့် Conflict Error ကို ကာကွယ်ပေးပါမည်
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
