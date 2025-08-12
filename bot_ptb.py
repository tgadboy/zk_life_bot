# pip install python-telegram-bot==20.3
import re
import logging
import random

from typing import Dict, List, Tuple

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, PreCheckoutQueryHandler, ContextTypes, filters
)

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



# ===== КОНСТАНТЫ ДЛЯ КНОПОК МЕНЮ =====
BTN_SELL        = "💰 Продать"
BTN_FIND        = "🔍 Найти"
BTN_SERVICE     = "🎯 Разместить услугу"
BTN_ADS         = "📢 Разместить рекламу"
BTN_FIND_SVC    = "🛠️ Найти сервис"
BTN_FIND_MASTER = "💅 Найти мастера"
BTN_DEALS       = "🔥 Акции и скидки"
BTN_RULES       = "📄 Правила канала"
BTN_BONUS       = "🎁 Получить 150 ₽"
BTN_PLAY        = "🎮 Поиграть"
BTN_ASK         = "💬 Задать вопрос"
BTN_CONTACTS    = "☎️ Важные контакты"

# (опционально) имя админа, если есть username:
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Zk_Life_Admin")  # например, "zk_admin"
RULES_URL = "https://t.me/zk_baraholka/7"         # можно заменить при необходимости

# ===== ИГРЫ: данные =====
GAME_BTN_TL  = "✅❌ Правда или ложь"
GAME_BTN_RPS = "✊✋✌️ Камень, ножницы, бумага"
GAME_BTN_FACT= "😄 Случайный факт или шутка"

TRUTH_OR_LIE = [
    ("Солнце — это звезда.", True),
    ("У улитки четыре сердца.", False),
    ("Амазонка — самая длинная река мира.", True),
    ("Человек использует 100% мозга постоянно.", False),
    ("Пингвины живут на Северном полюсе.", False),
    ("Молния может ударить в одно место дважды.", True),
]

FACTS_OR_JOKES = [
    "Факт: Самая короткая война в истории длилась около 38 минут.",
    "Шутка: — Доктор, я вижу будущее! — И как оно? — Расплывчатое… у вас очки запотели.",
    "Факт: У осьминога три сердца.",
    "Шутка: Моя диета проста: если я не вижу еды — я сплю.",
    "Факт: Мед — единственный продукт, который не портится.",


from telegram import ReplyKeyboardMarkup

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source = " ".join(context.args) if context.args else ""
    text = (
        "<b> Привет! 👋 </b>\n\n"
        "Я Лайвбот — твой помощник на территории ЖК.\n\n"
        "Я помогу найти то, что ты ищешь.\n"
        "Если чего-то нет в списке — ты можешь написать администратору.\n\n"
        "Внизу нажми на ту кнопку, тема которой тебя интересует. А если хочешь перейди назад в закреп канала нажми "
         '<a href="https://t.me/zk_baraholka/7">вернуться к каналу.</a>'
    )

    # Кнопки по две в ряд с эмодзи
    buttons = [
        ["💰 Продать", "🔍 Найти"],
        ["🎯 Разместить услугу", "📢 Разместить рекламу"],
        ["🛠️ Найти сервис", "💅 Найти мастера"],
        ["🔥 Акции и скидки", "🎁 Получить 150 ₽"],
        ["🎮 Поиграть", "☎️ Важные контакты"],
        ["💬 Задать вопрос", "📗 Правила канала"],
    ]

    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# ==== ОБРАБОТКА КНОПОК МЕНЮ (reply) ====
async def start_new_with_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Запускает создание объявления сразу с выбранной категорией."""
    uid = update.effective_user.id
    pending[uid] = {"category": category, "text": "", "photos": [], "contact": "", "paid": False}
    await update.message.reply_text(
        f"Категория: {category}\n\nНапишите текст объявления (до 1000 символов)."
    )
    return TEXT  # позволяем ConversationHandler забрать управление

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Роутер для нажатий на кнопки меню (reply-клавиатура)."""
    msg = (update.message.text or "").strip()

    # 1) Продать → запустить воронку /new с категорией "Продажа"
    if msg == BTN_SELL:
        return await start_new_with_category(update, context, "Продажа")

    # 2) Найти → подсказка, как искать в канале
    if msg == BTN_FIND:
        await update.message.reply_text(
            "Чтобы найти объявление, откройте канал и используйте поиск по ключевым словам.\n"
            "Например: «велосипед», «сдаю», «услуги ремонта».",
            disable_web_page_preview=True
        )
        return

    # 3) Разместить услугу → воронка с категорией "Услуги"
    if msg == BTN_SERVICE:
        return await start_new_with_category(update, context, "Услуги")

    # 4) Разместить рекламу → контакт администратора
    if msg == BTN_ADS:
        contact_text = "Свяжитесь с администратором для рекламы."
        if ADMIN_USERNAME:
            contact_text += f" Пишите: @{ADMIN_USERNAME}"
        else:
            contact_text += f" ID администратора: {ADMIN_ID}"
        await update.message.reply_text(contact_text)
        return

    # 5) Найти сервис → подсказка/ссылка (при желании тут можно сделать каталог)
    if msg == BTN_FIND_SVC:
        await update.message.reply_text(
            "Напишите, какой сервис вы ищете (например: клининг, доставка, ветеринар) — подскажу или дам контакты."
        )
        return

    # 6) Найти мастера → подсказка/ссылка
    if msg == BTN_FIND_MASTER:
        await update.message.reply_text(
            "Какого мастера ищете? (например: сантехник, электрик, парикмахер)\n"
            "Напишите одним сообщением — я предложу варианты."
        )
        return

    # 7) Акции и скидки → можно использовать хэштег в канале
    if msg == BTN_DEALS:
        await update.message.reply_text(
            "Смотрите свежие акции и скидки в канале по хэштегу #акции.\n"
            "Перейти: https://t.me/zk_baraholka",
            disable_web_page_preview=True
        )
        return

    # 8) Правила канала → ссылка
    if msg == BTN_RULES:
        await update.message.reply_text(
            f"Правила канала: {https://t.me/zk_baraholka/14}",
            disable_web_page_preview=True
        )
        return

    # 9) Получить 150 ₽ → инструкция (заполни свою механику)
    if msg == BTN_BONUS:
        await update.message.reply_text(
            "🎁 Бонус 150 ₽: пригласите друга в канал и пришлите скрин — начислим бонус.\n"
            "Подробности у администратора."
        )
        return

    # 10) Поиграть → заглушка/мини-активность
   if msg == BTN_PLAY:
    return await show_games_menu(update, context)


    # 11) Задать вопрос → контакт/форма
    if msg == BTN_ASK:
        if ADMIN_USERNAME:
            await update.message.reply_text(f"Задайте вопрос администратору: @{ADMIN_USERNAME}")
        else:
            await update.message.reply_text("Напишите ваш вопрос одним сообщением — я передам администратору.")
        return

    # 12) Важные контакты → краткий список (заполни своими)
    if msg == BTN_CONTACTS:
        await update.message.reply_text(
            "Важные контакты ЖК:\n"
            "• Охрана: +7 (000) 000-00-00\n"
            "• УК: +7 (000) 000-00-01\n"
            "• Аварийная служба: +7 (000) 000-00-02\n"
            "• Консьерж: +7 (000) 000-00-03"
        )
        return

    # Если пришёл текст, который не совпадает с кнопками — ничего не делаем здесь.
    # Пусть обработают другие хендлеры (например, твой ConversationHandler).
    return



from telegram import InlineKeyboardMarkup, InlineKeyboardButton


async def show_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(GAME_BTN_TL,  callback_data="game_tl")],
        [InlineKeyboardButton(GAME_BTN_RPS, callback_data="game_rps")],
        [InlineKeyboardButton(GAME_BTN_FACT,callback_data="game_fact")],
    ])
    await update.message.reply_text("Выберите игру:", reply_markup=kb)

async def send_truth_or_lie_round(query, context):
    stmt, is_true = random.choice(TRUTH_OR_LIE)
    # Сохраняем правильный ответ в data у пользователя
    context.user_data["tl_answer"] = is_true
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Правда", callback_data="game_tl_answer_true"),
         InlineKeyboardButton("❌ Ложь",   callback_data="game_tl_answer_false")],
        [InlineKeyboardButton("🔁 Ещё",    callback_data="game_tl")],
    ])
    await query.edit_message_text(f"Правда или ложь?\n\n{stmt}", reply_markup=kb)

async def play_rps_round(query, context, user_choice=None):
    # Если пользователь сделал ход — разыгрываем раунд
    if user_choice:
        bot_choice = random.choice(["rock", "paper", "scissors"])
        names = {"rock": "✊ Камень", "paper": "✋ Бумага", "scissors": "✌️ Ножницы"}

        # Вычислим результат
        result = "Ничья!"
        if (user_choice, bot_choice) in [
            ("rock","scissors"), ("scissors","paper"), ("paper","rock")
        ]:
            result = "Ты выиграл! 🎉"
        elif user_choice != bot_choice:
            result = "Я выиграл! 😎"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✊", callback_data="game_rps_pick_rock"),
             InlineKeyboardButton("✋", callback_data="game_rps_pick_paper"),
             InlineKeyboardButton("✌️", callback_data="game_rps_pick_scissors")],
            [InlineKeyboardButton("🔁 Ещё", callback_data="game_rps")]
        ])
        await query.edit_message_text(
            f"Ты: {names[user_choice]}\nЯ: {names[bot_choice]}\n\n{result}\n\nСыграем ещё?",
            reply_markup=kb
        )
        return

    # Первый показ выбора
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✊", callback_data="game_rps_pick_rock"),
         InlineKeyboardButton("✋", callback_data="game_rps_pick_paper"),
         InlineKeyboardButton("✌️", callback_data="game_rps_pick_scissors")],
    ])
    await query.edit_message_text("Выбери: камень, ножницы или бумага:", reply_markup=kb)

async def send_random_fact(query):
    await query.edit_message_text(random.choice(FACTS_OR_JOKES))


# ==== ОСНОВНОЙ ФУНКЦИОНАЛ ОБЪЯВЛЕНИЙ ====
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


# Сообщение с кнопкой «Начни здесь» — для закрепа
async def cmd_getbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = await context.bot.get_me()  # у me.username всегда актуальное имя бота
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Начни здесь", url=f"https://t.me/{me.username}?start=from_channel")]]
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
    
    app.add_handler(CallbackQueryHandler(games_router, pattern="^game_"))
    
    app.add_handler(conv)
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    app.run_polling()


if __name__ == "__main__":
    main()











