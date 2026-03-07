from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.connection import get_db
from database.models import Server, Event

router = APIRouter()

@router.post("/settings")
async def update_settings(
    request: Request,
    guild_id: str = Form(...),
    prefix: str = Form(...),
    log_channel_id: str = Form(None),
    events: list[str] = Form([]),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Server).where(Server.guild_id == guild_id)
    result = await db.execute(stmt)
    server = result.scalar_one_or_none()
    
    if not server:
        server = Server(guild_id=guild_id)
        db.add(server)

    server.prefix = prefix
    server.log_channel_id = log_channel_id
    
    # Reset events and enable selected ones
    stmt_ev = select(Event).where(Event.guild_id == guild_id)
    result_ev = await db.execute(stmt_ev)
    existing_events = result_ev.scalars().all()
    
    for ev in existing_events:
        ev.enabled = ev.event_name in events
        
    # Find events that are enabled but not in DB yet
    existing_names = [e.event_name for e in existing_events]
    for e in events:
        if e not in existing_names:
            db.add(Event(guild_id=guild_id, event_name=e, enabled=True))

    await db.commit()
    
    return RedirectResponse(url="/", status_code=303)
