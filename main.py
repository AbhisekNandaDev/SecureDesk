# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.db import get_db, init_db, close_db
from routes.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Check ---
    try:
        print("Connecting to database...")
        await init_db()
        print("✅ Database connected & initialized successfully.")
    except Exception as e:
        print(f"❌ Database connection failed on startup: {e}")

    yield

    # --- Shutdown Cleanup ---
    await close_db()


app = FastAPI(
    title="SecureDesk API",
    description="Secure Helpdesk & Ticketing Platform with pgvector",
    version="1.0.0",
    #lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)


@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """API endpoint to check if DB is connected and responding."""
    try:
        result = await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "result": result.scalar()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {str(e)}",
        )


@app.get("/", tags=["Root"])
def home():
    return {"message": "Welcome to the SecureDesk API!"}
