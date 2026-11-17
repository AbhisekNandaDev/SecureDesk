import asyncio
import sys
from pathlib import Path

# Add project root to sys.path so modules like 'core', 'models', 'schema' can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from core.db import engine


async def check_database_connection():
    print("Testing connection to database...")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            db_version = result.scalar()
            print("✅ Database connected successfully!")
            print(f"PostgreSQL version: {db_version}")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_database_connection())
