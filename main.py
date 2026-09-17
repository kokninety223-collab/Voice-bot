import os
import asyncio
import threading
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from gtts import gTTS

# အစ်ကို့ရဲ့ Token အမှန်
TOKEN = "8822502239:AAGRyjwDPm46Pl-ZGPqlE1BhM8MtjE9LXW4"

# Render မအိပ်သွားစေရန် Dummy Server
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! အသံထုတ်ချင်သော မြန်မာစာသားကို တိုက်ရိုက် ပို့ပေးပါ။")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text: return
        
    status = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်... (ခဏစောင့်ပါ)")
    
    try:
        def generate_audio():
            # Google AI ဖြင့် မြန်မာအသံ ('my') ထုတ်လုပ်ခြင်း
            tts = gTTS(text=text, lang='my', slow=False)
            audio_path = os.path.join(tempfile.gettempdir(), "voice.mp3")
            tts.save(audio_path)
            return audio_path

        loop = asyncio.get_running_loop()
        audio_file = await loop.run_in_executor(None, generate_audio)
        
        with open(audio_file, 'rb') as f:
            await update.message.reply_voice(voice=f, caption=text[:40])
            
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Error တက်သွားပါသည်:\n{str(e)}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running perfectly...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
