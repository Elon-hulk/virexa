from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.future import select
from database.connection import get_db
from database.models import Server
from dashboard.routers.auth import get_current_user, fetch_admin_guilds
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.templating import Jinja2Templates
from config.settings import DISCORD_CLIENT_ID

import os
router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@router.get("/servers")
async def list_servers(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Server))
    servers = result.scalars().all()
    return [{"id": s.id, "guild_id": s.guild_id, "log_channel": s.log_channel_id, "prefix": s.prefix} for s in servers]

@router.get("/select_server", response_class=HTMLResponse)
async def select_server(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    admin_guilds = []
    if user.access_token:
        admin_guilds = await fetch_admin_guilds(user.access_token)

    return templates.TemplateResponse("select_server.html", {
        "request": request,
        "user": user,
        "guilds": admin_guilds,
        "discord_client_id": DISCORD_CLIENT_ID,
    })
