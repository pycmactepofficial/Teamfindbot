import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import usersservice
import json

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8605814904:AAHNo71VB6cORx159yxWSEV7FiBw-ia2pHU")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://web-production-be2c5.up.railway.app")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Check and add/update user in JSON
    user_data = usersservice.user_service.add_or_update_user(chat_id, user_id)

    text = (
        "👋 Добро пожаловать в **Team Find**!\n\n"
        "Здесь ты можешь найти команду для киберспорта или набрать игроков в свой состав.\n\n"
        "Нажми «Открыть Team Find🎮», чтобы:\n"
        "👤 создать профиль игрока\n"
        "🔍 найти команду\n"
        "👥 собрать свой состав\n\n"
        "Удачи на пути к победам! 🏆"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть Team Find🎮", web_app=WebAppInfo(url=WEB_APP_URL))]
        ]
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("register_player"))
async def cmd_register_player(message: types.Message):
    await message.answer("Для регистрации игрока используй мини-приложение или пришли данные в формате: /register_player Игра Роль Ранг Описание")

@dp.message(Command("register_team"))
async def cmd_register_team(message: types.Message):
    await message.answer("Для регистрации команды используй мини-приложение или пришли данные в формате: /register_team Игра Ранг Участники Описание")

@dp.message()
async def any_message(message: types.Message):
    await message.answer("Используй /start для начала работы.")

async def run_bot():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(run_bot())
