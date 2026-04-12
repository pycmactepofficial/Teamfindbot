import asyncio
import logging
import os
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import usersservice
from fastapi.staticfiles import StaticFiles
import json

logging.basicConfig(level=logging.INFO)

class InterestRequest(BaseModel):
    profile_id: int
    owner_user_id: int
    current_user_id: int
    current_username: str = ""
    current_name: str = ""

class VerificationReport(BaseModel):
    user_id: int
    timestamp: str
    verdict: str
    findings: dict

# ---------- Telegram Bot ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8605814904:AAHNo71VB6cORx159yxWSEV7FiBw-ia2pHU")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://web-production-be2c5.up.railway.app")
PROXY_URL = 'socks5://193.233.254.63:1080'

dp = Dispatcher()

async def create_bot_and_dispatcher():
    bot = Bot(token=BOT_TOKEN)
    return bot

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    await usersservice.user_service.add_or_update_user(chat_id, user_id)

    text = (
        "👋 Добро пожаловать в **Team Find**!\n\n"
        "Нажми «Открыть Team Find🎮», чтобы создать профиль или найти команду."
    )

    webapp_url_with_user = f"{WEB_APP_URL}?user_id={user_id}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть Team Find🎮", web_app=WebAppInfo(url=webapp_url_with_user))]
        ]
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("register_player"))
async def cmd_register_player(message: types.Message):
    await message.answer("Используй мини-приложение для регистрации.")

@dp.message(Command("register_team"))
async def cmd_register_team(message: types.Message):
    await message.answer("Используй мини-приложение для регистрации.")

@dp.message()
async def any_message(message: types.Message):
    await message.answer("Используй /start для начала работы.")

@dp.message(lambda msg: msg.web_app_data is not None)
async def handle_webapp_data(message: types.Message):
    data = json.loads(message.web_app_data.data)
    user_id = message.from_user.id
    if data['type'] == 'player':
        result = await usersservice.user_service.add_user(
            user_id=user_id,
            name=data['name'],
            game=data['game'],
            role=data['role'],
            rank=data['rank'],
            description=data['description']
        )
    else:
        result = await usersservice.user_service.add_team(
            user_id=user_id,
            name=data['name'],
            game=data['game'],
            rank=data['rank'],
            members=data['members'],
            description=data['description']
        )
    await message.answer("✅ Анкета создана! Загляни в 'Мои анкеты'.")

# ---------- FastAPI WebApp ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await usersservice.user_service.init_db()
    yield
    # Shutdown (опционально закрываем соединения, если нужно)

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return FileResponse(os.path.join("mini-app", "index.html"))

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/data")
async def get_data(game: str = "all", type_filter: str = "all", search: str = ""):
    try:
        data = await usersservice.user_service.search(game=game, type_filter=type_filter, search_text=search)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user-profiles/{user_id}")
async def get_user_profiles(user_id: int):
    try:
        profiles = await usersservice.user_service.get_user_profiles(user_id)
        return JSONResponse(content=profiles)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/register")
async def register(data: dict):
    try:
        user_id = int(data.get('user_id', 0))
        if user_id == 0:
            raise ValueError("user_id required")
        if data['type'] == 'player':
            result = await usersservice.user_service.add_user(
                user_id=user_id,
                name=data['name'],
                game=data['game'],
                role=data['role'],
                rank=data['rank'],
                description=data['description']
            )
        else:
            result = await usersservice.user_service.add_team(
                user_id=user_id,
                name=data['name'],
                game=data['game'],
                rank=data['rank'],
                members=data['members'],
                description=data.get('description', '')
            )
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/profile/{profile_id}")
async def delete_profile(profile_id: int, user_id: int):
    try:
        success = await usersservice.user_service.delete_profile(user_id, profile_id)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/profile/{profile_id}")
async def update_profile(profile_id: int, data: dict):
    try:
        user_id = int(data.get('user_id', 0))
        if user_id == 0:
            raise ValueError("user_id required")
        update_data = {k: v for k, v in data.items() if k != 'user_id'}
        # Проверка: если тип команды, то обновляем team_members
        success = await usersservice.user_service.update_profile(user_id, profile_id, **update_data)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/user/{user_id}/verification-status")
async def get_user_verification_status(user_id: int):
    try:
        status = await usersservice.user_service.get_user_verification_status(user_id)
        return JSONResponse(content=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/user/{user_id}/verification")
async def receive_user_verification_report(user_id: int, report: VerificationReport):
    """
    Принимает отчёт от клиента античита для верификации пользователя.
    """
    try:
        # Проверяем, существует ли пользователь
        user = await usersservice.user_service._get_user_by_user_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Сохраняем результат верификации
        success = await usersservice.user_service.save_user_verification(user_id, report.dict())
        if success:
            return {"status": "success", "message": "Verification report saved for user"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save report")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/interest")
async def send_interest(req: InterestRequest):
    try:
        # Получаем данные анкеты
        profile = await usersservice.user_service.get_profile_by_id(req.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Анкета не найдена")

        # Получаем chat_id владельца
        owner_chat_id = await usersservice.user_service.get_chat_id_by_user_id(req.owner_user_id)
        if not owner_chat_id:
            raise HTTPException(status_code=404, detail="Владелец анкеты не найден в базе")

        # Формируем текст и ссылку на откликнувшегося
        if req.current_username:
            mention = f"@{req.current_username}"
            link = f"tg://resolve?domain={req.current_username}"
        else:
            mention = f"пользователь {req.current_user_id}"
            link = f"tg://user?id={req.current_user_id}"

        profile_type = profile['type']
        profile_name = profile['name']

        if profile_type == 'team':
            text = f"🏆 В вашу команду **{profile_name}** хочет вступить {mention}\n\n👉 [Написать {mention}]({link})"
        else:
            text = f"👤 Пользователь {mention} заинтересован в вашей анкете игрока **{profile_name}**\n\n👉 [Написать {mention}]({link})"

        # Отправляем сообщение через бота
        bot = await create_bot_and_dispatcher()
        await bot.send_message(owner_chat_id, text, parse_mode="Markdown", disable_web_page_preview=True)

        return {"status": "success", "message": "Уведомление отправлено"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Запуск обоих сервисов ----------
async def run_bot():
    bot = await create_bot_and_dispatcher()
    await dp.start_polling(bot, skip_updates=True)

async def run_web():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(run_bot(), run_web())

if __name__ == "__main__":
    asyncio.run(main())