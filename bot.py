import os
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("qureo-helper")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
# Optional OpenAI-compatible API settings. Without these, bot gives a helpful setup message.
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip()
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini").strip()

SYSTEM_PROMPT = """أنت مساعد تعليمي لطالب ثانوي. اشرح السؤال بالعربية المصرية البسيطة،
ثم وضّح طريقة الحل، وبعدها أعطِ إجابة مقترحة إذا أمكن. في أسئلة البرمجة، حدّد اللغة
(غالبًا JavaScript أو Python) واكتب كودًا واضحًا مع شرح مختصر. في الاختيار من متعدد،
اذكر الاختيار المقترح وسببًا مختصرًا. لو الصورة غير واضحة، اطلب صورة أوضح.
لا تطلب كلمة مرور QUREO أو أي بيانات دخول. لا تدخل إلى QUREO ولا تضغط إرسال نيابة عن المستخدم.
"""

async def ask_ai(text: str, image_bytes: bytes | None = None, image_mime: str = "image/jpeg") -> str:
    if not AI_API_KEY:
        return (
            "البوت اتجهّز، لكن محتاج إعداد خدمة ذكاء اصطناعي عشان يحل الأسئلة.\n\n"
            "لو أنت صاحب البوت، أضف AI_API_KEY في إعدادات الاستضافة. "
            "من غير مفتاح، البوت يقدر يستقبل الرسائل فقط ومش هيقدر يحللها تلقائيًا."
        )
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)
        content = [{"type": "text", "text": text or "حل السؤال الظاهر في الصورة واشرحه."}]
        if image_bytes:
            import base64
            b64 = base64.b64encode(image_bytes).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{image_mime};base64,{b64}"}
            })
        response = await client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or "مش قادر أطلع إجابة واضحة. جرّب تاني."
    except Exception as exc:
        log.exception("AI request failed")
        return (
            "حصلت مشكلة في خدمة الإجابة. راجع إعدادات AI_API_KEY وAI_BASE_URL وAI_MODEL "
            "أو جرّب لاحقًا.\n"
            f"تفاصيل مختصرة: {type(exc).__name__}"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلًا! أنا Qureo Helper 📘\n\n"
        "ابعت نص السؤال أو صورة واضحة، وأنا أساعدك في فهمه وحله.\n"
        "أقدر أساعد في الاختيار من متعدد، JavaScript، Python، ومفاهيم الثقافة المالية.\n\n"
        "مهم: ما تبعتش كلمة مرور QUREO أو أي بيانات شخصية."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "طريقة الاستخدام:\n"
        "• ابعت السؤال كنص.\n"
        "• أو ابعت صورة واضحة للسؤال.\n"
        "• لو السؤال برمجة، اكتب اللغة المطلوبة لو معروفة.\n"
        "البوت مساعد تعليمي منفصل؛ لا يسجّل دخولًا إلى QUREO ولا يضغط إرسال تلقائيًا."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    answer = await ask_ai(msg.text)
    await msg.reply_text(answer)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.photo:
        return
    photo = msg.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        temp_path = tmp.name
    try:
        await tg_file.download_to_drive(custom_path=temp_path)
        image_bytes = Path(temp_path).read_bytes()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
    caption = msg.caption or "حل السؤال الظاهر في الصورة واشرحه بالعربية المصرية."
    answer = await ask_ai(caption, image_bytes=image_bytes, image_mime="image/jpeg")
    await msg.reply_text(answer)

async def main():
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in the hosting environment.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    log.info("Qureo Helper is running")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
