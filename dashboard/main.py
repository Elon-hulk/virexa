import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.connection import init_db, get_db
from database.models import Server, Event, Log
from dashboard.routers import auth, servers, logs, settings
from dashboard.routers.auth import get_current_user

app = FastAPI(title="Virexa Dashboard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router)
app.include_router(servers.router)
app.include_router(logs.router)
app.include_router(settings.router)

@app.on_event("startup")
async def startup_event():
    await init_db()

# ── Health check (for UptimeRobot / ping monitors) ────────────────────────────
@app.api_route("/ping", methods=["GET", "HEAD"])
async def ping():
    return JSONResponse({"status": "ok"})

# ── Main dashboard (always renders, login handled client-side) ─────────────────
# include HEAD so external monitors hitting "/" don't get 405s
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    # Always render the page; if no user, JS will show the login overlay
    recent_logs = []
    server_count = events_count = logs_count = 0
    if user:
        server_count = len((await db.execute(select(Server))).scalars().all())
        events_count = len((await db.execute(select(Event))).scalars().all())
        result = await db.execute(select(Log).order_by(Log.timestamp.desc()).limit(10))
        recent_logs = result.scalars().all()
        logs_count = len(recent_logs)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "server_count": server_count,
        "events_count": events_count,
        "logs_count": logs_count,
        "recent_logs": recent_logs,
    })

# ── Logs page ──────────────────────────────────────────────────────────────────
@app.get("/logs_page", response_class=HTMLResponse)
async def logs_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    result = await db.execute(select(Log).order_by(Log.timestamp.desc()).limit(50))
    recent_logs = result.scalars().all()
    return templates.TemplateResponse("logs.html", {
        "request": request, "user": user, "recent_logs": recent_logs
    })

# ── Settings page ──────────────────────────────────────────────────────────────
@app.get("/settings_page", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    guild_id: str = None,
):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("settings.html", {
        "request": request, "user": user, "guild_id": guild_id
    })

# ── Docs ───────────────────────────────────────────────────────────────────────
docs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "virexa-docs", ".output", "public"))
if os.path.exists(docs_path):
    app.mount("/docs", StaticFiles(directory=docs_path, html=True), name="docs")
else:
    @app.get("/docs", response_class=HTMLResponse)
    @app.get("/docs/", response_class=HTMLResponse)
    async def read_docs():
        return HTMLResponse(f"<h1>Docs are building... (Looking for {docs_path}) Please wait a moment and refresh.</h1>")
