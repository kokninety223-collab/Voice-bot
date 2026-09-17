import os
import asyncio
import threading
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

def check_hf_api():
    try:
        c = Client(HF_SPACE)
        info = "✅ Space သို့ ချိတ်ဆက်မိပါပြီ။ API Rule များမှာ:\n\n"
        for idx, endp in enumerate(c.endpoints):
            api_name = getattr(endp, 'api_name', None)
            if not api_name: 
                api_name = f"Tab Number: {idx}"
            info += f"🎯 {api_name}\n"
            
            params = getattr(endp, 'parameters', [])
            if not params:
                info += "  - (ဘာ Parameter မှ မတောင်းပါ)\n"
            else:
                for p in params:
                    p_name = getattr(p, 'parameter_name', 'Unknown')
                    p_type = getattr(p, 'type', 'Unknown')
                    info += f"  - {p_name} : {p_type}\n"
            info += "\n"
        return info
    except Exception as e:
        return f"❌ Hugging Face Space သို့ ချိတ်ဆက်၍မရပါ။:\n\n{str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! API ကို စစ်ဆေးရန် စာတစ်ကြောင်း ရိုက်ပို့ကြည့်ပါ။")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await update.message.reply_text("🔍 Hugging Face ဘက်ရှိ အခြေအနေကို စစ်ဆေးနေပါသည်...")
    try:
        loop = asyncio.get_running_loop()
        api_info = await loop.run_in_executor(None, check_hf_api)
        await status.edit_text(api_info[:4000])
    except Exception as e:
        await status.edit_text(f"Error: {str(e)}")

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
