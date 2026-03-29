import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

import usersservice

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

@app.get("/api/user-profiles/{user_id}")
async def get_user_profiles(user_id: int):
    try:
        profiles = usersservice.user_service.get_user_profiles(user_id)
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
            result = usersservice.user_service.add_user(
                user_id=user_id,
                name=data['name'],
                game=data['game'],
                role=data['role'],
                rank=data['rank'],
                description=data['description']
            )
        else:
            result = usersservice.user_service.add_team(
                user_id=user_id,
                name=data['name'],
                game=data['game'],
                rank=data['rank'],
                members=data['members'],
                description=data['description']
            )
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/profile/{profile_id}")
async def delete_profile(profile_id: int, user_id: int):
    try:
        success = usersservice.user_service.delete_profile(user_id, profile_id)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Profile not found or not owned by user")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/profile/{profile_id}")
async def update_profile(profile_id: int, data: dict):
    try:
        user_id = int(data.get('user_id', 0))
        if user_id == 0:
            raise ValueError("user_id required")
        
        update_data = {k: v for k, v in data.items() if k != 'user_id'}
        success = usersservice.user_service.update_profile(user_id, profile_id, **update_data)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Profile not found or not owned by user")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
