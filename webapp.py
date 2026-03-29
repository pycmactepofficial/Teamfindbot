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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
