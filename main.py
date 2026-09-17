import os
import asyncio
import threading
import urllib.request
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client, handle_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

HF_SPACE = "karikatura13/my-voxcpm2-voice"
TOKEN = "8822502239:AAGTJq5g8QbcslgNz-5P89_RqZk4IC46b_I"

client = None
def get_client():
    global client
    if client is None:
        client = Client(HF_SPACE)
    return client

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

CHOOSE_STYLE, CUSTOM_STYLE, WAIT_AUDIO, CHOOSE_SEED, CUSTOM_SEED, GET_TEXT = range(6)

PRESET_STYLES = {
    "style_female": "(A warm, gentle young female voice, clear storytelling tone)",
    "style_male": "(A calm and professional male narrator in his late 20s, clear studio mic tone)",
    "style_news": "(A confident, serious and articulate news anchor voice, steady pace)",
    "style_anime": "(A cute, energetic young anime female character voice, lively)"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👩 မိန်းကလေးသံ", callback_data="style_female"),
         InlineKeyboardButton("👨 ယောက်ျားလေးသံ", callback_data="style_male")],
        [InlineKeyboardButton("🎙️ News", callback_data="style_news"),
         InlineKeyboardButton("✨ Anime", callback_data="style_anime")],
        [InlineKeyboardButton("✍️ ကိုယ်ပိုင် Style စာရိုက်မည်", callback_data="style_custom")],
        [InlineKeyboardButton("🎤 အသံဖိုင်ဖြင့် Clone လုပ်မည်", callback_data="style_clone")]
    ]
    await update.message.reply_text("အဆင့် (၁) - Voice Style ရွေးပါ သို့မဟုတ် Clone ရွေးပါ အစ်ကို-", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_STYLE

async def style_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data["style"] = None
    context.user_data["ref_audio"] = None

    if query.data == "style_custom":
        await query.edit_message_text("✍️ ကိုယ်ပိုင် Style (English) ရိုက်ထည့်ပါ:\n(ဥပမာ: A deep male voice)")
        return CUSTOM_STYLE
    elif query.data == "style_clone":
        await query.edit_message_text("🎤 အသံတု (Clone) လုပ်ရန်အတွက် ၃ စက္ကန့်မှ ၁၀ စက္ကန့်အတွင်းရှိ **Voice Note သို့မဟုတ် Audio ဖိုင်** ကို ပို့ပေးပါ အစ်ကို။")
        return WAIT_AUDIO
    else:
        context.user_data["style"] = PRESET_STYLES[query.data]
        return await ask_seed(query, context)

async def custom_style_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["style"] = update.message.text.strip()
    return await ask_seed(update, context)

async def handle_audio_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio_obj = update.message.voice or update.message.audio
    if not audio_obj:
        await update.message.reply_text("ကျေးဇူးပြု၍ အသံဖိုင် သို့မဟုတ် Voice Note သာ ပို့ပေးပါ။")
        return WAIT_AUDIO
        
    status_msg = await update.message.reply_text("📥 အသံဖိုင်ကို လက်ခံရယူနေပါသည်...")
    file = await context.bot.get_file(audio_obj.file_id)
    temp_audio_path = os.path.join(tempfile.gettempdir(), f"clone_{audio_obj.file_id}.ogg")
    await file.download_to_drive(temp_audio_path)
    
    context.user_data["ref_audio"] = temp_audio_path
    await status_msg.delete()
    return await ask_seed(update, context)

async def ask_seed(event, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎲 Default Seed (42)", callback_data="seed_42"),
         InlineKeyboardButton("🎲 Random Seed (123)", callback_data="seed_123")],
        [InlineKeyboardButton("🔢 စိတ်ကြိုက် Seed ရိုက်မည်", callback_data="seed_custom")]
    ]
    msg = "အဆင့် (၂) - Voice Seed (အသံတည်ငြိမ်ရန်) ရွေးပါ-"
    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(event, "edit_message_text"):
        await event.edit_message_text(msg, reply_markup=reply_markup)
    else:
        await event.reply_text(msg, reply_markup=reply_markup)
    return CHOOSE_SEED

async def seed_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "seed_custom":
        await query.edit_message_text("🔢 Seed နံပါတ်ရိုက်ထည့်ပါ (ဥပမာ: 999):")
        return CUSTOM_SEED
    context.user_data["seed"] = int(query.data.split("_")[1])
    await query.edit_message_text("အဆင့် (၃) - အသံထုတ်ချင်သော မြန်မာစာသားကို ပို့ပေးပါ-")
    return GET_TEXT

async def custom_seed_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: context.user_data["seed"] = int(update.message.text.strip())
    except ValueError: context.user_data["seed"] = 42
    await update.message.reply_text("အဆင့် (၃) - အသံထုတ်ချင်သော မြန်မာစာသားကို ပို့ပေးပါ-")
    return GET_TEXT

def find_audio_file(data):
    if isinstance(data, dict):
        for k in ["path", "name", "url", "file_path"]:
            if k in data and data[k]:
                res = find_audio_file(data[k])
                if res: return res
        for v in data.values():
            res = find_audio_file(v)
            if res: return res
    elif isinstance(data, (list, tuple)):
        for i in data:
            res = find_audio_file(i)
            if res: return res
    elif isinstance(data, str):
        if os.path.exists(data): return data
        if data.startswith("http"):
            path = tempfile.mktemp(suffix=".wav")
            urllib.request.urlretrieve(data, path)
            return path
        if any(data.lower().endswith(x) for x in [".wav", ".mp3", ".ogg"]): return data
    return None

def generate_voice(style, ref_audio, text, seed):
    c = get_client()
    last_error = ""
    prompt_text = f"{style} ... {text}" if style else text
    
    # Auto Endpoint Finder (Parameter အမှန်ဖြင့်သာ ချိတ်ဆက်ခြင်း)
    for i in range(5):
        if ref_audio:
            # Voice Clone Mode အတွက် Parameter ၆ ခု ပို့ခြင်း
            try:
                res = c.predict(handle_file(ref_audio), "", text, 2.0, 10, int(seed), fn_index=i)
                audio = find_audio_file(res)
                if audio: return audio
            except Exception as e:
                last_error += f"\n[Tab {i} Clone]: {str(e)}"
        else:
            # Text Mode အတွက် Parameter ၄ ခု သီးသန့် ပို့ခြင်း
            try:
                res = c.predict(prompt_text, 2.0, 10, int(seed), fn_index=i)
                audio = find_audio_file(res)
                if audio: return audio
            except Exception as e:
                last_error += f"\n[Tab {i} Text]: {str(e)}"
                
    raise ValueError(f"AI Model ဆီမှ အသံဖိုင် ထုတ်ယူ၍မရပါ။\n{last_error[:400]}")

async def get_text_and_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_to_speak = update.message.text.strip()
    style = context.user_data.get("style", None)
    ref_audio = context.user_data.get("ref_audio", None)
    seed = context.user_data.get("seed", 42)
    
    status_msg = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည် အစ်ကို (ခဏစောင့်ပေးပါ)...")
    try:
        loop = asyncio.get_running_loop()
        audio_path = await loop.run_in_executor(None, lambda: generate_voice(style, ref_audio, text_to_speak, seed))
        
        with open(audio_path, 'rb') as f:
            caption = f"Seed: {seed}\nMode: {'Voice Clone' if ref_audio else 'Text Style'}\n{text_to_speak[:30]}"
            await update.message.reply_voice(voice=f, caption=caption)
        await status_msg.delete()
        await update.message.reply_text("နောက်ထပ်လုပ်ရန် /start နှိပ်ပါ။")
    except Exception as e:
        await status_msg.edit_text(f"Error တက်သွားပါသည် အစ်ကို:\n{str(e)}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("လုပ်ဆောင်ချက်ကို ရပ်လိုက်ပါပြီ။ ပြန်စရန် /start နှိပ်ပါ။")
    return ConversationHandler.END

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_STYLE: [CallbackQueryHandler(style_button_callback)],
            CUSTOM_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_style_input)],
            WAIT_AUDIO: [MessageHandler(filters.VOICE | filters.AUDIO, handle_audio_upload)],
            CHOOSE_SEED: [CallbackQueryHandler(seed_button_callback)],
            CUSTOM_SEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_seed_input)],
            GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_text_and_generate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    app.add_handler(conv)
    
    print("Bot polling is running...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        while True: await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
