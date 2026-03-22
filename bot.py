import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

import usersservice

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8605814904:AAHNo71VB6cORx159yxWSEV7FiBw-ia2pHU"
WEB_APP_URL = "https://web-production-be2c5.up.railway.app/#"  # Замени на реальный URL Railway

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажи конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return FileResponse(os.path.join("mini-app", "index.html"))

# app.mount("/", StaticFiles(directory="mini-app", html=True), name="static")  # Убрал, чтобы не перекрывать routes

@app.get("/api/data")
async def get_data(game: str = "all", type_filter: str = "all", search: str = ""):
    try:
        data = usersservice.user_service.search(game=game, type_filter=type_filter, search_text=search)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
async def test():
    return {"test": "API is working"}

@app.post("/api/register")
async def register(data: dict):
    try:
        if data['type'] == 'player':
            usersservice.user_service.add_user(
                user_id=data['id'],
                name=data['name'],
                game=data['game'],
                role=data['role'],
                rank=data['rank'],
                description=data['description']
            )
        else:
            usersservice.user_service.add_team(
                user_id=data['id'],
                name=data['name'],
                game=data['game'],
                rank=data['rank'],
                members=data['members'],
                description=data['description']
            )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@dp.message(Command("register_player"))
async def cmd_register_player(message: types.Message):
    # Простая регистрация, в реальности нужно диалог
    await message.answer("Для регистрации игрока используй мини-приложение или пришли данные в формате: /register_player Игра Роль Ранг Описание")

@dp.message(Command("register_team"))
async def cmd_register_team(message: types.Message):
    await message.answer("Для регистрации команды используй мини-приложение или пришли данные в формате: /register_team Игра Ранг Участники Описание")

@dp.message()
async def any_message(message: types.Message):
    await message.answer("Используй /start для начала работы.")

async def main():
    # Запуск бота и сервера параллельно через Uvicorn Server
    from asyncio import create_task
    bot_task = create_task(dp.start_polling(bot))
    port = int(os.getenv("PORT", 8082))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    server_task = create_task(server.serve())
    await asyncio.gather(bot_task, server_task)

async def run_server_only():
    port = int(os.getenv("PORT", 8082))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))