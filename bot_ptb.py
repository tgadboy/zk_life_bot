# pip install python-telegram-bot==20.3

import sqlite3  # Добавьте этот импорт
import re
import os
import random
import logging
from typing import Dict, List, Tuple
import time  # Добавьте этот импорт
from telegram.error import Conflict  # Добавьте этот импорт

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    ReplyKeyboardMarkup,
    InputMediaPhoto,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

from database import (
    create_ad, get_ad, update_ad_text, set_ad_photos,
    set_ad_contact, set_ad_paid, set_ad_published, delete_ad
)

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@live_myakinino_park"       # или числовой -100xxxxxxxxx
ADMIN_ID = 6233188035              # твой Telegram user id (число)

# Оплата (опционально)
PROVIDER_TOKEN = ""                # токен провайдера (ЮKassa/CloudPayments)
PRIORITY_PRICE_COP = 30000         # 300 ₽ в копейках

MAX_PHOTOS = 6  # Новый лимит: до 6 фото

# Авто-модерация
BANNED_WORDS = ["мошенн", "наркот", "оруж", "поддел", "эрот", "инвест", "быстрый заработок"]
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MIN_LEN = 10

# Ссылки
CHANNEL_PIN_URL = "https://t.me/zk_baraholka/7"   # закреп канала (вернуться из бота)
RULES_URL = "https://t.me/zk_baraholka/7"        # правила канала

# Имя админа (без @). Если пусто — будем показывать ADMIN_ID.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@live_help_team")
# ===================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("baraholka")

# Состояния диалога объявлений
(CATEGORY, TEXT, PHOTOS, CONTACT, CONFIRM, PAYMENT) = range(6)

# Память для черновиков (MVP без БД)
# ... другие импорты ...
from database import (
    create_ad, get_ad, update_ad_text, set_ad_photos,
    set_ad_contact, set_ad_paid, set_ad_published, delete_ad
)

# ===== КНОПКИ МЕНЮ (reply клавиатура) =====
BTN_SELL        = "💰 Продать"
BTN_FIND        = "🔍 Найти"
BTN_SERVICE     = "🎯 Разместить услугу"
BTN_ADS         = "📢 Разместить рекламу"
BTN_FIND_SVC    = "🛠️ Найти сервис"
BTN_FIND_MASTER = "💅 Найти мастера"
BTN_DEALS       = "🔥 Акции и скидки"
BTN_RULES       = "➡️ Вернуться на канал"
BTN_BONUS       = "🎁 Получить 150 ₽"
BTN_PLAY        = "🎮 Поиграть"
BTN_ASK         = "💬 Задать вопрос"
BTN_CONTACTS    = "☎️ Важные контакты"

# ===== ИГРЫ: данные =====
GAME_BTN_TL   = "✅❌ Правда или ложь"
GAME_BTN_RPS  = "✊✋✌️ Камень, ножницы, бумага"
GAME_BTN_FACT = "😄 Случайный факт или шутка"

TRUTH_OR_LIE: List[Tuple[str, bool]] = [
    ("Солнце — это звезда.", True),
    ("У улитки четыре сердца.", False),
    ("Амазонка — самая длинная река мира.", True),
    ("Человек использует 100% мозга постоянно.", False),
    ("Пингвины живут на Северном полюсе.", False),
    ("Молния может ударить в одно место дважды.", True),
    ("Земля вращается вокруг Солнца.", True),
    ("В Антарктиде есть медведи.", False),
    ("Вода кипит при 50°C.", False),
    ("Кошки могут мурлыкать.", True),
]

FACTS_OR_JOKES: List[str] = [
    "Факт: Самая короткая война в истории длилась около 38 минут.",
    "Шутка: — Доктор, я вижу будущее! — И как оно? — Расплывчатое… у вас очки запотели.",
    "Факт: У осьминога три сердца.",
    "Шутка: Моя диета проста: если я не вижу еды — я сплю.",
    "Факт: Мёд — единственный продукт, который не портится.",
    "🐝 Пчёлы могут узнавать лица людей.",
    "🌍 В мире больше кур, чем людей.",
    "😂 Почему утка перешла дорогу? Чтобы попасть на другую сторону!",
    "🪐 На Юпитере идёт дождь из алмазов.",
    "😄 — Что сказал ноль восьмёрке? — Классный ремень!",
]
# ===== Конец блока игр =====


# ==== УТИЛИТА АВТО-МОДЕРАЦИИ ====
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


# ==== СТАРТ + МЕНЮ ====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>Привет! 👋</b>\n\n"
        "Я Лайвбот — твой помощник на территории ЖК.\n\n"
        "Я помогу найти то, что ты ищешь.\n"
        "Если чего-то нет в списке — ты можешь написать администратору.\n\n"
        "Нажми на нужную кнопку ниже. "
        
    )

    buttons = [
        [BTN_SELL, BTN_FIND],
        [BTN_SERVICE, BTN_ADS],
        [BTN_FIND_SVC, BTN_FIND_MASTER],
        [BTN_DEALS, BTN_BONUS],
        [BTN_PLAY, BTN_CONTACTS],
        [BTN_ASK, BTN_RULES],
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    await update.message.reply_text(
        text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True
    )


# ==== ОБРАБОТКА КНОПОК МЕНЮ (reply) ====
async def start_new_with_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    uid = update.effective_user.id
    pending[uid] = {"category": category, "text": "", "photos": [], "contact": "", "paid": False}
    await update.message.reply_text(
        f"Категория: {category}\n\nНапишите текст объявления (до 1000 символов)."
    )
    return TEXT

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (update.message.text or "").strip()

    if msg == BTN_PLAY:
        await handle_play(update, context)
        return

    if msg == BTN_SELL:
        return await start_new_with_category(update, context, "Продажа")

    if msg == BTN_SERVICE:
        return await start_new_with_category(update, context, "Услуги")

    if msg == BTN_FIND:
        await update.message.reply_text(
            "Чтобы найти объявление, откройте канал и используйте поиск по ключевым словам.\n"
            "Например: «велосипед», «сдаю», «услуги ремонта».",
            disable_web_page_preview=True,
        )
        return

    if msg == BTN_ADS:
        contact_text = "Свяжитесь с администратором для рекламы."
        if ADMIN_USERNAME:
            contact_text += f" Пишите: @{ADMIN_USERNAME}"
        else:
            contact_text += f" ID администратора: {ADMIN_ID}"
        await update.message.reply_text(contact_text)
        return

    if msg == BTN_FIND_SVC:
        await update.message.reply_text(
            "Напишите, какой сервис вы ищете (например: клининг, доставка, ветеринар) — подскажу или дам контакты."
        )
        return

    if msg == BTN_FIND_MASTER:
        await update.message.reply_text(
            "Какого мастера ищете? (например: сантехник, электрик, парикмахер)\n"
            "Напишите одним сообщением — я предложу варианты."
        )
        return

    if msg == BTN_DEALS:
        await update.message.reply_text(
            "Смотрите свежие акции и скидки в канале по хэштегу #акции.\n"
            "Перейти: https://t.me/zk_baraholka",
            disable_web_page_preview=True,
        )
        return

    if msg == BTN_BONUS:
        await update.message.reply_text(
            "🎁 Бонус 150 ₽: пригласите друга в канал и пришлите скрин — начислим бонус.\n"
            "Подробности у администратора."
        )
        return

    if msg == BTN_CONTACTS:
        await update.message.reply_text(
            "Важные контакты ЖК:\n"
            "• Охрана: +7 (000) 000-00-00\n"
            "• УК: +7 (000) 000-00-01\n"
            "• Аварийная служба: +7 (000) 000-00-02\n"
            "• Консьерж: +7 (000) 000-00-03"
        )
        return

    if msg == BTN_ASK:
        if ADMIN_USERNAME:
            await update.message.reply_text(f"Задайте вопрос администратору: @{ADMIN_USERNAME}")
        else:
            await update.message.reply_text("Напишите ваш вопрос одним сообщением — я передам администратору.")
        return

    if msg == BTN_RULES:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Канал ЖК ЛАЙВ", url="https://t.me/zk_baraholka/7")]]
        )
        await update.message.reply_text(
            "Нажмите кнопку ниже, чтобы вернуться на канал:",
            reply_markup=kb
        )
        return



    return


# ==== ИГРЫ ====
async def handle_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton(GAME_BTN_TL,   callback_data="game_tl")],
        [InlineKeyboardButton(GAME_BTN_RPS,  callback_data="game_rps")],
        [InlineKeyboardButton(GAME_BTN_FACT, callback_data="game_fact")],
    ]
    await update.message.reply_text("Выберите игру:", reply_markup=InlineKeyboardMarkup(kb))

async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # Правда или ложь — вопрос
    if q.data == "game_tl":
        stmt, ans = random.choice(TRUTH_OR_LIE)
        context.user_data["tl_answer"] = ans
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Правда", callback_data="tl_true"),
                InlineKeyboardButton("❌ Ложь",   callback_data="tl_false"),
            ]
        ])
        await q.edit_message_text(f"Правда или ложь?\n\n{stmt}", reply_markup=kb)
        return

    # Правда или ложь — ответ
    if q.data in ("tl_true", "tl_false"):
        user_ans = (q.data == "tl_true")
        correct = context.user_data.get("tl_answer")
        text = "🎉 Верно!" if user_ans == correct else "❌ Неверно!"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Ещё", callback_data="game_tl")]])
        await q.edit_message_text(text, reply_markup=kb)
        return

    # Камень, ножницы, бумага — выбор
    if q.data == "game_rps":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✊", callback_data="rps_rock"),
                InlineKeyboardButton("✋", callback_data="rps_paper"),
                InlineKeyboardButton("✌️", callback_data="rps_scissors"),
            ]
        ])
        await q.edit_message_text("Выбери: камень, ножницы или бумага", reply_markup=kb)
        return

    # Камень, ножницы, бумага — раунд
    if q.data.startswith("rps_"):
        user_choice = q.data.split("_")[1]  # rock/paper/scissors
        bot_choice = random.choice(["rock", "paper", "scissors"])
        names = {"rock": "✊ Камень", "paper": "✋ Бумага", "scissors": "✌️ Ножницы"}

        result = "Ничья!"
        if (user_choice, bot_choice) in [
            ("rock", "scissors"), ("scissors", "paper"), ("paper", "rock")
        ]:
            result = "Ты выиграл! 🎉"
        elif user_choice != bot_choice:
            result = "Я выиграл! 😎"

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✊", callback_data="rps_rock"),
                InlineKeyboardButton("✋", callback_data="rps_paper"),
                InlineKeyboardButton("✌️", callback_data="rps_scissors"),
            ],
            [InlineKeyboardButton("🔁 Ещё", callback_data="game_rps")],
        ])
        await q.edit_message_text(
            f"Ты: {names[user_choice]}\nЯ: {names[bot_choice]}\n\n{result}",
            reply_markup=kb,
        )
        return

    # Случайный факт/шутка
    if q.data == "game_fact":
        await q.edit_message_text(random.choice(FACTS_OR_JOKES))
        return


# ==== ОСНОВНОЙ ФУНКЦИОНАЛ ОБЪЯВЛЕНИЙ ====
async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Создаем новое объявление в БД и сохраняем его ID в данные контекста (context.user_data)
    ad_id = create_ad(user.id, None)  # Категория пока None
    context.user_data['current_ad_id'] = ad_id  # Сохраняем ID объявления для этого пользователя

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
    try:
        q = update.callback_query
        await q.answer()
        user = q.from_user

        # Достаем ID объявления из контекста
        ad_id = context.user_data.get('current_ad_id')
        log.info(f"User {user.id} selected category for ad {ad_id}")
        if not ad_id:
            await q.edit_message_text("Сессия истекла. Начните заново: /new")
            return ConversationHandler.END

        cat_map = {
            "cat_sale": "Продажа",
            "cat_service": "Услуги",
            "cat_buy": "Покупка",
            "cat_free": "Отдам/Обмен",
            "cat_other": "Другое",
        }
        selected_category = cat_map.get(q.data, "Другое")
        log.info(f"Selected category: {selected_category}")

        # Обновляем категорию в базе данных
        conn = sqlite3.connect('baraholka.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE ads SET category = ? WHERE id = ? AND user_id = ?',
            (selected_category, ad_id, user.id)
        )
        conn.commit()
        
        # Проверяем, обновилась ли запись
        if cursor.rowcount == 0:
            log.error(f"Failed to update category for ad {ad_id}. No rows affected.")
            await q.edit_message_text("Произошла ошибка при сохранении категории. Попробуйте снова: /new")
            conn.close()
            return ConversationHandler.END
        
        conn.close()
        log.info(f"Category updated successfully for ad {ad_id}")

        await q.edit_message_text(
            f"✅ Категория: {selected_category}\n\n"
            "Напиши текст объявления (от 10 до 1000 символов)"
        )
        return TEXT


    except Exception as e:
        # Логируем любую ошибку, которая может возникнуть
        log.error(f"Error in on_category: {str(e)}", exc_info=True)
        # Пытаемся отправить сообщение об ошибке пользователю
        try:
            await q.edit_message_text("😕 Произошла техническая ошибка. Попробуй начать заново командой /new")
        except:
            pass
        return ConversationHandler.END

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        text = (update.message.text or "").strip()

        # Достаем ID объявления из контекста
        ad_id = context.user_data.get('current_ad_id')
        log.info(f"User {user_id} sent text for ad {ad_id}")

        if not ad_id:
            await update.message.reply_text("Сессия истекла. Начни заново: /new")
            return ConversationHandler.END

        # Проверяем длину текста
        if len(text) > 1000:
            await update.message.reply_text("Слишком длинно. Сократи до 1000 символов.")
            return TEXT

        # Проверяем текст автоматической модерацией
        ok, reason = auto_moderate(text)
        if not ok:
            await update.message.reply_text(f"Текст не прошел проверку: {reason}\nПопробуй отправить другой текст.")
            return TEXT

        # ОБНОВЛЯЕМ ТЕКСТ ОБЪЯВЛЕНИЯ В БАЗЕ ДАННЫХ
        success = update_ad_text(ad_id, user_id, text)
        
        if not success:
            log.error(f"Failed to update text in DB for ad {ad_id}. User {user_id}")
            await update.message.reply_text("Произошла ошибка при сохранении. Попробуй снова: /new")
            return ConversationHandler.END

        log.info(f"Text for ad {ad_id} updated successfully.")
        
        # Сообщение и логика остаются прежними
        await update.message.reply_text(
            f"✅ <b>Текст принят </b>\n\n"
            f"Теперь отправь до {MAX_PHOTOS} фото для объявления. Можно отправить сразу несколько.\n\n"
            f"<i>💡 Советы для лучшего объявления:</i>\n\n"
            f"• <b>Первое фото</b> сделай самым лучшим и привлекательным (главный вид товара)\n\n"
            f"• <b>На остальных фото</b> показывай детали, недостатки, этикетки, комплектацию\n\n"
            "Когда закончишь — нажми /done\n"
            "Если фото не нужно — нажми /skip",
            parse_mode="HTML"
        )
        return PHOTOS

    except Exception as e:
        log.error(f"Error in on_text: {str(e)}", exc_info=True)
        await update.message.reply_text("😕 Произошла непредвиденная ошибка. Попробуй начать заново командой /new")
        return ConversationHandler.END
        
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        # Достаем ID объявления из контекста
        ad_id = context.user_data.get('current_ad_id')
        if not ad_id:
            await update.message.reply_text("Сессия истекла. Начните заново: /new")
            return ConversationHandler.END

        # Получаем данные объявления с помощью функции get_ad (она возвращает словарь!)
        ad_data = get_ad(ad_id, user_id)
        if not ad_data:
            await update.message.reply_text("Объявление не найдено. Начните заново: /new")
            return ConversationHandler.END

        # Теперь можно обращаться по имени поля, так как это словарь
        current_photos = ad_data['photos'].split(',') if ad_data['photos'] else []

        # Проверяем лимит фото
        if len(current_photos) >= MAX_PHOTOS:
            await update.message.reply_text(f"❌ Максимум {MAX_PHOTOS} фото. Отправьте /done чтобы завершить.")
            return PHOTOS

        # Добавляем новое фото
        new_photo_id = update.message.photo[-1].file_id
        current_photos.append(new_photo_id)

        # Обновляем запись в БД
        success = set_ad_photos(ad_id, user_id, current_photos)
        
        if not success:
            await update.message.reply_text("❌ Ошибка при сохранении фото. Попробуйте снова.")
            return PHOTOS

        await update.message.reply_text(
            f"✅ Фото {len(current_photos)}/{MAX_PHOTOS} добавлено.\n"
            f"Отправьте ещё фото или /done чтобы завершить."
        )
        return PHOTOS

    except Exception as e:
        log.error(f"Error in on_photo: {str(e)}", exc_info=True)
        await update.message.reply_text("😕 Ошибка при обработке фото. Попробуй еще раз загрузить фото или начните заново /new")
        return PHOTOS

async def on_photos_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        ad_id = context.user_data.get('current_ad_id')
        if not ad_id:
            await update.message.reply_text("Сессия истекла. Начните заново: /new")
            return ConversationHandler.END

        await update.message.reply_text(
            "✅ Теперь укажи контакт для связи.\n" 
            "(твой ник в телеграме, например @zk_life_bot )\n\n"
            "Или отправь /me чтобы я автоматически ввёл твой Telegram username."
        )
        return CONTACT
    
    except Exception as e:
        log.error(f"Error in on_photos_done: {str(e)}", exc_info=True)
        await update.message.reply_text("😕 Произошла ошибка. Попробуй начать заново: /new")
        return ConversationHandler.END

async def on_photos_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        ad_id = context.user_data.get('current_ad_id')
        if not ad_id:
            await update.message.reply_text("Сессия истекла. Начни заново: /new")
            return ConversationHandler.END

        # Явно устанавливаем пустой список фото в БД
        success = set_ad_photos(ad_id, user_id, [])
        if not success:
            log.warning(f"Failed to set empty photos for ad {ad_id}")

        await update.message.reply_text(
            "✅ Фото пропущены. Укажи контакт для связи (твой ник в телеграме, например @zk_life_bot ).\n"
            "Или отправь /me чтобы я автоматически ввёл твой Telegram username."
        )
        return CONTACT

    except Exception as e:
        log.error(f"Error in on_photos_skip: {str(e)}", exc_info=True)
        await update.message.reply_text("😕 Произошла ошибка. Попробуй начать заново: /new")
        return ConversationHandler.END

async def on_contact_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        ad_id = context.user_data.get('current_ad_id')
        if not ad_id:
            await update.message.reply_text("Сессия истекла. Начни заново: /new")
            return ConversationHandler.END

        # Используем username пользователя
        username = user.username
        contact = f"@{username}" if username else f"ID: {user_id}"
        
        # Сохраняем контакт в БД
        success = set_ad_contact(ad_id, user_id, contact)
        
        if not success:
            await update.message.reply_text("❌ Ошибка при сохранении контакта. Попробуй снова.")
            return CONTACT

        log.info(f"Contact set to {contact} for ad {ad_id}")
        return await confirm_preview(update, context)

    except Exception as e:
        log.error(f"Error in on_contact_me: {str(e)}", exc_info=True)
        await update.message.reply_text("😕 Произошла ошибка. Попробуй ещё раз: /new")
        return ConversationHandler.END

async def on_contact_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        ad_id = context.user_data.get('current_ad_id')
        if not ad_id:
            await update.message.reply_text("Сессия истекла. Начни заново: /new")
            return ConversationHandler.END

        contact = (update.message.text or "").strip()
        
        # Простая валидация контакта
        if not contact or len(contact) < 3:
            await update.message.reply_text("❌ Слишком короткий контакт. Введи твой ник @username.")
            return CONTACT

        # Сохраняем контакт в БД
        success = set_ad_contact(ad_id, user_id, contact)
        
        if not success:
            await update.message.reply_text("❌ Ошибка при сохранении контакта. Попробуй снова.")
            return CONTACT

        log.info(f"Contact set to {contact} for ad {ad_id}")
        return await confirm_preview(update, context)

    except Exception as e:
        log.error(f"Error in on_contact_text: {str(e)}", exc_info=True)
        await update.message.reply_text("😕 Произошла ошибка. Попробуй начать заново: /new")
        return ConversationHandler.END

async def confirm_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        ad_id = context.user_data.get('current_ad_id')
        if not ad_id:
            await update.message.reply_text("Сессия истекла. Начни заново: /new")
            return ConversationHandler.END

        # Получаем данные объявления из БД
        ad_data = get_ad(ad_id, user_id)
        if not ad_data:
            await update.message.reply_text("Объявление не найдено. Начни заново: /new")
            return ConversationHandler.END

        # Формируем превью
        preview = (
            f"<b>Предпросмотр объявления:</b>\n\n"
            f"🏷️ Категория: {ad_data['category']}\n\n"
            f"📄 Описание: {ad_data['text']}\n\n"
            f"👤 Контакт: {ad_data['contact']}\n\n"
            f"🖼️ Фото: {len(ad_data['photos'].split(',')) if ad_data['photos'] else 0} шт."
        )

        # Создаем кнопки
        buttons = [[InlineKeyboardButton("✅ Отправить бесплатно", callback_data="post_free")]]
        
        if PROVIDER_TOKEN:
            buttons.append([InlineKeyboardButton("⚡ Приоритет (платно)", callback_data="post_paid")])
        
        buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="post_cancel")])

        await update.message.reply_text(
            preview,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return CONFIRM

    except Exception as e:
        log.error(f"Error in confirm_preview: {str(e)}", exc_info=True)
        await update.message.reply_text("😕 Произошла ошибка. Попробуйте начать заново: /new")
        return ConversationHandler.END

async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        await q.answer()
        user_id = q.from_user.id
        
        ad_id = context.user_data.get('current_ad_id')
        if not ad_id:
            await q.edit_message_text("Сессия истекла. Начните заново: /new")
            return ConversationHandler.END

        # Получаем данные объявления для модерации
        ad_data = get_ad(ad_id, user_id)
        if not ad_data:
            await q.edit_message_text("Объявление не найдено. Начните заново: /new")
            return ConversationHandler.END

        # Проверяем текст автомодерацией
        ok, reason = auto_moderate(ad_data['text'])
        if not ok:
            await q.edit_message_text(
                f"Объявление не прошло проверку: {reason}\nОтредактируйте и отправьте заново (/new)."
            )
            return ConversationHandler.END

        if q.data == "post_cancel":
            # Удаляем объявление из БД при отмене
            delete_ad(ad_id, user_id)
            await q.edit_message_text("❌ Объявление отменено и удалено.")
            return ConversationHandler.END

        if q.data == "post_free":
            # Публикуем бесплатно
            await q.edit_message_text("📤 Отправляем объявление в канал...")
            await publish_to_channel(context, user_id, priority=False)
            await q.edit_message_text("✅ Объявление опубликовано в канале!")
            return ConversationHandler.END

        if q.data == "post_paid":
            if not PROVIDER_TOKEN:
                await q.edit_message_text("⚠️ Оплата временно недоступна. Используйте бесплатную публикацию.")
                return CONFIRM
            
            # Создаем счет на оплату
            price = [LabeledPrice("Приоритетная публикация", PRIORITY_PRICE_COP)]
            await context.bot.send_invoice(
                chat_id=user_id,
                title="Приоритетная публикация",
                description="Ваше объявление будет размещено вверху ленты",
                payload=f"priority_{ad_id}",
                provider_token=PROVIDER_TOKEN,
                currency="RUB",
                prices=price,
            )
            await q.edit_message_text("💳 Счет для оплаты отправлен. После оплаты ваши объявления будут опубликованы.")
            return PAYMENT

    except Exception as e:
        log.error(f"Error in on_confirm: {str(e)}", exc_info=True)
        try:
            await q.edit_message_text("😕 Произошла ошибка. Попробуй начать заново: /new")
        except:
            pass
        return ConversationHandler.END

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def on_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        ad_id = context.user_data.get('current_ad_id')
        
        if ad_id:
            # Помечаем объявление как оплаченное в БД
            set_ad_paid(ad_id, user_id)
            # Публикуем с приоритетом
            await update.message.reply_text("💳 Оплата получена! Публикуем объявление...")
            await publish_to_channel(context, user_id, priority=True)
        else:
            # Если ad_id нет в контексте, пытаемся найти последнее объявление пользователя
            conn = sqlite3.connect('baraholka.db')
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM ads WHERE user_id = ? ORDER BY id DESC LIMIT 1',
                (user_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                ad_id = result['id']
                set_ad_paid(ad_id, user_id)
                await update.message.reply_text("💳 Оплата получена! Публикуем ваше последнее объявление...")
                await publish_to_channel(context, user_id, priority=True)
            else:
                await update.message.reply_text("❌ Не найдено объявление для публикации. Создайте новое: /new")

    except Exception as e:
        log.error(f"Error in on_paid: {str(e)}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при обработке оплаты. Свяжитесь с администратором.")
        

async def publish_to_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int, priority: bool):
    try:
        log.info(f"Starting publication process for user {user_id}, priority: {priority}")
        
        # Получаем последнее объявление пользователя из БД
        conn = sqlite3.connect('baraholka.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT category, text, contact, photos FROM ads WHERE user_id = ? ORDER BY id DESC LIMIT 1',
            (user_id,)
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            log.error(f"No ad found for user {user_id}")
            await context.bot.send_message(chat_id=user_id, text="❌ Объявление не найдено в базе данных.")
            return

        category, text, contact, photos_str = result
        photo_ids = photos_str.split(',') if photos_str else []
        
        log.info(f"Ad data: category={category}, text_len={len(text)}, contact={contact}, photos={len(photo_ids)}")

        # Формируем подпись
        caption = (
            f"{'⚡ ПРИОРИТЕТНОЕ ОБЪЯВЛЕНИЕ\n\n' if priority else ''}"
            f"🏷️ **Категория:** {category}\n\n"
            f"📄 **Описание:** {text}\n\n"
            f"👤 **Контакт:** {contact}"
        )
        
        # Публикуем в канал
        try:
            if photo_ids:
                # Отправляем медиагруппу
                media = []
                for i, photo_id in enumerate(photo_ids):
                    media.append(InputMediaPhoto(
                        media=photo_id, 
                        caption=caption if i == 0 else None,
                        parse_mode="Markdown"
                    ))
                
                await context.bot.send_media_group(
                    chat_id=CHANNEL_ID,
                    media=media
                )
                log.info(f"Media group sent to channel {CHANNEL_ID} with {len(photo_ids)} photos")
            else:
                # Отправляем только текст
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=caption,
                    parse_mode="Markdown"
                )
                log.info(f"Text message sent to channel {CHANNEL_ID}")

            # Помечаем как опубликованное
            conn = sqlite3.connect('baraholka.db')
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE ads SET is_published = TRUE WHERE user_id = ? AND id = (SELECT MAX(id) FROM ads WHERE user_id = ?)',
                (user_id, user_id)
            )
            conn.commit()
            conn.close()

            await context.bot.send_message(chat_id=user_id, text="✅ Объявление успешно опубликовано в канале!")
            log.info(f"Ad successfully published for user {user_id}")

        except Exception as channel_error:
            log.error(f"Channel publication error: {channel_error}")
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Ошибка при отправке в канал. Проверьте права бота в канале."
            )

    except Exception as e:
        log.error(f"Error in publish_to_channel: {str(e)}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="😕 При публикации объявления произошла ошибка. Администратор уже уведомлен."
            )
        except:
            pass

async def cmd_check_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка прав бота в канале"""
    try:
        chat = await context.bot.get_chat(CHANNEL_ID)
        await update.message.reply_text(f"Канал: {chat.title}\nID: {chat.id}\nТип: {chat.type}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка доступа к каналу: {e}")
        

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    pending.pop(uid, None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# Сообщение с кнопкой «Начни здесь» — для закрепа
async def cmd_getbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = await context.bot.get_me()
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Начни здесь", url=f"https://t.me/{me.username}?start=from_channel")]]
    )
    await update.message.reply_text(
        "📢 Разместить объявление в «ЖК Барахолка»\n\nНажмите кнопку ниже, чтобы отправить объявление боту.",
        reply_markup=kb,
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("getbutton", cmd_getbutton))
    app.add_handler(CommandHandler("play", handle_play))
    app.add_handler(CommandHandler("check", cmd_check_channel))

    # Игры (inline callbacks)
    app.add_handler(CallbackQueryHandler(game_callback, pattern="^(game_|tl_|rps_)"))

    # Воронка объявлений (ConversationHandler)
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
    app.add_handler(conv)

    # Обработчик меню (reply-кнопки)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    # Запуск приложения с обработкой ошибок
    try:
        app.run_polling()
    except Conflict as e:
        log.error(f"Conflict error: {e}. Restarting in 10 seconds...")
        time.sleep(10)
        main()  # Перезапускаем приложение
    except Exception as e:
        log.error(f"Unexpected error: {e}. Restarting in 30 seconds...")
        time.sleep(30)
        main()  # Перезапускаем приложение

if __name__ == "__main__":
    main()


































