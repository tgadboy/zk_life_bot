from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

# Вставь токен своего бота
BOT_TOKEN = "8305074407:AAF-AkXy1R9Bjck2Dv8o706QjxeJtzxeJ0g"

# Создаём объект бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("✅ Бот запущен. Напиши /getbutton, чтобы получить кнопку.")

@dp.message(commands=["getbutton"])
async def cmd_getbutton(message: types.Message):
    # Кнопка-ссылка на бота
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить бота", url=f"https://t.me/{(await bot.me()).username}")]
        ]
    )
    await message.answer("Нажми, чтобы запустить бота:", reply_markup=keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
