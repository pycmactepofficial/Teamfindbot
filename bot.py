import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8605814904:AAHNo71VB6cORx159yxWSEV7FiBw-ia2pHU"
WEB_APP_URL = "https://localhost:8000"      # сюда вставим адрес после запуска ngrok

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    text = (
        "👋 Добро пожаловать в **Team Find**!\n\n"
        "Здесь ты можешь найти команду для киберспорта или набрать игроков в свой состав.\n\n"
        "🔎 **Что умеет бот:**\n"
        "• Найти команду по твоей игре\n"
        "• Найти игроков для своей команды\n"
        "• Фильтр по рангу и роли\n"
        "• Общение с игроками прямо в Telegram\n\n"
        "🎮 **Поддерживаемые игры:**\n"
        "CS2 • Valorant • Dota 2 • Fortnite • League of Legends и другие.\n\n"
        "Нажми «Открыть Team Find🎮», чтобы:\n"
        "👤 создать профиль игрока\n"
        "🔍 найти команду\n"
        "👥 собрать свой состав\n\n"
        "Удачи на пути к победам! 🏆"
    )
    # Кнопка для открытия мини‑приложения
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть Team Find🎮", web_app=WebAppInfo(url=WEB_APP_URL))]
        ]
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message()
async def any_message(message: types.Message):
    await message.answer("Используй /start для начала работы.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())