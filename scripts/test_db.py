import asyncio
import pathlib
import sys

import asyncpg


def load_database_url(env_path: pathlib.Path) -> str:
    if not env_path.exists():
        raise FileNotFoundError(f"Missing env file: {env_path}")

    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "DATABASE_URL":
            v = value.strip().strip('"').strip("'")
            return v
    raise RuntimeError("DATABASE_URL not found in .env")


def normalize_for_asyncpg(url: str) -> str:
    # SQLAlchemy async URL format -> asyncpg DSN format
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")

    # Supabase pooler typically requires SSL
    if "sslmode=" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    return dsn


async def main() -> int:
    env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
    url = load_database_url(env_path)
    dsn = normalize_for_asyncpg(url)

    try:
        conn = await asyncpg.connect(dsn, timeout=10)
        val = await conn.fetchval("select 1")
        await conn.close()
        print(f"DB OK: {val}")
        return 0
    except Exception as e:
        print("DB FAILED:")
        print(repr(e))
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

