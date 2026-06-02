from fastapi import Depends, FastAPI, Header, HTTPException, status
import aiosqlite

from config import WEB_ADMIN_API_KEY
from db import DB_PATH

app = FastAPI()


async def require_api_key(x_api_key: str | None = Header(default=None)):
    if not WEB_ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WEB_ADMIN_API_KEY не задан на сервере"
        )

    if x_api_key != WEB_ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный API key"
        )


@app.get("/matches", dependencies=[Depends(require_api_key)])
async def matches():
    async with aiosqlite.connect(DB_PATH) as db:
        return await (await db.execute("SELECT * FROM matches")).fetchall()


@app.get("/scores", dependencies=[Depends(require_api_key)])
async def scores():
    async with aiosqlite.connect(DB_PATH) as db:
        return await (await db.execute("SELECT * FROM scores")).fetchall()
