from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

BOT_TOKEN = "8305074407:AAF-AkXy1R9Bjck2Dv8o706QjxeJtzxeJ0g"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот на PTB запущен. Команда /getbutton выдаёт кнопку.")

async def getbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = await context.bot.get_me()
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🚀 Запустить бота", url=f"https://t.me/zk_life_bot")]]
    )
    await update.message.reply_text("Нажми, чтобы запустить бота:", reply_markup=kb)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getbutton", getbutton))
    app.run_polling()

if __name__ == "__main__":
    main()
