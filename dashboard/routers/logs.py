from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import asyncio
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.connection import get_db
from database.models import Log
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket)
    try:
        # Send the last 10 logs on connect
        result = await db.execute(select(Log).order_by(Log.timestamp.desc()).limit(10))
        logs = result.scalars().all()
        for log in reversed(logs):
            await websocket.send_text(json.dumps({
                "id": log.id,
                "guild_id": log.guild_id,
                "event_type": log.event_type,
                "user_id": log.user_id,
                "description": log.description,
                "timestamp": log.timestamp.isoformat()
            }))

        # Keep connection alive, polling for new logs every 5 seconds
        last_id = logs[0].id if logs else 0
        while True:
            await asyncio.sleep(5)
            result = await db.execute(
                select(Log).where(Log.id > last_id).order_by(Log.timestamp.asc())
            )
            new_logs = result.scalars().all()
            for log in new_logs:
                await websocket.send_text(json.dumps({
                    "id": log.id,
                    "guild_id": log.guild_id,
                    "event_type": log.event_type,
                    "user_id": log.user_id,
                    "description": log.description,
                    "timestamp": log.timestamp.isoformat()
                }))
                last_id = log.id

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@router.get("/api/logs")
async def get_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Log).order_by(Log.timestamp.desc()).limit(50))
    logs = result.scalars().all()
    return [{
        "id": log.id,
        "guild_id": log.guild_id,
        "event_type": log.event_type,
        "description": log.description,
        "timestamp": log.timestamp.isoformat()
    } for log in logs]
