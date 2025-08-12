# pip install python-telegram-bot==20.3
import re
import logging
from typing import Dict, List, Tuple

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, PreCheckoutQueryHandler, ContextTypes, filters
)
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

WELCOME_DEFAULT = "👋 Привет! Это бот «ЖК Барахолка». Нажмите «Подать объявление» ниже."
WELCOME_FROM_CHANNEL = "🎉 Вы пришли из канала «ЖК Барахолка». Готовы подать объявление? Жмите ниже."

def _menu_kb(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Подать объявление", callback_data="start_new")],
        [InlineKeyboardButton("📜 Правила", url="https://t.me/zk_baraholka/1")],  # при желании замени ссылку
    ])

# /start c поддержкой deep-link: ?start=from_channel
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    source = args[0] if args else ""
    me = await context.bot.get_me()
    text = WELCOME_FROM_CHANNEL if source == "from_channel" else WELCOME_DEFAULT
    await update.message.reply_text(text, reply_markup=_menu_kb(me.username))

# Сообщение с кнопкой (для закрепа)
async def getbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = await context.bot.get_me()
    deep_link = f"https://t.me/{me.username}?start=from_channel"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📩 Подать объявление", url=deep_link)]])
    await update.message.reply_text(
        "Подать объявление в «ЖК Барахолка» — нажмите кнопку ниже:",
        reply_markup=kb,
    )

# Обработка клика по «📝 Подать объявление»
async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "start_new":
        # Простой вариант: попросим ввести /new (если у тебя уже есть сценарий /new)
        await q.message.reply_text("Окей! Нажмите команду /new, чтобы подать объявление.")
        # Если захочешь — позже привяжём кнопку напрямую к твоей функции cmd_new.

# ============ НАСТРОЙКИ ============
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID  = "@zk_baraholka"      # или числовой -100xxxxxxxxx
ADMIN_ID    = 6233188035            # твой Telegram user id (число)

# Оплата (опционально). Если пока не нужно — оставь пустой строкой.
PROVIDER_TOKEN = ""                # токен провайдера (ЮKassa/CloudPayments)
PRIORITY_PRICE_COP = 30000         # 300 ₽ в копейках

MAX_PHOTOS = 5

# Авто-модерация
BANNED_WORDS = ["мошенн", "наркот", "оруж", "поддел", "эрот", "инвест", "быстрый заработок"]
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MIN_LEN = 10
# ===================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("baraholka")

# Состояния диалога
(CATEGORY, TEXT, PHOTOS, CONTACT, CONFIRM, PAYMENT) = range(6)

# Память для черновиков (MVP без БД)
pending: Dict[int, Dict] = {}  # user_id -> {category, text, photos, contact, paid}


def auto_moderate(text: str) -> Tuple[bool, str]:
    t = (text or "").lower()
    for w in BANNED_WORDS:
        if w in t:
            return False, f"Обнаружено запрещённое слово: «{w}»."
    if URL_RE.search(text or ""):
        return False, "Ссылки в тексте запрещены."
    if not text or len(text.strip()) < MIN_LEN:
        return False, f"Слишком короткое описание (минимум {MIN_LEN} символов)."
    return True, ""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот «ЖК Барахолка».\n"
        "Чтобы подать объявление, нажмите /new"
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    pending[uid] = {"category": None, "text": "", "photos": [], "contact": "", "paid": False}
    kb = [
        [InlineKeyboardButton("Продажа", callback_data="cat_sale")],
        [InlineKeyboardButton("Услуги", callback_data="cat_service")],
        [InlineKeyboardButton("Покупка", callback_data="cat_buy")],
        [InlineKeyboardButton("Отдам/Обмен", callback_data="cat_free")],
        [InlineKeyboardButton("Другое", callback_data="cat_other")],
    ]
    await update.message.reply_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(kb))
    return CATEGORY


async def on_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if uid not in pending:
        await q.edit_message_text("Сначала /new")
        return ConversationHandler.END
    cat_map = {
        "cat_sale": "Продажа",
        "cat_service": "Услуги",
        "cat_buy": "Покупка",
        "cat_free": "Отдам/Обмен",
        "cat_other": "Другое",
    }
    pending[uid]["category"] = cat_map.get(q.data, "Другое")
    await q.edit_message_text(
        f"Категория: {pending[uid]['category']}\n\nНапишите текст объявления (до 1000 символов)."
    )
    return TEXT


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in pending:
        await update.message.reply_text("Сначала /new")
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if len(text) > 1000:
        await update.message.reply_text("Слишком длинно. Сократите до 1000 символов.")
        return TEXT
    pending[uid]["text"] = text
    await update.message.reply_text(
        f"Текст принят.\nТеперь отправьте до {MAX_PHOTOS} фото по одному. "
        "Когда хватит — /done. Если без фото — /skip."
    )
    return PHOTOS


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in pending:
        await update.message.reply_text("Сначала /new")
        return ConversationHandler.END
    photos: List[str] = pending[uid]["photos"]
    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"Максимум {MAX_PHOTOS} фото. Отправьте /done.")
        return PHOTOS
    photos.append(update.message.photo[-1].file_id)
    await update.message.reply_text(f"Фото {len(photos)}/{MAX_PHOTOS} добавлено. Отправьте ещё или /done.")
    return PHOTOS


async def on_photos_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in pending:
        await update.message.reply_text("Сначала /new")
        return ConversationHandler.END
    await update.message.reply_text(
        "Фото приняты. Напишите контакт (телефон или @username), либо /me чтобы использовать ваш username."
    )
    return CONTACT


async def on_photos_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in pending:
        await update.message.reply_text("Сначала /new")
        return ConversationHandler.END
    await update.message.reply_text(
        "Фото пропущены. Напишите контакт (телефон или @username), либо /me чтобы использовать ваш username."
    )
    return CONTACT


async def on_contact_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in pending:
        await update.message.reply_text("Сначала /new")
        return ConversationHandler.END
    username = update.effective_user.username
    pending[uid]["contact"] = f"@{username}" if username else str(uid)
    return await confirm_preview(update, context)


async def on_contact_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in pending:
        await update.message.reply_text("Сначала /new")
        return ConversationHandler.END
    pending[uid]["contact"] = (update.message.text or "").strip()
    return await confirm_preview(update, context)


async def confirm_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = pending[uid]
    preview = (
        f"Категория: {data['category']}\n\n"
        f"{data['text']}\n\n"
        f"Контакт: {data['contact']}\n"
        f"Фото: {len(data['photos'])} шт."
    )
    buttons = [[InlineKeyboardButton("✅ Отправить бесплатно (в очередь)", callback_data="post_free")]]
    if PROVIDER_TOKEN:
        buttons.append([InlineKeyboardButton("⚡ Приоритет (платно)", callback_data="post_paid")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="post_cancel")])
    await update.message.reply_text("Предпросмотр объявления:\n\n" + preview,
                                    reply_markup=InlineKeyboardMarkup(buttons))
    return CONFIRM


async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if uid not in pending:
        await q.edit_message_text("Сессия истекла. Начните заново: /new")
        return ConversationHandler.END

    if q.data == "post_cancel":
        pending.pop(uid, None)
        await q.edit_message_text("Отменено.")
        return ConversationHandler.END

    ok, reason = auto_moderate(pending[uid]["text"])
    if not ok:
        await q.edit_message_text(
            f"Объявление не прошло авто-проверку: {reason}\nОтредактируйте и отправьте заново (/new)."
        )
        return ConversationHandler.END

    if q.data == "post_free":
        await q.edit_message_text("Готово! Объявление отправлено в канал.")
        await publish_to_channel(context, uid, priority=False)
        pending.pop(uid, None)
        return ConversationHandler.END

    if q.data == "post_paid":
        if not PROVIDER_TOKEN:
            await q.edit_message_text("Оплата недоступна. Свяжитесь с админом.")
            return ConversationHandler.END
        price = [LabeledPrice("Приоритетная публикация", PRIORITY_PRICE_COP)]
        await context.bot.send_invoice(
            chat_id=uid,
            title="Приоритетная публикация",
            description="Ваше объявление выйдет быстрее (вне очереди).",
            payload=f"priority_{uid}",
            provider_token=PROVIDER_TOKEN,
            currency="RUB",
            prices=price,
        )
        await q.edit_message_text("Счёт отправлен. После оплаты объявление будет опубликовано.")
        return PAYMENT


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def on_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in pending:
        pending[uid]["paid"] = True
        await update.message.reply_text("Оплата получена! Публикуем объявление.")
        await publish_to_channel(context, uid, priority=True)
        pending.pop(uid, None)


async def publish_to_channel(context: ContextTypes.DEFAULT_TYPE, uid: int, priority: bool):
    data = pending.get(uid) or {}
    caption = f"[{data.get('category','')}] \n\n{data.get('text','')}\n\nКонтакт: {data.get('contact','')}"
    if priority:
        caption = "⚡ Приоритет\n\n" + caption

    # Сначала текст, затем фото (проще и надёжнее для новичка)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
    for fid in data.get("photos") or []:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=fid)

    # Авто-уведомление автора
    try:
        await context.bot.send_message(chat_id=uid, text="Ваше объявление опубликовано в канале.")
    except Exception:
        pass


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    pending.pop(uid, None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# Сообщение с кнопкой «Отправить объявление» — для закрепа
async def cmd_getbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = await context.bot.get_me()
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📩 Отправить объявление", url=f"https://t.me/{me.username}")]]
    )
    await update.message.reply_text(
        "📢 Разместить объявление в «ЖК Барахолка»\n\nНажмите кнопку ниже, чтобы отправить объявление боту.",
        reply_markup=kb,
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("new", cmd_new)],
        states={
            CATEGORY: [CallbackQueryHandler(on_category)],
            TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_text)],
            PHOTOS: [
                MessageHandler(filters.PHOTO, on_photo),
                CommandHandler("done", on_photos_done),
                CommandHandler("skip", on_photos_skip),
            ],
            CONTACT: [
                CommandHandler("me", on_contact_me),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_contact_text),
            ],
            CONFIRM: [CallbackQueryHandler(on_confirm)],
            PAYMENT: [
                PreCheckoutQueryHandler(precheckout),
                MessageHandler(filters.SUCCESSFUL_PAYMENT, on_paid),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("getbutton", cmd_getbutton))
    app.add_handler(conv)
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("getbutton", getbutton))
app.add_handler(CallbackQueryHandler(menu_callbacks, pattern="^(start_new)$"))

    app.run_polling()


if __name__ == "__main__":
    main()

