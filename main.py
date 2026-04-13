import asyncio
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlencode
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import usersservice
from fastapi.staticfiles import StaticFiles
import json
import re
from typing import Optional
import aiohttp

logging.basicConfig(level=logging.INFO)

# ---------- Pydantic модели ----------
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

class RegisterPlayerRequest(BaseModel):
    user_id: int
    type: str = "player"
    name: str
    game: str
    role: str
    rank: str
    description: str = ""
    steam_playtime: int = 0

class RegisterTeamRequest(BaseModel):
    user_id: int
    type: str = "team"
    name: str
    game: str
    rank: str
    members: int
    description: str = ""

# ---------- Telegram Bot ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8605814904:AAHNo71VB6cORx159yxWSEV7FiBw-ia2pHU")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://web-production-be2c5.up.railway.app")
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")
STEAM_RETURN_URL = os.getenv("STEAM_RETURN_URL", f"{WEB_APP_URL}/auth/steam/callback")

dp = Dispatcher()

async def create_bot():
    return Bot(token=BOT_TOKEN)

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

@dp.message()
async def any_message(message: types.Message):
    await message.answer("Используй /start для начала работы.")

# ---------- FastAPI ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await usersservice.user_service.init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика и корень
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse(os.path.join("mini-app", "index.html"))

# ---------- Steam OpenID ----------
@app.get("/auth/steam")
async def steam_login(user_id: int):
    realm = WEB_APP_URL
    return_to = STEAM_RETURN_URL
    params = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.mode': 'checkid_setup',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.return_to': f"{return_to}?user_id={user_id}",
        'openid.realm': realm,
    }
    steam_login_url = "https://steamcommunity.com/openid/login?" + urlencode(params)
    logging.info(f"Redirecting to Steam login for user_id={user_id}")
    return RedirectResponse(steam_login_url)

@app.get("/api/steam/userinfo")
async def get_steam_userinfo(user_id: int):
    steam_id = await usersservice.user_service.get_steam_id(user_id)
    if not steam_id:
        return {"linked": False, "personaname": None}
    if not STEAM_API_KEY:
        return {"linked": True, "personaname": None, "error": "No API key"}
    url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    params = {
        'key': STEAM_API_KEY,
        'steamids': steam_id
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                players = data.get('response', {}).get('players', [])
                if players:
                    personaname = players[0].get('personaname', '')
                    return {"linked": True, "personaname": personaname}
                return {"linked": True, "personaname": None}
        except Exception as e:
            logging.exception(f"Error fetching Steam user info: {e}")
            return {"linked": True, "personaname": None}

@app.get("/auth/steam/callback")
async def steam_callback(request: Request, user_id: Optional[int] = None):
    logging.info(f"Steam callback called, query={dict(request.query_params)}")
    # Извлекаем user_id из query string, если не передан в пути
    query_params = dict(request.query_params)
    if user_id is None and 'user_id' in query_params:
        user_id = int(query_params['user_id'])
    if user_id is None:
        logging.error("Missing user_id in callback")
        return JSONResponse({"error": "Missing user_id"}, status_code=400)
    
    claimed_id = query_params.get('openid.claimed_id')
    if not claimed_id:
        logging.error("No openid.claimed_id in response")
        return JSONResponse({"error": "Invalid Steam response"}, status_code=400)
    
    match = re.search(r'https://steamcommunity.com/openid/id/(\d+)', claimed_id)
    if not match:
        logging.error(f"Could not extract SteamID from {claimed_id}")
        return JSONResponse({"error": "Could not extract Steam ID"}, status_code=400)
    steam_id = match.group(1)
    logging.info(f"Extracted steam_id={steam_id} for user_id={user_id}")
    
    success = await usersservice.user_service.update_steam_id(user_id, steam_id)
    if success:
        logging.info(f"SteamID {steam_id} saved for user {user_id}")
    else:
        logging.error(f"Failed to save SteamID for user {user_id}")
    
    redirect_url = f"{WEB_APP_URL}?user_id={user_id}"
    return RedirectResponse(url=redirect_url)

@app.get("/api/steam/status")
async def get_steam_status(user_id: int):
    steam_id = await usersservice.user_service.get_steam_id(user_id)
    if not steam_id:
        return {"linked": False, "has_games": False}
    games = await usersservice.user_service.get_steam_games(user_id)
    return {"linked": True, "has_games": len(games) > 0, "games_count": len(games)}

@app.get("/api/steam/games")
async def get_steam_games(user_id: int):
    games = await usersservice.user_service.get_steam_games(user_id)
    return JSONResponse(content=games)

# ---------- API регистрации ----------
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
                description=data.get('description', ''),
                steam_playtime=data.get('steam_playtime', 0)
            )
        else:
            result = await usersservice.user_service.add_team(
                user_id=user_id,
                name=data['name'],
                game=data['game'],
                rank=data['rank'],
                members=data.get('members', 5),
                description=data.get('description', '')
            )
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Прочие API ----------
@app.get("/api/data")
async def get_data(game: str = "all", type_filter: str = "all", search: str = ""):
    try:
        data = await usersservice.user_service.search(game=game, type_filter=type_filter, search_text=search)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- API Профиля ----------
@app.get("/api/user-profiles/{user_id}")
async def get_user_profiles(user_id: int):
    try:
        profiles = await usersservice.user_service.get_user_profiles(user_id)
        return JSONResponse(content=profiles)
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
        success = await usersservice.user_service.update_profile(user_id, profile_id, **update_data)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ---------- Верефикация ----------
@app.get("/api/user/{user_id}/verification-status")
async def get_user_verification_status(user_id: int):
    try:
        status = await usersservice.user_service.get_user_verification_status(user_id)
        return JSONResponse(content=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user/{user_id}/verification")
async def receive_user_verification_report(user_id: int, report: VerificationReport):
    try:
        user = await usersservice.user_service._get_user_by_user_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        success = await usersservice.user_service.save_user_verification(user_id, report.dict())
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save report")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ---------- Взаимодействие с анкетой ----------
@app.post("/api/interest")
async def send_interest(req: InterestRequest):
    try:
        profile = await usersservice.user_service.get_profile_by_id(req.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Анкета не найдена")
        owner_chat_id = await usersservice.user_service.get_chat_id_by_user_id(req.owner_user_id)
        if not owner_chat_id:
            raise HTTPException(status_code=404, detail="Владелец анкеты не найден")
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
        bot = await create_bot()
        await bot.send_message(owner_chat_id, text, parse_mode="Markdown", disable_web_page_preview=True)
        return {"status": "success", "message": "Уведомление отправлено"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Запуск ----------
async def run_bot():
    bot = await create_bot()
    await dp.start_polling(bot, skip_updates=True)

async def run_web():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(run_bot(), run_web())

if __name__ == "__main__":
    asyncio.run(main())