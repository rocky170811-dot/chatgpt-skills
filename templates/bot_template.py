"""
Шаблон Telegram-бота: приветствие, кнопки, лид-магнит за подписку, заявки в CSV.

Запуск:
    pip install -U python-telegram-bot python-dotenv
    python bot.py

Токен — только в .env, никогда в этом файле.
"""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.getenv("CHANNEL", "").strip()  # @канал — пусто, если проверка не нужна
LEADS_FILE = Path("leads.csv")

# --- Что бот выдаёт и как говорит. Меняй под себя ---------------------------

WELCOME = (
    "Привет, {name}!\n\n"
    "Я выдам тебе <b>гайд</b> — забирай по кнопке ниже."
)
MAGNET_TEXT = (
    "Держи гайд: https://example.com/guide\n\n"
    "Если будут вопросы — просто напиши мне сюда."
)
NEED_SUB_TEXT = "Чтобы забрать гайд, подпишись на канал и нажми кнопку ещё раз."

logging.basicConfig(
    format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


# --- Клавиатуры -------------------------------------------------------------

def main_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("📘 Забрать гайд", callback_data="magnet")]]
    if CHANNEL:
        rows.insert(
            0,
            [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL.lstrip('@')}")],
        )
    rows.append([InlineKeyboardButton("✍️ Оставить заявку", callback_data="lead")])
    return InlineKeyboardMarkup(rows)


# --- Проверка подписки ------------------------------------------------------

async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True, если проверка не настроена или пользователь состоит в канале.

    Важно: бот должен быть администратором канала, иначе Telegram вернёт ошибку.
    """
    if not CHANNEL:
        return True
    try:
        member = await context.bot.get_chat_member(CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as exc:
        log.warning("Не смог проверить подписку (бот админ канала?): %s", exc)
        return True  # не блокируем человека из-за нашей ошибки настройки


# --- Хендлеры ---------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "друг"
    await update.message.reply_text(
        WELCOME.format(name=name),
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # без этого кнопка «залипает»

    if query.data == "magnet":
        if await is_subscribed(query.from_user.id, context):
            await query.message.reply_text(MAGNET_TEXT, parse_mode=ParseMode.HTML)
            save_lead(query.from_user, "забрал гайд")
        else:
            await query.message.reply_text(NEED_SUB_TEXT, reply_markup=main_keyboard())

    elif query.data == "lead":
        context.user_data["waiting_for_lead"] = True
        await query.message.reply_text("Напиши свой вопрос — я передам его автору.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if context.user_data.pop("waiting_for_lead", False):
        save_lead(update.effective_user, text)
        await update.message.reply_text("Записал, спасибо! Скоро вернёмся с ответом.")
        return

    # --- ИИ-ответы. Раскомментируй, если задан ANTHROPIC_API_KEY -------------
    # import anthropic
    # client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # SYSTEM_PROMPT = "Ты дружелюбный помощник. Отвечай коротко, до 3 предложений."
    # reply = client.messages.create(
    #     model="claude-sonnet-5",
    #     max_tokens=500,
    #     system=SYSTEM_PROMPT,
    #     messages=[{"role": "user", "content": text}],
    # )
    # await update.message.reply_text(reply.content[0].text)
    # return

    await update.message.reply_text("Не понял. Нажми /start, чтобы увидеть кнопки.")


# --- Заявки в CSV -----------------------------------------------------------

def save_lead(user, message: str) -> None:
    is_new = not LEADS_FILE.exists()
    with LEADS_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["дата", "id", "username", "имя", "сообщение"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            user.id,
            user.username or "",
            user.first_name or "",
            message,
        ])


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    log.info("Бот запущен. Останови через Ctrl+C.")
    app.run_polling()


if __name__ == "__main__":
    main()