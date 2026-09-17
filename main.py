import os
import asyncio
import threading
import urllib.request
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client
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

# Hugging Face Space သတ်မှတ်ချက်များ
HF_SPACE = "karikatura13/my-voxcpm2-voice"
TOKEN = "8822502239:AAGTJq5g8QbcslgNz-5P89_RqZk4IC46b_I"

client = None

def get_client():
    global client
    if client is None:
        client = Client(HF_SPACE)
    return client

# Render Web Service မအိပ်သွားစေရန် Dummy Server
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

# Conversation အဆင့်များ
CHOOSE_STYLE, CUSTOM_STYLE, CHOOSE_SEED, CUSTOM_SEED, GET_TEXT = range(5)

PRESET_STYLES = {
    "style_female": "(A warm, gentle young female voice, clear storytelling tone)",
    "style_male": "(A calm and professional male narrator in his late 20s, clear studio mic tone)",
    "style_news": "(A confident, serious and articulate news anchor voice, steady pace)",
    "style_anime": "(A cute, energetic young anime female character voice, lively)"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("👩 မိန်းကလေးသံ", callback_data="style_female"),
            InlineKeyboardButton("👨 ယောက်ျားလေးသံ", callback_data="style_male")
        ],
        [
            InlineKeyboardButton("🎙️ News Narrator", callback_data="style_news"),
            InlineKeyboardButton("✨ Anime/Cute", callback_data="style_anime")
        ],
        [
            InlineKeyboardButton("✍️ ကိုယ်ပိုင် Style စာရိုက်ထည့်မည်", callback_data="style_custom")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("အဆင့် (၁) - ကျေးဇူးပြု၍ Voice Style (အသံပုံစံ) ရွေးချယ်ပါ-", reply_markup=reply_markup)
    return CHOOSE_STYLE

async def style_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "style_custom":
        await query.edit_message_text("✍️ ကိုယ်ပိုင် အသံပုံစံ (English prompt) ကို ရိုက်ထည့်ပေးပါ:\nဥပမာ- (A deep mature male voice)")
        return CUSTOM_STYLE
    else:
        context.user_data["style"] = PRESET_STYLES[choice]
        return await ask_seed(query, context)

async def custom_style_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["style"] = update.message.text.strip()
    return await ask_seed(update, context)

async def ask_seed(event, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🎲 Default Seed (42)", callback_data="seed_42"),
            InlineKeyboardButton("🎲 Random Seed (123)", callback_data="seed_123")
        ],
        [
            InlineKeyboardButton("🔢 စိတ်ကြိုက် Seed နံပါတ်ရိုက်ထည့်မည်", callback_data="seed_custom")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = "အဆင့် (၂) - Voice Seed (အသံမပြောင်းစေရန် ကုတ်နံပါတ်) ရွေးပါ-"

    if hasattr(event, "edit_message_text"):
        await event.edit_message_text(msg, reply_markup=reply_markup)
    else:
        await event.reply_text(msg, reply_markup=reply_markup)
    return CHOOSE_SEED

async def seed_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "seed_custom":
        await query.edit_message_text("🔢 ကြိုက်နှစ်သက်ရာ Seed နံပါတ်တစ်ခုခု ရိုက်ထည့်ပေးပါ (ဥပမာ- 999):")
        return CUSTOM_SEED
    elif choice == "seed_42":
        context.user_data["seed"] = 42
    else:
        context.user_data["seed"] = 123

    await query.edit_message_text("အဆင့် (၃) - အသံထုတ်ချင်သော မြန်မာစာသားကို ပို့ပေးပါ-")
    return GET_TEXT

async def custom_seed_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["seed"] = int(update.message.text.strip())
    except ValueError:
        context.user_data["seed"] = 42
    
    await update.message.reply_text("အဆင့် (၃) - အသံထုတ်ချင်သော မြန်မာစာသားကို ပို့ပေးပါ-")
    return GET_TEXT

# --- Audio Extraction Logic ---
def find_audio_file(data):
    if isinstance(data, dict):
        for key in ["path", "name", "url", "file_path"]:
            if key in data and data[key]:
                res = find_audio_file(data[key])
                if res: return res
        for val in data.values():
            res = find_audio_file(val)
            if res: return res
    elif isinstance(data, (list, tuple)):
        for item in data:
            res = find_audio_file(item)
            if res: return res
    elif isinstance(data, str):
        if os.path.exists(data): return data
        if data.startswith("http"):
            temp_path = tempfile.mktemp(suffix=".wav")
            urllib.request.urlretrieve(data, temp_path)
            return temp_path
        if any(data.lower().endswith(ext) for ext in [".wav", ".mp3", ".ogg"]):
            return data
    return None

def generate_voice(style, text, seed):
    c = get_client()
    input_text = f"{style} ... {text}"
    last_error = ""
    
    # Gradio API သို့ parameters အကုန်ထည့်၍ လှမ်းခေါ်ခြင်း
    try:
        raw_result = c.predict(None, "", input_text, 2.0, 10, int(seed), fn_index=1)
        audio_path = find_audio_file(raw_result)
        if audio_path: return audio_path
    except Exception as e:
        last_error += f"\nAttempt 1 Error: {str(e)}"
        
    try:
        raw_result = c.predict(None, "", input_text, 2.0, 10, int(seed), fn_index=2)
        audio_path = find_audio_file(raw_result)
        if audio_path: return audio_path
    except Exception as e:
        last_error += f"\nAttempt 2 Error: {str(e)}"

    raise ValueError(f"အသံဖိုင်မရရှိပါ။ အသေးစိတ်: {last_error}")

async def get_text_and_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_to_speak = update.message.text.strip()
    style = context.user_data.get("style", PRESET_STYLES["style_female"])
    seed = context.user_data.get("seed", 42)

    status_msg = await update.message.reply_text("🎙️ အသံထုတ်လုပ်နေပါသည်၊ ခဏစောင့်ပေးပါ အစ်ကို...")

    try:
        loop = asyncio.get_running_loop()
        # Background တွင် AI အသံထုတ်ခိုင်းခြင်း
        audio_file_path = await loop.run_in_executor(None, lambda: generate_voice(style, text_to_speak, seed))

        # Telegram သို့ Voice Note ပို့ခြင်း
        with open(audio_file_path, 'rb') as audio_file:
            caption_text = f"Seed: {seed}\nစာသား: {text_to_speak[:30]}..."
            await update.message.reply_voice(voice=audio_file, caption=caption_text)

        await status_msg.delete()
        await update.message.reply_text("နောက်ထပ် အသစ်ထုတ်ရန် /start ကို နှိပ်ပါ။")

    except Exception as e:
        await status_msg.edit_text(f"Error တက်သွားပါသည် အစ်ကို:\n{str(e)}")

    # တစ်ခါပြီးရင် အစကပြန်စရန်
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("လုပ်ဆောင်ချက်ကို ရပ်လိုက်ပါပြီ။ ပြန်စရန် /start နှိပ်ပါ။")
    return ConversationHandler.END

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # အဆင့်ဆင့် တောင်းယူမည့် Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_STYLE: [CallbackQueryHandler(style_button_callback)],
            CUSTOM_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_style_input)],
            CHOOSE_SEED: [CallbackQueryHandler(seed_button_callback)],
            CUSTOM_SEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_seed_input)],
            GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_text_and_generate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    app.add_handler(conv_handler)
    
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
    
