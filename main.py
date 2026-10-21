import logging
import requests
import json
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

#KREDENSIAL & API KEYS
import os
from dotenv import load_dotenv

# Memuat file .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PARSE_API_KEY = os.getenv("PARSE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Kriteria preferensi pribadi Anda untuk disaring oleh Gemini
USER_PREFERENCE_PROMPT = """
Saya mencari posisi yang cocok untuk latar belakang IT / Software / Data.
- Utamakan posisi Remote, Hybrid, atau lokasi Jabodetabek.
- Cocok untuk Entry-level, Junior, atau Fresh Graduate.
- Saring dan prioritaskan lowongan yang paling relevan dan prospektif.
"""

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# FUNCTION SEARCH JOBS VIA PARSE.BOT REST API
def fetch_jobs_from_parse_bot(keyword):
    url = "https://api.parse.bot/scraper/1e76f6c9-a45f-4896-ae1d-0207e707e979/search_jobs"
    
    headers = {
        "X-API-Key": PARSE_API_KEY
    }
    
    params = {
        "keyword": keyword,
        "page_size": 5,
        "country_code": "ID"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                jobs = data
            elif isinstance(data, dict):
                jobs = data.get("jobs", data.get("data", {}).get("jobs", []))
            else:
                jobs = []
            return jobs
        else:
            print(f"Error Parse.bot Status {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"Exception Parse.bot: {e}")
        return []

# GEMINI AI FILTER
# def analyze_with_gemini(keyword, raw_jobs):
#     client = genai.Client(api_key=GEMINI_API_KEY)

#     prompt = f"""
#     Anda adalah AI Job Agent pribadi saya.
    
#     Saya sedang mencari pekerjaan dengan kata kunci: "{keyword}"
#     Kriteria preferensi saya:
#     {USER_PREFERENCE_PROMPT}
    
#     Berikut adalah data mentah lowongan dari Parse.bot (Glints):
#     {json.dumps(raw_jobs, indent=2)}
    
#     Tugas Anda:
#     1. Analisis data lowongan kerja di atas.
#     2. Pilih lowongan yang PALING COCOK (vibe-match) dengan kriteria saya.
#     3. Tulis balasan dalam format Telegram Markdown yang rapi:
#        - 📌 **[Nama Posisi]** - [Nama Perusahaan]
#        - 📍 **Lokasi:** [Lokasi / Tipe Kerja]
#        - 💡 **Alasan Cocok:** [Penjelasan singkat]
#        - 🔗 **Link Melamar:** [URL Lowongan jika ada di data]
#     """

#     response = client.models.generate_content(
#         model="gemini-3.1-flash-lite",
#         contents=prompt
#     )
#     return response.text

# GEMINI AI ANALYSIS FUNCTION
def analyze_with_gemini(keyword, jobs_data):
    client = genai.Client(api_key=GEMINI_API_KEY)
    # Prompt khusus dengan instruksi format HTML dan kriteria filter
    prompt = f"""
    Kamu adalah AI Jobs Bot.
    Tugasmu adalah menganalisis dan menyaring daftar lowongan kerja dari Glints berdasarkan profil pengguna berikut:

    PROFIL PENGGUNA:
    - Status: Fresh Graduate / Early Career (Pengalaman magang < 1 tahun)
    - Prioritas Lokasi: Area JABODETABEK (Jakarta, Bogor, Depok, Tangerang, Bekasi) atau REMOTE.
    - Posisi yang dicari: {keyword}

    DATA LOWONGAN KERJA (RAW JSON):
    {jobs_data}

    INSTRUKSI FORMAT OUTPUT & ANALISIS (PENTING):
    1. Kelompokkan lowongan menjadi 2 kategori:
       - 🌟 REKOMENDASI UTAMA (Cocok Fresh Grad / Entry-Level): Lowongan magang, fresh grad, atau syarat 0-1 tahun pengalaman.
       - ⚠️ PERLU PERTIMBANGAN (Pengalaman 1-2 Tahun): Berikan catatan jika kualifikasi masih memungkinkan untuk dilamar.
    2. Untuk SETIAP lowongan yang ditampilkan, buat NAMA POSISI sebagai link HTML yang bisa diklik langsung ke Glints:
       Format Link: <a href="https://glints.com/id/opportunities/jobs/ID_JOB_DI_SINI">Nama Posisi - Perusahaan</a>
       (Gunakan nilai "id" dari objek job JSON untuk mengisi ID_JOB_DI_SINI).
    3. Cantumkan rincian singkat per lowongan:
       - 📍 Lokasi & Mode Kerja (Onsite/Hybrid/Remote)
       - 🎓 Syarat Pendidikan & Pengalaman
       - 💰 Estimasi Gaji (jika tersedia)
       - 💡 Catatan singkat AI (misal: "Sesuai domisili Jabodetabek & Fresh Grad").
    4. Jika ada lowongan di luar area Jabodetabek atau butuh pengalaman > 2 tahun, beri label peringatan tegas/abaikan.
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Error Gemini API: {e}")
        return "Maaf, terjadi kesalahan saat menganalisis lowongan dengan Gemini."


# TELEGRAM BOT HANDLERS
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "👋 <b>Selamat datang di AI Job Finder Agent!</b>\n\n"
        "Ketik perintah <code>/cari &lt;nama_pekerjaan&gt;</code> untuk mencari lowongan.\n"
        "Contoh: <code>/cari Web Developer</code> atau <code>/cari Frontend Jakarta</code>"
    )
    await update.message.reply_text(welcome_msg, parse_mode="HTML")

async def cari_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Harap masukkan kata kunci! Contoh: <code>/cari Web Developer</code>", 
            parse_mode="HTML"
        )
        return

    query_keyword = " ".join(context.args)
    
    # Mengirim status awal ke pengguna
    await update.message.reply_text(
        f"🔍 Sedang mengambil lowongan <b>{query_keyword}</b> dari Parse.bot dan menganalisis via Gemini AI...", 
        parse_mode="HTML"
    )

    # Ambil data dari Parse.bot
    raw_jobs = fetch_jobs_from_parse_bot(query_keyword)

    if not raw_jobs:
        await update.message.reply_text(
            "❌ Gagal mengambil data dari Parse.bot atau lowongan tidak ditemukan."
        )
        return

    # Analisis dengan Gemini AI
    ai_result = analyze_with_gemini(query_keyword, raw_jobs)

    # Kirim hasil ke Telegram menggunakan parse_mode="HTML"
    # Parameter disable_web_page_preview=True agar chat tidak dipenuhi gambar preview URL
    await update.message.reply_text(
        ai_result, 
        parse_mode="HTML", 
        disable_web_page_preview=True
    )
# TELEGRAM BOT HANDLERS
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "👋 **Selamat datang di AI Job Finder Agent (Powered by Parse.bot & Gemini)!**\n\n"
        "Ketik perintah `/cari <nama_pekerjaan>` untuk mulai mencari lowongan.\n"
        "Contoh: `/cari Python` atau `/cari Data Engineer`"
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def cari_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Harap masukkan kata kunci! Contoh: `/cari Python`", parse_mode="Markdown")
        return

    query_keyword = " ".join(context.args)
    await update.message.reply_text(f"🔍 Sedang memanggil Parse.bot API untuk lowongan *{query_keyword}* dan dianalisis Gemini...", parse_mode="Markdown")

    #  Ambil data dari Parse.bot menggunakan API Key
    raw_jobs = fetch_jobs_from_parse_bot(query_keyword)

    if not raw_jobs:
        await update.message.reply_text("❌ Gagal mengambil data dari Parse.bot atau lowongan tidak ditemukan. Periksa kembali API Key Anda.")
        return

    # Analisis dengan Gemini AI
    ai_result = analyze_with_gemini(query_keyword, raw_jobs)

    # Kirim hasil ke Telegram
    await update.message.reply_text(ai_result, disable_web_page_preview=True)

# RUN BOT
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("cari", cari_command))
    
    print("Bot Telegram AI Agent aktif menggunakan Parse.bot API!")
    app.run_polling()