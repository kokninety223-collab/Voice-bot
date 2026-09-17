import os
import asyncio
import threading
import urllib.request
import tempfile
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client, handle_file
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

HF_SPACE = "karikatura13/my-voxcpm2-voice"
TOKEN = "8822502239:AAGTJq5g8QbcslgNz-5P89_RqZk4IC46b_I"

# Clone လုပ်ရန် အသံဖိုင်များကို ယာယီမှတ်သားမည့် နေရာ
user_clone_audio = {}

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
        for k in ["path", "name", "url", "file_path"]:
            if k in data and data[k]:
                res = extract_audio(data[k])
                if res: return res
        for v in data.values():
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
        if any(data.lower().endswith(x) for x in [".wav", ".mp3", ".ogg", ".flac"]): return data
    return None

def generate_voice(text, ref_audio=None):
    c = Client(HF_SPACE)
    seed = random.randint(1, 99999)
    style = "(A warm, gentle young female voice, clear storytelling tone)"
    
    audio_file = handle_file(ref_audio) if ref_audio else None
    
    # Hugging Face AI က တောင်းဆိုနိုင်သော Parameter ပုံစံ (၄) မျိုးလုံးကို ကြိုတင်ပြင်ဆင်ထားခြင်း
    payloads = [
        # ပုံစံ ၁: VoxCPM2 အသစ် (Parameter ၉ ခု - Text, Style, Audio, PromptBool, PromptText, CFG, Steps, Seed, Normalize)
        (text, style, audio_file, False, "", 2.0, 10, seed, True),
        
        # ပုံစံ ၂: VoxCPM1.5 (Parameter ၇ ခု - Text, Audio, PromptText, CFG, Steps, Normalize, Denoise)
        (text, audio_file, "", 2.0, 10, True, True),
        
        # ပုံစံ ၃: Basic Clone (Parameter ၆ ခု)
        (text, audio_file, "", 2.0, 10, seed),
        
        # ပုံစံ ၄: Text-to-Speech ရိုးရိုး (Audio မပါဝင်သော Parameter)
        (text, style, 2.0, 10, seed)
    ]
    
    # AI ၏ Tab 0, 1, 2 အားလုံးကို အလိုအလျောက် စမ်းသပ်ချိတ်ဆက်ခြင်း
    # Error တက်ပါက လျစ်လျူရှုပြီး အလုပ်လုပ်သော Tab ကို အလိုအလျောက် ရှာဖွေမည်
    for fn_idx in range(3):
        for payload in payloads:
            try:
                res = c.predict(*payload, fn_index=fn_idx)
                audio_path = extract_audio(res)
                if audio_path:
                    return audio_path
            except Exception:
                pass

    raise ValueError("AI Model နှင့် ချိတ်ဆက်၍မရပါ။ (API Error)")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "မင်္ဂလာပါ အစ်ကို!\n\n"
        "💬 **ရိုးရိုးအသံထုတ်ရန်:**\nစာသားကို တိုက်ရိုက် ရိုက်ပို့လိုက်ပါ။\n\n"
        "🎤 **အသံတု (Clone) လုပ်ရန်:**\nအသံဖိုင်/Voice Note ကို အရင်ပို့ပါ၊ ပြီးမှ စာသားကို ပို့ပါ။"
    )
    await update.message.reply_text(msg)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio_obj = update.message.voice or update.message.audio
    if not audio_obj: return
    
    status = await update.message.reply_text("📥 အသံဖိုင်ကို မှတ်သားနေပါသည်...")
    file = await context.bot.get_file(audio_obj.file_id)
    
    path = os.path.join(tempfile.gettempdir(), f"{audio_obj.file_id}.ogg")
    await file.download_to_drive(path)
    
    user_clone_audio[update.message.chat_id] = path
    await status.edit_text("✅ အသံဖိုင် မှတ်သားပြီးပါပြီ။ ဒီအသံနဲ့ ပြောစေချင်တဲ့ **မြန်မာစာသား** ကို ပို့ပေးပါ အစ်ကို။")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.message.chat_id
    ref_audio = user_clone_audio.get(chat_id)
    
    status = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်... (ခဏစောင့်ပေးပါ)")
    
    try:
        loop = asyncio.get_running_loop()
        audio_path = await loop.run_in_executor(None, lambda: generate_voice(text, ref_audio))
        
        with open(audio_path, 'rb') as f:
            await update.message.reply_voice(voice=f, caption=text[:40])
        await status.delete()
        
        # Clone ပြီးသွားရင် အသံအဟောင်းကို ဖျက်မည် (ရိုးရိုး Text ပြန်သုံးလို့ရအောင်)
        if chat_id in user_clone_audio:
            del user_clone_audio[chat_id]
            
    except Exception as e:
        await status.edit_text(f"Error တက်သွားပါသည် အစ်ကို:\n{str(e)}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        while True: await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
