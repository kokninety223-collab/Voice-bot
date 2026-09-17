import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

HF_SPACE = "karikatura13/my-voxcpm2-voice"
client = Client(HF_SPACE)

TOKEN = "8822502239:AAGTJq5g8QbcslgNz-5P89_RqZk4IC46b_I"

# Render အတွက် Web Server (GET ရော HEAD ရော 200 OK ပြန်ပေးရန်)
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_to_speak = update.message.text.strip()
    status_msg = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်၊ ခဏစောင့်ပေးပါ...")

    try:
        input_text = f"... {text_to_speak}"
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: client.predict(input_text, api_name="/predict")
        )

        audio_path = result if isinstance(result, str) else result[0]

        with open(audio_path, 'rb') as audio_file:
            await update.message.reply_voice(voice=audio_file, caption=text_to_speak[:50])

        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"Error တက်သွားပါသည်: {str(e)}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot polling is starting...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        # Bot အမြဲ run နေစေရန်
        while True:
            await asyncio.sleep(3600)

def main():
    # Web server thread စတင်ခြင်း
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # Telegram Bot ကို asyncio loop သန့်သန့်ဖြင့် run ခြင်း
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
