import asyncio
import os
import uvicorn
from bot import run_bot
from webapp import app

async def main():
    bot_task = asyncio.create_task(run_bot())

    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    web_task = asyncio.create_task(uvicorn.Server(config).serve())

    await asyncio.gather(bot_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())
