from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from config.settings import DATABASE_URL

try:
    engine = create_async_engine(DATABASE_URL, echo=False)
except Exception as e:
    print(f"FAILED TO CREATE ENGINE: {e}")
    # Fallback to local sqlite for safety, though it won't persist
    engine = create_async_engine("sqlite+aiosqlite:///./virexa.db")

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    from database.models import Base
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Database initialization failed (ignoring for serverless compatibility): {e}")
