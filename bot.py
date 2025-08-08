# bot.py
import logging
import re
from typing import Dict, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)

# ---------------- CONFIG ----------------
BOT_TOKEN = "8305074407:AAF-AkXy1R9Bjck2Dv8o706QjxeJtzxeJ0g"
CHANNEL_ID = "@zk_baraholka"  # или числовой ID: -1001234567890
ADMIN_ID = 6233188035  # твой Telegram user id (число)
PROVIDER_TOKEN = "REPLACE_WITH_PROVIDER_TOKEN_OR_EMPTY"  # если не платишь — оставь пустым

# Цена приоритетной публикации в копейках (например 300 ₽ -> 30000 коп.)
PRIORITY_PRICE_COP = 30000

# Максимум фото
MAX_PHOTOS = 5

# ----------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния ConversationHandler
(
    CHOOSING_CATEGORY,
    TYPING_TEXT,
    UPLOADING_PHOTOS,
    ASK_CONTACT,
    CONFIRM,
    PAYMENT,
) = range(6)

# Временное хранилище заявок (в памяти)
pending_posts: Dict[int, Dict] = {}  # user_id -> post data


# --- Утилиты модерации ---
BANNED_WORDS = ["мошен", "поддел", "наркот", "оружие", "ссылка_запрет"]  # дополни

url_regex = re.compile(r"https?://\S+|www\.\S+")


def auto_moderate(text: str, photos: List) -> (bool, str):
    """Простейшая автоматическая модерация.
    Возвращает (passed: bool, reason_if_failed: str)
    """
    t = text.lower()
    # 1) Проверка на запрещённые слова
    for w in BANNED_WORDS:
        if w in t:
            return False, f"Найдено запрещённое слово: {w}"

    # 2) Ссылки — по умолчанию запрещаем
    if url_regex.search(text):
        return False, "Сообщения с внешними ссылками запрещены."

    # 3) Проверка длины
    if len(text) < 5:
        return False, "Слишком короткое описание."

    # 4) фото — не обязательная проверка, но можно добавить
    # Всё ок
    return True, ""


# --- Хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Чтобы подать объявление, нажмите /new\n"
        "Формат: текст + до 5 фото. Услуги размещаются по тарифу (приоритет — платно)."
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Продажа", callback_data="cat_sale")],
        [InlineKeyboardButton("Услуги", callback_data="cat_service")],
        [InlineKeyboardButton("Покупка", callback_data="cat_buy")],
        [InlineKeyboardButton("Отдам/Обмен", callback_data="cat_free")],
        [InlineKeyboardButton("Другое", callback_data="cat_other")],
    ]
    await update.message.reply_text(
        "Выберите категорию объявления:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_CATEGORY


async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cat_map = {
        "cat_sale": "Продажа",
        "cat_service": "Услуги",
        "cat_buy": "Покупка",
        "cat_free": "Отдам/Обмен",
        "cat_other": "Другое",
    }
    category = cat_map.get(query.data, "Другое")
    # Инициализируем черновик
    pending_posts[user_id] = {
        "category": category,
        "text": "",
        "photos": [],
        "contact": query.from_user.username or str(query.from_user.id),
        "paid": False,
    }
    await query.edit_message_text(f"Категория: {category}\n\nНапишите текст объявления (до 500 символов).")
    return TYPING_TEXT


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pending_posts:
        await update.message.reply_text("Сначала выберите /new и категорию.")
        return ConversationHandler.END

    text = update.message.text.strip()
    if len(text) > 1000:
        await update.message.reply_text("Текст слишком длинный — сократите до 1000 символов.")
        return TYPING_TEXT

    pending_posts[user_id]["text"] = text
    await update.message.reply_text(
        f"Текст сохранён. Теперь можете отправить до {MAX_PHOTOS} фото (или отправьте /skip если без фото)."
    )
    return UPLOADING_PHOTOS


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pending_posts:
        await update.message.reply_text("Сначала выберите /new и категорию.")
        return ConversationHandler.END

    files = pending_posts[user_id]["photos"]
    if len(files) >= MAX_PHOTOS:
        await update.message.reply_text(f"Максимум {MAX_PHOTOS} фото.")
        return UPLOADING_PHOTOS

    # Сохраняем file_id (для публикации в канал достаточно file_id)
    photo = update.message.photo[-1]  # лучшее качество
    files.append(photo.file_id)
    await update.message.reply_text(f"Фото принято ({len(files)}/{MAX_PHOTOS}). Отправьте ещё или /done.")
    return UPLOADING_PHOTOS


async def skip_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pending_posts:
        await update.message.reply_text("Сначала выберите /new и категорию.")
        return ConversationHandler.END
    await update.message.reply_text("Фото пропущены. Укажите контакт (тел/username) или отправьте /me чтобы использовать ваш username.")
    return ASK_CONTACT


async def done_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pending_posts:
        await update.message.reply_text("Сначала выберите /new и категорию.")
        return ConversationHandler.END
    await update.message.reply_text("Фото приняты. Укажите контакт (тел/username) или отправьте /me чтобы использовать ваш username.")
    return ASK_CONTACT


async def use_my_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pending_posts:
        await update.message.reply_text("Сначала выберите /new и категорию.")
        return ConversationHandler.END
    username = update.message.from_user.username
    pending_posts[user_id]["contact"] = f"@{username}" if username else str(user_id)
    return await confirm_flow_start(update, context)


async def receive_contact_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pending_posts:
        await update.message.reply_text("Сначала выберите /new и категорию.")
        return ConversationHandler.END
    contact = update.message.text.strip()
    pending_posts[user_id]["contact"] = contact
    return await confirm_flow_start(update, context)


async def confirm_flow_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    data = pending_posts[user_id]
    # Автоматическая премодерация
    passed, reason = auto_moderate(data["text"], data["photos"])
    preview = f"Категория: {data['category']}\n\n{data['text']}\n\nКонтакт: {data['contact']}\n"
    if data["photos"]:
        preview += f"\nФото: {len(data['photos'])} шт."

    if not passed:
        # Если не прошло — уведомляем пользователя и отправляем админу
        await update.message.reply_text(f"К сожалению, объявление не прошло проверку: {reason}\nАдминистратор рассмотрит его.")
        # отправляем админу
        admin_msg = f"⚠️ Объявление от @{user.username or user.id} НЕ прошло авто-модерацию.\nПричина: {reason}\n\nPreview:\n{preview}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        # отправляем в админ-чат для ручной модерации
        # (мы можем переслать данные)
        # завершение
        del pending_posts[user_id]
        return ConversationHandler.END

    # Если прошло — спросим про приоритет (платная опция)
    kb = [
        [InlineKeyboardButton("Опубликовать бесплатно (в очередь)", callback_data="do_free")],
    ]
    # Если провайдер настроен, предложим оплату
    if PROVIDER_TOKEN:
        kb.append([InlineKeyboardButton("Приоритет — платно (быстрая публикация)", callback_data="do_pay")])
    kb.append([InlineKeyboardButton("Отменить", callback_data="do_cancel")])

    await update.message.reply_text(
        "Превью объявления:\n\n" + preview + "\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return CONFIRM


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in pending_posts:
        await query.edit_message_text("Время сессии истекло или вы уже отправили объявление.")
        return ConversationHandler.END

    if query.data == "do_cancel":
        del pending_posts[user_id]
        await query.edit_message_text("Подача объявления отменена.")
        return ConversationHandler.END

    if query.data == "do_free":
        # Публикуем бесплатно (в порядке очереди = публикуем сразу, но можно реализовать очередь)
        await query.edit_message_text("Ваше объявление отправлено в очередь на публикацию (бесплатно).")
        await publish_to_channel(context, user_id, priority=False)
        del pending_posts[user_id]
        return ConversationHandler.END

    if query.data == "do_pay":
        # начинаем платеж: отправляем инвойс
        # Создаем цену
        price = LabeledPrice(label="Приоритетная публикация", amount=PRIORITY_PRICE_COP)
        try:
            await context.bot.send_invoice(
                chat_id=user_id,
                title="Приоритетная публикация",
                description="Публикация объявления в канале ЖК БАРАХОЛКА — приоритетная",
                payload=f"priority_post_{user_id}",
                provider_token=PROVIDER_TOKEN,
                currency="RUB",
                prices=[price],
            )
            await query.edit_message_text("Выберите оплату в чате. После оплаты объявление будет опубликовано.")
            return PAYMENT
        except Exception as e:
            logger.error("Ошибка отправки инвойса: %s", e)
            await query.edit_message_text("Не удалось инициировать оплату. Попробуйте позже.")
            return ConversationHandler.END


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем pre_checkout_query, подтверждаем."""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь оплатил — публикуем объявление с приоритетом."""
    payment = update.message.successful_payment
    user_id = update.message.from_user.id
    # payload можно не проверять здесь, но можно сверить
    # публикуем
    await update.message.reply_text("Оплата получена! Через несколько минут объявление появится в канале.")
    # отмечаем платное
    if user_id in pending_posts:
        pending_posts[user_id]["paid"] = True
        await publish_to_channel(context, user_id, priority=True)
        del pending_posts[user_id]
    else:
        # безопасность: ничего не найдено
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Оплата от {user_id}, но объявление не найдено в памяти.")


async def publish_to_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int, priority: bool):
    """Публикует объявление pending_posts[user_id] в канал."""
    data = pending_posts.get(user_id)
    if not data:
        return
    caption = f"[{data['category']}]\n\n{data['text']}\n\nКонтакт: {data['contact']}"
    # если приоритет — добавим значок
    if priority:
        caption = "⚡️ Приоритет\n\n" + caption

    # Публикация: если есть фото — отправляем медиагруппу или одно фото с подписью
    bot = context.bot
    try:
        if data["photos"]:
            # если несколько фото, отправляем первую с подписью, остальные как media_group
            # проще: отправим все фото как медиагруппу (без подписи), затем текст постом
            media = data["photos"]
            # сначала отправим текст + метка
            await bot.send_message(chat_id=CHANNEL_ID, text=caption)
            for file_id in media:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=file_id)
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=caption)
        # уведомим автора
        await bot.send_message(chat_id=user_id, text="Ваше объявление опубликовано в канале.")
    except Exception as e:
        logger.error("Ошибка публикации: %s", e)
        await bot.send_message(chat_id=ADMIN_ID, text=f"Ошибка при публикации объявления от {user_id}: {e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if pending_posts.get(user_id):
        del pending_posts[user_id]
    await update.message.reply_text("Подача объявления отменена.")
    return ConversationHandler.END


# Admin command to list pending (for future extension)
async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lines = []
    for uid, post in pending_posts.items():
        lines.append(f"user={uid}, cat={post['category']}, len_text={len(post['text'])}, photos={len(post['photos'])}")
    await update.message.reply_text("\n".join(lines) if lines else "Нет черновиков.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("new", cmd_new)],
        states={
            CHOOSING_CATEGORY: [CallbackQueryHandler(category_chosen)],
            TYPING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
            UPLOADING_PHOTOS: [
                MessageHandler(filters.PHOTO, photo_handler),
                CommandHandler("skip", skip_photos),
                CommandHandler("done", done_photos),
            ],
            ASK_CONTACT: [
                CommandHandler("me", use_my_contact),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_contact_text),
            ],
            CONFIRM: [CallbackQueryHandler(confirm_callback)],
            PAYMENT: [],  # handled by payments handlers
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("admin_pending", admin_pending))
    # Payments handlers
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(CallbackQueryHandler(precheckout_callback, pattern="^pre_checkout$"))  # not strictly needed

    app.run_polling()


if __name__ == "__main__":
    main()

