import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

HF_SPACE = "karikatura13/my-voxcpm2-voice"

# Gradio Client စတင်ချိတ်ဆက်ခြင်း
try:
    client = Client(HF_SPACE)
except Exception as e:
    client = None
    print(f"Client init error: {e}")

TOKEN = "8822502239:AAGTJq5g8QbcslgNz-5P89_RqZk4IC46b_I"

# Render Web Service အမြဲ Alive ဖြစ်စေရန်
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

def call_hf_api(text):
    global client
    if client is None:
        client = Client(HF_SPACE)
    
    # ပထမဆုံး default index ဖြင့် စမ်းသပ်ခေါ်ယူခြင်း
    try:
        return client.predict(text, fn_index=0)
    except Exception:
        # အကယ်၍ fn_index မရပါက api_name မပါဘဲ ခေါ်ယူခြင်း
        return client.predict(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_to_speak = update.message.text.strip()
    status_msg = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်၊ ခဏစောင့်ပေးပါ...")

    try:
        input_text = f"... {text_to_speak}"
        loop = asyncio.get_running_loop()
        
        # Background worker ဖြင့် API ခေါ်ခြင်း
        result = await loop.run_in_executor(None, lambda: call_hf_api(input_text))

        # Result format စစ်ဆေးခြင်း (tuple, list သို့မဟုတ် str)
        if isinstance(result, (list, tuple)):
            audio_path = result[0]
        elif isinstance(result, dict) and "name" in result:
            audio_path = result["name"]
        else:
            audio_path = str(result)

        with open(audio_path, 'rb') as audio_file:
            await update.message.reply_voice(voice=audio_file, caption=text_to_speak[:50])

        await status_msg.delete()
        
    except Exception as e:
        # Space ၏ endpoints အသေးစိတ်ကို ပြသပေးခြင်း
        err_msg = str(e)
        if client and hasattr(client, 'endpoints'):
            endpoints_list = list(client.endpoints.keys())
            err_msg += f"\n\nရရှိနိုင်သော APIs: {endpoints_list}"
        await status_msg.edit_text(f"Error တက်သွားပါသည်:\n{err_msg}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot polling is starting...")
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
    
